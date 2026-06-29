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
    VectorSearchProfile,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField as AzureSemanticField
)
# Reuse our prior text processing script logic
from chunk_and_embed import read_and_chunk_document, generate_vectors_for_chunks

# Resolve directory paths relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load variables from root .env file
load_dotenv(os.path.join(script_dir, "../.env"))

# 1. Access Credentials for Cloud Search Engine
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_URL")   # Paste your Search URL
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")         # Paste your Admin Key
INDEX_NAME = os.getenv("AZURE_KNOWLEDGE_INDEX")

# 2. Track, Extract, and Prepare Multiple Data Files Natively
target_files = [
    os.path.join(script_dir, "sample_corp_doc.txt"),
    os.path.join(script_dir, "sample_tesla_doc.txt")  # 🛠️ Added multi-source support
]

# 3. Connect to the Index Management Client
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY))

# 4. Define the Vector Search Parameters
vector_search_config = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="myHnswConfig")],
    profiles=[VectorSearchProfile(name="myVectorProfile", algorithm_configuration_name="myHnswConfig")]
)

# 5. Design the Database Table Schema Layout with Semantic Prioritization
semantic_config = SemanticSearch(
    configurations=[
        SemanticConfiguration(
            name="mySemanticConfig",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=AzureSemanticField(field_name="filename"),
                content_fields=[AzureSemanticField(field_name="content_text")]
            )
        )
    ]
)

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content_text", type=SearchFieldDataType.String),
    SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536, # Must match text-embedding-3-small
        vector_search_profile_name="myVectorProfile"
    )
]

index_definition = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search_config, semantic_search=semantic_config)

# 6. Instantiate the Schema inside Azure Cloud (Drop old layout to apply updates smoothly)
print(f"Checking for old index '{INDEX_NAME}' to drop...")
try:
    index_client.delete_index(INDEX_NAME)
    print(f"🗑️ Successfully deleted old index '{INDEX_NAME}' to clear schema.")
except Exception:
    print("No existing index found to delete. Proceeding...")

print(f"Creating fresh search index '{INDEX_NAME}' with 'filename' schema in Azure...")
index_client.create_or_update_index(index_definition)

# 7. Collect Vectors and Upload Unified Batches to Azure Cloud Index
cloud_upload_payload = []

for target_file in target_files:
    if not os.path.exists(target_file):
        print(f"⚠️ Warning: File not found at {target_file}. Skipping execution for this target.")
        continue
        
    print(f"📦 Processing, chunking, and embedding: {os.path.basename(target_file)}")
    document_chunks = read_and_chunk_document(target_file)
    embedded_dataset = generate_vectors_for_chunks(document_chunks)
    
    source_file_basename = os.path.basename(target_file)
    print(f"   Generated {len(embedded_dataset)} chunks for '{source_file_basename}'")
    
    # Map matching dictionary metadata references for this document
    for record in embedded_dataset:
        cloud_upload_payload.append({
            "id": record["id"],
            "content_text": record["content_text"],
            "content_vector": record["content_vector"],
            "filename": source_file_basename  # Enforced lowercase key match
        })

print(f"📡 Uploading {len(cloud_upload_payload)} vectorized packets across all sources to Azure...")
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=AzureKeyCredential(SEARCH_KEY))
results = search_client.upload_documents(documents=cloud_upload_payload)
print(f"🟢 Successfully uploaded {len(results)} chunks to Azure AI Search Cloud!")