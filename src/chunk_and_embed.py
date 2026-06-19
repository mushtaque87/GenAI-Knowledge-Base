import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

# 1. Initialize your Azure OpenAI Client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),                            
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
)

def read_and_chunk_document(file_path: str) -> list[str]:
    """
    Reads a local text file and safely partitions it into overlapping semantic chunks.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Could not locate the target file at: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
        
    # Configure the structural boundaries for our chunks
    # 1000 characters is roughly 150-200 words. 
    # 150 characters of overlap ensures sentences near boundaries are preserved intact.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len
    )
    
    chunks = text_splitter.split_text(raw_text)
    print(f"Chunks generated from file: {chunks}\n\n")
    return chunks

def generate_vectors_for_chunks(chunks: list[str]) -> list[dict]:
    """
    Batches document chunks and transmits them to Azure OpenAI to produce vector matrices.
    """
    processed_payloads = []
    
    print(f"Total chunks generated from file: {len(chunks)}")
    print("Initiating batch embedding requests to cloud infrastructure...\n")
    
    # We can pass an entire list of strings directly to the API to minimize HTTP overhead
    response = client.embeddings.create(
        input=chunks,
        model=os.getenv("AZURE_OPENAI_MODEL", "text-embedding-3-small")
    )
    
    # Map the resulting vectors back to their respective text chunks structurally
    for index, chunk_text in enumerate(chunks):
        vector = response.data[index].embedding
        
        # Build an enterprise data envelope pattern
        chunk_envelope = {
            "id": f"chunk_row_{index}",
            "content_text": chunk_text,
            "content_vector": vector,
            "vector_dimensions": len(vector)
        }
        processed_payloads.append(chunk_envelope)
        
    return processed_payloads

# --- Execution Block ---
if __name__ == "__main__":
    target_file = os.path.join(script_dir, "sample_corp_doc.txt")
    
    try:
        # Step A: Slice the data locally using natural linguistic rules
        document_chunks = read_and_chunk_document(target_file)
        
        # Step B: Ship the text array to Azure to get our mathematical embeddings
        embedded_dataset = generate_vectors_for_chunks(document_chunks)
        
        # Step C: Inspect our new data schema
        first_chunk = embedded_dataset[0]
        print("=== Structural Validation Complete ===")
        print(f"Envelope Key ID: {first_chunk['id']}")
        print(f"Vector Space Matrix Dimensions: {first_chunk['vector_dimensions']}")
        print(f"Text Snippet Preview (First 80 chars): {first_chunk['content_text'][:80]}...")
        print(f"Vector Matrix Preview (First 3 entries): {first_chunk['content_vector'][:3]}")
        
    except Exception as e:
        print(f"Execution failed standard run parameters: {str(e)}")