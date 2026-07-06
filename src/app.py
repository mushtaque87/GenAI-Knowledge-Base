import os
import json
import logging
from dotenv import load_dotenv

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# 🛠️ OPENTELEMETRY TRACING IMPORTS
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# 1. Configure the system logger framework
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai_gateway")

# 🤫 OPTIMIZATION: Mute background OTel exporter HTTP dependency logging noise
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 🛠️ EXTRACT AND CHECK THE CONNECTION STRING BEFORE INITIALIZATION
AI_CONN_STR = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

if not AI_CONN_STR:
    logger.warning(
        "⚠️ APPLICATIONINSIGHTS_CONNECTION_STRING is missing or empty! "
        "Falling back to an un-exported local console tracer to prevent container startup crash."
    )
    tracer = trace.get_tracer("etisalat.ai.gateway")
else:
    try:
        configure_azure_monitor(connection_string=AI_CONN_STR)
        tracer = trace.get_tracer("etisalat.ai.gateway")
        logger.info("🚀 OpenTelemetry Azure Monitor instrumentation initialized successfully.")
    except Exception as initialization_error:
        logger.error(f"❌ Failed to boot Azure Monitor OTel: {str(initialization_error)}")
        logger.warning("Falling back to dummy local tracer for application safety.")
        tracer = trace.get_tracer("etisalat.ai.gateway")

# Initialize Constants
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_URL")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_KNOWLEDGE_INDEX")

app = FastAPI(
    title="Etisalat Enterprise AI Gateway",
    description="Production-grade API exposing our Azure AI Search and GPT-4.1-mini RAG streaming pipeline.",
    version="1.1.0"
)

# AUTO-INSTRUMENT FASTAPI LIFECYCLE ROUTING
if AI_CONN_STR:
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("🟢 FastAPI lifecycle routing auto-instrumentation attached successfully.")
    except Exception as instrumentation_error:
        logger.error(f"⚠️ FastAPI Auto-instrumentation skipped: {str(instrumentation_error)}")

ai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT, 
    api_key=AZURE_OPENAI_KEY,                            
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

class QueryRequest(BaseModel):
    question: str = Field(..., example="What digital broadband services does Etisalat provide?")

# 4. Create the Core Chat Streaming Endpoint
@app.post("/api/v1/chat", summary="Query the Cloud Knowledge Base with Real-Time Streaming Chunks")
async def chat_endpoint(request: QueryRequest):
    # Establish parent span context framework
    master_span = trace.get_current_span()
    user_question = request.question
    logger.info(f"📥 Received inbound API inquiry: '{user_question}'")
    
    try:
        # Step A: Vectorize the live question
        with tracer.start_as_current_span("openai_embeddings_generation") as embedding_span:
            query_resp = ai_client.embeddings.create(
                input=[user_question], 
                model="text-embedding-3-small"
            )
            logger.info("📡 Generated embedding token vectors successfully via OpenAI.")
            question_vector = query_resp.data[0].embedding
        
        # Step B: Execute Cloud Vector Query
        vector_query = VectorizedQuery(
            vector=question_vector,
            k_nearest_neighbors=3,
            fields="content_vector"
        )
        
        with tracer.start_as_current_span("azure_ai_search_retrieval") as search_span:
            logger.info("🔍 Initiating Hybrid Search query with Semantic Reranking...")
            
            # Use fixed dictionary setup to safeguard against underlying SDK keyword parser anomalies
            search_args = {
                "search_text": user_question,
                "vector_queries": [vector_query],
                "top": 5,
                "select": ["content_text", "filename"],
                "query_type": "semantic",
                "semantic_configuration_name": "mySemanticConfig"
            }
            search_results = search_client.search(**search_args)

        with tracer.start_as_current_span("semantic_filtering_extraction") as filter_span:
            retrieved_contexts = []
            unique_source_files = set()
            row_count = 0
            skipped_count = 0

            for idx, doc in enumerate(search_results, start=1):
                reranker_score = doc.get("@search.rerankerScore")

                if reranker_score is not None and reranker_score < 2.0:
                    logger.info(f"⏩ Skipping low-relevance chunk (Score: {reranker_score:.2f}) from file: '{doc.get('filename')}'")
                    skipped_count += 1
                    continue
            
                row_count += 1
                text_chunk = doc["content_text"]
                source_file = doc.get("filename", "Unknown_Source_Document.txt")

                logger.info(f"   👉 [Hit #{row_count}] Found in File: '{source_file}'")
                unique_source_files.add(source_file)
                retrieved_contexts.append(f"--- [Source Reference Node #{idx} | File: {source_file}] ---\n{text_chunk}\n")

            filter_span.set_attribute("search.total_hits", row_count + skipped_count)
            filter_span.set_attribute("search.accepted_hits", row_count)

        # Fallback guard clause for empty contexts
        if not retrieved_contexts:
            logger.warning(f"⚠️ Zero matching nodes returned from database for query: '{user_question}'")
            def empty_generator():
                yield "data: " + json.dumps({"answer": "I cannot find this information in my corporate documents.", "sources": []}) + "\n\n"
            return StreamingResponse(empty_generator(), media_type="text/event-stream")

        full_grounding_context = "\n".join(retrieved_contexts)
        sources_list = list(unique_source_files)

        # Step C: System Prompt Engineering Setup
        system_instruction = (
            "You are an expert enterprise corporate assistant at Etisalat.\n"
            "Your task is to answer the user's question using ONLY the provided Source Reference Nodes.\n\n"
            "CRITICAL CITATION RULES:\n"
            "1. Every single factual statement, sentence, or claim you make MUST be directly followed by an inline numerical citation bracket matching the source number that provided the fact (e.g., [1] or [2]).\n"
            "2. If multiple sources support a claim, combine them (e.g., [1][3]).\n"
            "3. Do NOT make any general statements without an accompanying inline citation.\n"
            "4. If the provided context does not contain enough evidence to answer the question completely, explicitly state 'I do not possess the required data within my index files.' Do not extrapolate or hallucinate."
        )
        user_payload = f"Context from Live Azure Database:\n{full_grounding_context}\n\nQuestion: {user_question}"

        # 🚀 Use standard generator framework for streaming text tokens (FastAPI runs this in a background threadpool)
        def response_stream_generator():
            # Create a separate child trace span tracking LLM response duration metrics
            with tracer.start_as_current_span("llm_answer_generation") as llm_span:
                logger.info("🧠 Initializing continuous asynchronous pipeline chunk stream generation...")
                
                response_stream = ai_client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_payload}
                    ],
                    temperature=0.0,
                    stream=True # 💡 Activates Token Streaming channel
                )
                
                # Stream individual text chunks out as they arrive
                for chunk in response_stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        token = chunk.choices[0].delta.content
                        if token:
                            # Standard Server-Sent Events (SSE) network data mapping protocol payload layout
                            yield f"data: {json.dumps({'token': token})}\n\n"
                
                # Append final payload signature tracking data packet containing citations reference array
                yield f"data: {json.dumps({'done': True, 'sources': sources_list})}\n\n"
                logger.info("🟢 Token chunk stream tracking pipeline processing completed successfully.")

        return StreamingResponse(response_stream_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"❌ Critical Endpoint Crash Encountered: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health", summary="API Health Check")
async def health_check():
    return {"status": "healthy", "service": "enterprise-ai-core"}