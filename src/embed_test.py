import os
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load variables from .env file
load_dotenv()

# 1. Initialize the client targeting your specific Azure infrastructure instance
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
)

# 2. Define the payload text you want to turn into math
sample_text = "Etisalat provides high-scale digital architecture frameworks across telecom sectors."

print(f"Sending text to Azure OpenAI: '{sample_text}'...\n")

# 3. Call the embeddings interface using your explicit deployment name
response = client.embeddings.create(
    input=[sample_text],
    model=os.getenv("AZURE_OPENAI_MODEL", "text-embedding-3-small")
)

# 4. Extract the high-dimensional vector array response
vector_data = response.data[0].embedding

# 5. Output structural validation metrics
print("--- Vector Generation Successful ---")
print(f"Vector Dimensions (Length): {len(vector_data)}")
print(f"Sample of the first 5 vector values: {vector_data[:5]}")