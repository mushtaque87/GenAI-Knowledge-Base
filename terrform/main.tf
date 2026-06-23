# 1. Define the Required Cloud Providers
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# 2. Reference Your Existing Azure AI Search Resource (Saves Costs / Retains Free Tier)
data "azurerm_search_service" "existing_search" {
  name                = "aisearch-enterprise-mushtaque"
  resource_group_name = "rg-enterprise-ai-crawl"
}

# 3. Create Your Production Dedicated Resource Group
resource "azurerm_resource_group" "rg" {
  name     = "rg-enterprise-ai-prod"
  location = "eastus2" 
}

# 4. Provision the Azure OpenAI Cognitive Account (The Compute Engine)
resource "azurerm_cognitive_account" "openai" {
  name                = "aoai-solution-architect-prod-mushtaque"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"
}

# 5. Automatically Deploy the text-embedding-3-small Model Snapshot
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  
  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  scale {
    type = "Standard"
  }
}

# 6. Automatically Deploy Your Active working gpt-4.1-mini Model
resource "azurerm_cognitive_deployment" "chat" {
  name                 = "gpt-4.1-mini" # Matches your environment variable string exactly
  cognitive_account_id = azurerm_cognitive_account.openai.id
  
  model {
    format  = "OpenAI"
    name    = "gpt-4.1-mini"  # Corrected to target your supported 4.1 iteration profile
    version = "2025-04-14"    # Matches your environment's deployment schema target snapshot
  }

  scale {
    type = "Standard"
  }
}


output "openai_endpoint" {
  value       = azurerm_cognitive_account.openai.endpoint
  description = "The dynamically generated endpoint for Azure OpenAI"
}

output "openai_primary_key" {
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
  description = "The primary access key for the new OpenAI instance"
}