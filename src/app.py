from httpcore import request
import os
from dotenv import load_dotenv
import logging

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

from fastapi import FastAPI, HTTPException
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

# 🛠️ EXTRACT AND CHECK THE CONNECTION STRING BEFORE INITIALIZATION
AI_CONN_STR = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

if not AI_CONN_STR:
    logger.warning(
        "⚠️ APPLICATIONINSIGHTS_CONNECTION_STRING is missing or empty! "
        "Falling back to an un-exported local console tracer to prevent container startup crash."
    )
    # Provide a dummy fallback tracer instance to keep the application code from breaking
    tracer = trace.get_tracer("etisalat.ai.gateway")
else:
    try:
        # Pass the verified key directly to guarantee instantiation clarity
        configure_azure_monitor(connection_string=AI_CONN_STR)
        tracer = trace.get_tracer("etisalat.ai.gateway")
        logger.info("🚀 OpenTelemetry Azure Monitor instrumentation initialized successfully.")
    except Exception as initialization_error:
        logger.error(f"❌ Failed to boot Azure Monitor OTel: {str(initialization_error)}")
        logger.warning("Falling back to dummy local tracer for application safety.")
        tracer = trace.get_tracer("etisalat.ai.gateway")

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

# 🛠️ AUTO-INSTRUMENT FASTAPI LIFECYCLE ROUTING
if AI_CONN_STR:
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("🟢 FastAPI lifecycle routing auto-instrumentation attached successfully.")
    except Exception as instrumentation_error:
        logger.error(f"⚠️ FastAPI Auto-instrumentation skipped: {str(instrumentation_error)}")
        

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
    question: str = Field(..., example="What digital broadband services does Etisalat provide?")

class QueryResponse(BaseModel):
    status: str
    query: str
    answer: str = Field(..., description="The factual answer containing footnote markdown anchors like [1].")
    sources: list[str] = Field(..., description="The unique filenames utilized to compile this answer context.")

# 4. Create the Core Chat Endpoint
@app.post("/api/v1/chat",response_model=QueryResponse, summary="Query the Cloud Knowledge Base with Citations")
async def chat_endpoint(request: QueryRequest):
    # 🛠️ Master Span to measure absolute processing time of the client request
    with tracer.start_as_current_span("rag_chat_pipeline") as master_span:
        try:
            user_question = request.question
            logger.info(f"📥 Received inbound API inquiry: '{user_question}'")
            master_span.set_attribute("rag.question", user_question)

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
            # 🛠️ Isolate cloud retrieval time to determine if Azure AI Search or Network is lagging
            with tracer.start_as_current_span("azure_ai_search_retrieval") as search_span:
                logger.info("🔍 Initiating Hybrid Search query with Semantic Reranking...")
                search_params = {
                    "search_text": user_question,
                    "vector_queries": [vector_query],
                    "top": 5,
                    "select": ["content_text", "filename"],
                    "query_type": "semantic",
                    "semantic_configuration_name": "mySemanticConfig"
                }
                search_results = search_client.search(**search_params)

            # 🛠️ Measure localized document processing and threshold execution speed
            with tracer.start_as_current_span("semantic_filtering_extraction") as filter_span:
                # Construct an ordered grounding payload array
                retrieved_contexts = []
                unique_source_files = set()
                # Count total number of retrieved nodes
                row_count = 0
                skipped_count = 0

                for idx, doc in enumerate(search_results, start=1):
                    # 🛠️ Catch Azure's semantic reranker score
                    reranker_score = doc.get("@search.rerankerScore")

                    # If semantic ranking is on, drop anything below our relevance threshold
                    if reranker_score is not None and reranker_score < 2.0:
                        logger.info(f"⏩ Skipping low-relevance chunk (Score: {reranker_score:.2f}) from file: '{doc.get('filename')}'")
                        skipped_count += 1
                        continue
                
                    row_count += 1
                    text_chunk = doc["content_text"]
                    source_file = doc.get("filename", "Unknown_Source_Document.txt")

                    # Print EXACTLY what text chunk came back from Azure AI Search
                    logger.info(f"   👉 [Hit #{row_count}] Found in File: '{source_file}'")
                    logger.info(f"      Content Preview: {text_chunk[:120]}...") # Logs first 120 chars

                    # Map structural reference keys
                    unique_source_files.add(source_file)
                    retrieved_contexts.append(f"--- [Source Reference Node #{idx} | File: {source_file}] ---\n{text_chunk}\n")
                    logger.info(f"📊 Extraction phase completed. Total raw chunks retrieved: {row_count}")


                 # Populate Span metadata attributes for telemetry reporting
                filter_span.set_attribute("search.total_hits", row_count + skipped_count)
                filter_span.set_attribute("search.accepted_hits", row_count)
                filter_span.set_attribute("search.filtered_noise_hits", skipped_count)

            # Move check and generation logic out of the retrieval loop context
            if not retrieved_contexts:
                logger.warning(f"⚠️ Zero matching nodes returned from database for query: '{user_question}'")
                return QueryResponse(
                    status="success",
                    query=user_question,
                        answer="I cannot find this information in my corporate documents.",
                        sources=[]
                    )
                

            # Combine matching document chunks into a unified string payload
            logger.info(f"🧠 Dispatching context engine payload to gpt-4.1-mini model execution...")
            full_grounding_context = "\n".join(retrieved_contexts)

            # Step C: Heavy-Duty Instruction Following System Prompt Engineering
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
            
            # 🛠️ Measure how many milliseconds the GPT generation deployment takes to respond
            with tracer.start_as_current_span("llm_answer_generation") as llm_span: 
                # Step D: Call live gpt-4.1-mini deployment
                chat_response = ai_client.chat.completions.create(
                    model="gpt-4.1-mini", 
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_payload}
                    ],
                    temperature=0.0 # Force determinism to eliminate creative guessing
                )
                final_answer = chat_response.choices[0].message.content
                llm_span.set_attribute("llm_input_tokens", chat_response.usage.prompt_tokens)
                llm_span.set_attribute("llm_output_tokens", chat_response.usage.completion_tokens)
                llm_span.set_attribute("llm_total_tokens", chat_response.usage.total_tokens)
                
            logger.info("🟢 Answer generated successfully by the LLM. Streaming payload response.")
            master_span.set_attribute("rag.result_status", "success")

            return QueryResponse(
                status="success",
                query=user_question,
                answer=final_answer,
                sources=list(unique_source_files)
            )

        except Exception as e:
            logger.error(f"❌ Critical Endpoint Crash Encountered: {str(e)}", exc_info=True)
            # Track failure details inside the OpenTelemetry span layout
            master_span.record_exception(e)
            master_span.set_status(trace.StatusCode.ERROR, description=str(e))
            raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# 5. Health Check Endpoint (Vital for enterprise monitoring and container readiness probes)
@app.get("/health", summary="API Health Check")
async def health_check():
    return {"status": "healthy", "service": "enterprise-ai-core"}