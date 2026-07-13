```bash
#!/bin/bash
# Exit immediately if any command fails
set -e

# 1. Load configuration coordinates
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

DOCKER_IMAGE_NAME="mushtaque87/genai-knowledge-base:v1"

echo "🔐 Step 1: Re-authenticating local Azure CLI session..."
az account set --subscription "f4f93f61-a239-4940-9a03-1970339e53ad"

echo "📦 Step 2: Compiling cross-platform Image for Cloud Nodes (linux/amd64)..."
# Using buildx or direct platform flags targets Intel/AMD nodes on Azure natively
docker build --platform linux/amd64 --no-cache -t $DOCKER_IMAGE_NAME .

echo "🚀 Step 3: Pushing image registry layers to Docker Hub..."
docker push $DOCKER_IMAGE_NAME

echo "🏗️ Step 4: Applying Production Infrastructure state shifts via Terraform..."
cd terrform
terraform apply -auto-approve -lock=false

echo "🎯 Step 5: Refreshing live Container App deployment configuration..."
az containerapp update \
  --name genai-knowledge-base \
  --resource-group rg-enterprise-ai-prod \
  --image $DOCKER_IMAGE_NAME

echo "🟢 Production Application infrastructure successfully compiled, pushed, and deployed!"