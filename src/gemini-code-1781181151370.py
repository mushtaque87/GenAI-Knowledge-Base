import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# 1. Initialize the Search Client 
# Note: For the 'Crawl' phase, you can swap credential with your API key string
service_endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
credential = DefaultAzureCredential() 

search_client = SearchClient(
    endpoint=service_endpoint,
    index_name=index_name,
    credential=credential
)

def perform_hybrid_search(user_query: str, query_vector: list[float]):
    """
    Executes a parallel text and vector search, merging results 
    using Reciprocal Rank Fusion (RRF) for maximum accuracy.
    """
    # Define the vector search component
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=5,
        fields="content_vector"
    )
    
    # Execute the hybrid search query
    results = search_client.search(
        search_text=user_query,        # The traditional keyword search element
        vector_queries=[vector_query], # The semantic vector search element
        top=3,                         # Return the absolute top 3 most relevant chunks
        select=["parent_document", "content_text"]
    )
    
    return results