#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Load local .env variables if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "🚀 Spinning up cloud infrastructure with Terraform..."
terraform -chdir=terrform apply -auto-approve -lock=false


echo "🔍 Extracting dynamic keys and endpoints from Terraform state..."
OPENAI_ENDPOINT=$(terraform -chdir=terrform output -raw openai_endpoint)
OPENAI_KEY=$(terraform -chdir=terrform output -raw openai_primary_key)

echo "🛑 Cleaning up older container instances if they exist..."
docker rm -f rag-service-prod 2>/dev/null || true

# 🛠️ FIXED: Rebuild the local Docker image to bake in your new Python logs and code changes!
echo "📦 Rebuilding application Docker image..."
docker build --no-cache -t etisalat-ai-gateway:v1 .

echo "🐳 Booting Docker Container with new infrastructure configurations..."
docker run -d \
  -p 8000:8000 \
  --name rag-service-prod \
  -e AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT" \
  -e AZURE_OPENAI_API_KEY="$OPENAI_KEY" \
  -e AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4.1-mini" \
  -e AZURE_SEARCH_URL="$AZURE_SEARCH_URL" \
  -e AZURE_SEARCH_KEY="$AZURE_SEARCH_KEY" \
  -e AZURE_KNOWLEDGE_INDEX="$AZURE_KNOWLEDGE_INDEX" \
  -e APPLICATIONINSIGHTS_CONNECTION_STRING="$APPLICATIONINSIGHTS_CONNECTION_STRING" \
  etisalat-ai-gateway:v1

echo "🟢 Stack completely updated and running at http://localhost:8000"