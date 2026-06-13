import os
import numpy as np
import faiss
from dotenv import load_dotenv
from openai import AzureOpenAI
from chunk_and_embed import read_and_chunk_document, generate_vectors_for_chunks

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

# 1. Initialize your Azure OpenAI Client (to convert our search question to a vector)
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),  
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),                            
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
)

# --- Prep the Local Data ---
target_file = os.path.join(script_dir, "sample_corp_doc.txt")
# Reuse your previous script logic to chunk and embed the text
document_chunks = read_and_chunk_document(target_file)
embedded_dataset = generate_vectors_for_chunks(document_chunks)

# 2. Extract raw vector arrays and transform them into a standard float32 NumPy matrix
# FAISS requires a continuous mathematical matrix layout to perform calculations
raw_vectors = [item["content_vector"] for item in embedded_dataset]
vectors_matrix = np.array(raw_vectors).astype('float32')

# 3. Provision the local FAISS Index 
# IndexFlatIP uses "Inner Product" (Cosine Similarity) to find matching vectors
dimension = 1536
local_index = faiss.IndexFlatIP(dimension)
local_index.add(vectors_matrix) # Upload the chunk matrices into local memory

print(f"--> Successfully loaded {local_index.ntotal} vectors into the local database.\n")

# --- Simulate an Enterprise User Search Query ---
user_query = "Who is the CEO of Etisalat and when was it founded?"
print(f"User Question: '{user_query}'")

# 4. Turn the user's live query into a matching vector space
query_response = client.embeddings.create(
    input=[user_query],
    model=os.getenv("AZURE_OPENAI_MODEL", "text-embedding-3-small")
)
query_vector = np.array([query_response.data[0].embedding]).astype('float32')

# 5. Search the Database
# local_index.search returns the distance score and the index position of the closest match
k_nearest_neighbors = 1 
scores, indices = local_index.search(query_vector, k_nearest_neighbors)

# 6. Extract and Output the Winning Chunk
winning_index = indices[0][0]
winning_score = scores[0][0]
matched_document_chunk = embedded_dataset[winning_index]["content_text"]

print("\n=== Local Database Search Results ===")
print(f"Match Confidence Score (Cosine Similarity): {winning_score:.4f}")
print(f"Closest Database Row ID: chunk_row_{winning_index}")
print(f"Retrieved Context block text:\n{matched_document_chunk}")