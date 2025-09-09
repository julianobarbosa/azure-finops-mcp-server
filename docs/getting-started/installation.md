# Installation Guide

## System Requirements

### Prerequisites
- Python 3.10 or higher
- Azure CLI installed and configured
- Active Azure subscription(s)
- Appropriate Azure RBAC permissions

### Operating System Support
- ✅ Windows 10/11
- ✅ macOS 11+
- ✅ Linux (Ubuntu 20.04+, RHEL 8+, etc.)

## Installation Methods

### 1. Install from PyPI (Recommended)

```bash
pip install azure-finops-mcp-server
```

For a specific version:
```bash
pip install azure-finops-mcp-server==2.0.0
```

### 2. Install from Source

```bash
# Clone the repository
git clone https://github.com/julianobarbosa/azure-finops-mcp-server.git
cd azure-finops-mcp-server

# Install in development mode
pip install -e .
```

### 3. Install with Docker

```bash
# Pull the Docker image
docker pull ghcr.io/julianobarbosa/azure-finops-mcp-server:latest

# Run the container
docker run -it --rm \
  -v ~/.azure:/root/.azure \
  ghcr.io/julianobarbosa/azure-finops-mcp-server:latest
```

## Azure Authentication

### Using Azure CLI (Recommended)

```bash
# Login to Azure
az login

# List available subscriptions
az account list --output table

# Set default subscription (optional)
az account set --subscription "Your Subscription Name"
```

### Using Service Principal

Create a service principal:
```bash
az ad sp create-for-rbac \
  --name "azure-finops-mcp-server" \
  --role "Cost Management Reader" \
  --scopes /subscriptions/{subscription-id}
```

Set environment variables:
```bash
export AZURE_CLIENT_ID="<client-id>"
export AZURE_CLIENT_SECRET="<client-secret>"
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_SUBSCRIPTION_ID="<subscription-id>"
```

### Using Managed Identity (Azure VMs)

If running on an Azure VM with managed identity:
```bash
# No additional configuration needed
# The server will automatically use the VM's managed identity
```

## Verify Installation

### Check Version
```bash
azure-finops-mcp-server --version
```

### Test Connection
```bash
# Run a simple test command
azure-finops-mcp-server test-connection
```

### Verify Permissions
```bash
# Check if you have the required permissions
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

## Required Azure Permissions

### Minimum Required Roles
- **Cost Management Reader** - For cost analysis
- **Reader** - For resource enumeration

### Recommended Roles for Full Functionality
- **Cost Management Contributor** - For budget management
- **Monitoring Reader** - For metrics access

### Custom Role Definition
```json
{
  "Name": "FinOps MCP Server",
  "Description": "Custom role for Azure FinOps MCP Server",
  "Actions": [
    "Microsoft.Consumption/*/read",
    "Microsoft.CostManagement/*/read",
    "Microsoft.Compute/virtualMachines/read",
    "Microsoft.Compute/virtualMachines/instanceView/read",
    "Microsoft.Compute/disks/read",
    "Microsoft.Network/publicIPAddresses/read",
    "Microsoft.Resources/subscriptions/read",
    "Microsoft.Resources/subscriptions/resourceGroups/read"
  ],
  "AssignableScopes": [
    "/subscriptions/{subscription-id}"
  ]
}
```

## Troubleshooting Installation

### Common Issues

#### 1. Python Version Error
```
ERROR: Package requires Python >=3.10
```
**Solution**: Upgrade Python to 3.10 or higher

#### 2. Azure CLI Not Found
```
ERROR: Azure CLI is not installed
```
**Solution**: Install Azure CLI from [Microsoft's official site](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)

#### 3. Permission Denied
```
ERROR: AuthorizationFailed
```
**Solution**: Ensure you have the required Azure RBAC roles

#### 4. SSL Certificate Error
```
ERROR: SSL: CERTIFICATE_VERIFY_FAILED
```
**Solution**: Update certificates or set:
```bash
export AZURE_CLI_DISABLE_CONNECTION_VERIFICATION=1
```

## Next Steps

After successful installation:
1. [Configure the server](configuration.md)
2. [Follow the Quick Start guide](quickstart.md)
3. [Explore example usage](examples.md)