import os
from dotenv import load_dotenv

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# 1. Initialize Constants (Ensure these exactly match your verified working variables)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_URL")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME =  os.getenv("AZURE_KNOWLEDGE_INDEX")

# 2. Instantiate App and Managed Clients
app = FastAPI(
    title="Etisalat Enterprise AI Gateway",
    description="Production-grade API exposing our Azure AI Search and GPT-4.1-mini RAG pipeline.",
    version="1.0.0"
)

ai_client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),                            
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

# 3. Define the Structured Input Contract (Pydantic Model)
class QueryRequest(BaseModel):
    question: str

# 4. Create the Core Chat Endpoint
@app.post("/api/v1/chat", summary="Query the Cloud Knowledge Base")
async def chat_endpoint(request: QueryRequest):
    try:
        user_question = request.question
        
        # Step A: Vectorize the live question
        query_resp = ai_client.embeddings.create(
            input=[user_question], 
            model="text-embedding-3-small"
        )
        question_vector = query_resp.data[0].embedding
        
        # Step B: Execute Cloud Vector Query
        vector_query = VectorizedQuery(
            vector=question_vector,
            k_nearest_neighbors=1,
            fields="content_vector"
        )
        
        search_results = search_client.search(
            search_text=None,
            vector_queries=[vector_query],
            top=1,
            select=["content_text"]
        )
        
        retrieved_chunk = ""
        for doc in search_results:
            retrieved_chunk = doc["content_text"]
            break
            
        if not retrieved_chunk:
            raise HTTPException(status_code=404, detail="No relevant context found in corporate cloud memory.")

        # Step C: Setup Grounding Instructions
        system_instruction = (
            "You are an expert corporate assistant. Answer the user's question using "
            "ONLY the provided corporate text context. Be exact and direct."
        )
        user_payload = f"Context from Live Azure Database:\n{retrieved_chunk}\n\nQuestion: {user_question}"
        
        # Step D: Call live gpt-4.1-mini deployment
        chat_response = ai_client.chat.completions.create(
            model="gpt-4.1-mini", 
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_payload}
            ],
            temperature=0.1
        )
        
        return {
            "status": "success",
            "query": user_question,
            "answer": chat_response.choices[0].message.content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# 5. Health Check Endpoint (Vital for enterprise monitoring and container readiness probes)
@app.get("/health", summary="API Health Check")
async def health_check():
    return {"status": "healthy", "service": "enterprise-ai-core"}