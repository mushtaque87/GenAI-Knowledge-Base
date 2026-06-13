import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

# 1. Initialize Credentials
# (Ensure these match the exact resource credentials from your prior steps)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL", "text-embedding-3-small")

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_URL")  
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY") 
INDEX_NAME = os.getenv("AZURE_KNOWLEDGE_INDEX")

# 2. Instantiate both Cloud Service Clients
ai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-06-01"
)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

def query_cloud_knowledge_base(user_question: str) -> str:
    """
    Executes a cloud-native RAG pipeline using live Azure AI Search 
    and Azure OpenAI.
    """
    # Step A: Vectorize the live question using the cloud model
    query_resp = ai_client.embeddings.create(
        input=[user_question], 
        model=os.getenv("AZURE_OPENAI_MODEL", "text-embedding-3-small")
    )
    question_vector = query_resp.data[0].embedding
    
    # Step B: Configure the cloud vector query parameters
    vector_query = VectorizedQuery(
        vector=question_vector,
        k_nearest_neighbors=1,        # Pull the absolute best 1 matching chunk
        fields="content_vector"       # Look inside the vector column we designed
    )
    
    # Step C: Execute Vector Search against the Azure Cloud Index
    print("Searching Azure AI Search cloud database...")
    search_results = search_client.search(
        search_text=None,             # Pure vector search (no text keyword matching)
        vector_queries=[vector_query],
        top=1,
        select=["content_text"]       # Pull only the raw text field back
    )
    
    # Extract the text payload from the search hit response object
    retrieved_chunk = ""
    for doc in search_results:
        retrieved_chunk = doc["content_text"]
        break
        
    if not retrieved_chunk:
        return "No relevant context found in the cloud index."

    # Step D: Construct the grounding prompt for the Chat Model
    system_instruction = (
        "You are an expert corporate assistant. Answer the user's question using "
        "ONLY the provided corporate text context. Be exact and direct."
    )
    user_payload = f"Context from Live Azure Database:\n{retrieved_chunk}\n\nQuestion: {user_question}"
    
    # Step E: Generate precise answer via Chat Model
    print(f"Generating precise response via deployment '{AZURE_OPENAI_CHAT_DEPLOYMENT}'...")
    chat_response = ai_client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_payload}
        ],
        temperature=0.1
    )
    
    return chat_response.choices[0].message.content

# --- Run the Cloud RAG Execution ---
if __name__ == "__main__":
    question = "When was Etisalat CEO appointed"
    
    print(f"\nUser Query: '{question}'")
    answer = query_cloud_knowledge_base(question)
    
    print("\n=== Verified System Response ===")
    print(answer)