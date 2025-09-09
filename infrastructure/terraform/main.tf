terraform {
  required_version = ">= 1.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  
  backend "azurerm" {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "tfstateazurefinops"
    container_name       = "tfstate"
    key                  = "azure-finops-mcp.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default = {
    Project     = "Azure-FinOps-MCP"
    ManagedBy   = "Terraform"
    Environment = "Production"
  }
}

# Resource Group for FinOps resources
resource "azurerm_resource_group" "finops" {
  name     = "rg-finops-mcp-${var.environment}"
  location = var.location
  tags     = var.tags
}

# Storage Account for metrics and logs
resource "azurerm_storage_account" "metrics" {
  name                     = "stfinopsmetrics${var.environment}"
  resource_group_name      = azurerm_resource_group.finops.name
  location                 = azurerm_resource_group.finops.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  blob_properties {
    versioning_enabled = true
    
    delete_retention_policy {
      days = 7
    }
  }
  
  tags = var.tags
}

# Container for metrics storage
resource "azurerm_storage_container" "metrics" {
  name                  = "metrics"
  storage_account_name  = azurerm_storage_account.metrics.name
  container_access_type = "private"
}

# Container for audit logs
resource "azurerm_storage_container" "audit" {
  name                  = "audit-logs"
  storage_account_name  = azurerm_storage_account.metrics.name
  container_access_type = "private"
}

# Key Vault for secure configuration
resource "azurerm_key_vault" "config" {
  name                = "kv-finops-${var.environment}"
  location            = azurerm_resource_group.finops.location
  resource_group_name = azurerm_resource_group.finops.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
  
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id
    
    secret_permissions = [
      "Get",
      "List",
      "Set",
      "Delete",
      "Purge"
    ]
  }
  
  tags = var.tags
}

# Application Insights for monitoring
resource "azurerm_application_insights" "monitoring" {
  name                = "ai-finops-mcp-${var.environment}"
  location            = azurerm_resource_group.finops.location
  resource_group_name = azurerm_resource_group.finops.name
  application_type    = "other"
  retention_in_days   = 90
  
  tags = var.tags
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "law-finops-mcp-${var.environment}"
  location            = azurerm_resource_group.finops.location
  resource_group_name = azurerm_resource_group.finops.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  
  tags = var.tags
}

# Service Principal for MCP Server
resource "azurerm_user_assigned_identity" "mcp_server" {
  name                = "id-finops-mcp-${var.environment}"
  resource_group_name = azurerm_resource_group.finops.name
  location            = azurerm_resource_group.finops.location
  tags                = var.tags
}

# Role assignments for the Service Principal
resource "azurerm_role_assignment" "cost_reader" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Cost Management Reader"
  principal_id         = azurerm_user_assigned_identity.mcp_server.principal_id
}

resource "azurerm_role_assignment" "reader" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.mcp_server.principal_id
}

# Data source for current Azure context
data "azurerm_client_config" "current" {}

# Outputs
output "resource_group_name" {
  value = azurerm_resource_group.finops.name
}

output "storage_account_name" {
  value = azurerm_storage_account.metrics.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.config.vault_uri
}

output "app_insights_instrumentation_key" {
  value     = azurerm_application_insights.monitoring.instrumentation_key
  sensitive = true
}

output "mcp_server_identity_id" {
  value = azurerm_user_assigned_identity.mcp_server.id
}

output "mcp_server_client_id" {
  value = azurerm_user_assigned_identity.mcp_server.client_id
}