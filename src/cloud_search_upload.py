import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
# Reuse our prior text processing script logic
from chunk_and_embed import read_and_chunk_document, generate_vectors_for_chunks

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

# 1. Access Credentials for Cloud Search Engine
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_URL")   # Paste your Search URL
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")                                   # Paste your Admin Key
INDEX_NAME = os.getenv("AZURE_KNOWLEDGE_INDEX")

# 2. Extract and Prepare the Real Text Data Payload
target_file = os.path.join(script_dir, "sample_corp_doc.txt")
document_chunks = read_and_chunk_document(target_file)
embedded_dataset = generate_vectors_for_chunks(document_chunks)

# 3. Connect to the Index Management Client
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY))

# 4. Define the Vector Search Parameters
# We use HNSW (Hierarchical Navigable Small World) - the enterprise standard for fast vector lookups
vector_search_config = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="myHnswConfig")],
    profiles=[VectorSearchProfile(name="myVectorProfile", algorithm_configuration_name="myHnswConfig")]
)

# 5. Design the Database Table Schema Layout
fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content_text", type=SearchFieldDataType.String),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536, # Must match text-embedding-3-small
        vector_search_profile_name="myVectorProfile"
    )
]

index_definition = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search_config)

# 6. Instantiate the Schema inside Azure Cloud
print(f"Creating search index '{INDEX_NAME}' in Azure...")
index_client.create_or_update_index(index_definition)

# 7. Upload our Data Envelopes into the Cloud Database Index
print("Uploading vectorized data packets to Azure Cloud Index...")
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=AzureKeyCredential(SEARCH_KEY))

# Re-map our dictionary key names slightly to perfectly line up with our schema field names
cloud_upload_payload = []
for record in embedded_dataset:
    cloud_upload_payload.append({
        "id": record["id"],
        "content_text": record["content_text"],
        "content_vector": record["content_vector"]
    })

results = search_client.upload_documents(documents=cloud_upload_payload)
print(f"Successfully uploaded {len(results)} chunks to Azure AI Search Cloud!")