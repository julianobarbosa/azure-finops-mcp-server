# Azure FinOps MCP Server - Quick Start with uv

## Installation Steps with uv

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create and activate virtual environment
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
# Install all Azure dependencies
uv pip install -r requirements.txt

# Or install the package in development mode
uv pip install -e .
```

### 4. Login to Azure
```bash
az login
az account list  # View available subscriptions
```

### 5. Test the installation
```bash
# Run the MCP server directly
python -m azure_finops_mcp_server.main

# Or if installed as a package
azure-finops-mcp-server
```

## Configure Claude Desktop

Update your Claude Desktop configuration:

**macOS/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "azure_finops": {
      "command": "azure-finops-mcp-server",
      "args": []
    }
  }
}
```

If using a virtual environment, use the full path:
```json
{
  "mcpServers": {
    "azure_finops": {
      "command": "/path/to/project/.venv/bin/azure-finops-mcp-server",
      "args": []
    }
  }
}
```

## Testing the MCP Server

Once configured, restart Claude Desktop and test with:

1. **Cost Query:**
   ```
   "Get Azure costs for all my subscriptions for the last 7 days"
   ```

2. **Audit Query:**
   ```
   "Run a FinOps audit on my Production subscription in eastus region"
   ```

## Troubleshooting

### If the command is not found:
```bash
# Check if it's in your virtual environment
which azure-finops-mcp-server

# If using uv, ensure the venv is activated
source .venv/bin/activate
```

### If Azure authentication fails:
```bash
# Re-authenticate with Azure
az login --tenant YOUR_TENANT_ID

# Set default subscription
az account set --subscription "Subscription Name"
```

## Development with uv

### Update dependencies
```bash
uv pip install --upgrade azure-identity azure-mgmt-costmanagement
```

### Add new dependencies
```bash
uv pip install some-new-package
uv pip freeze > requirements.txt
```

### Run tests
```bash
python test_mcp_compatibility.py
```

## Performance Note

`uv` is significantly faster than `pip` for installing packages. When working with Azure SDK dependencies, you'll notice:
- ~10x faster installation speed
- Better dependency resolution
- Automatic caching of packages

## Next Steps

1. Review the [README.md](README.md) for detailed usage examples
2. Check Azure RBAC permissions for your identity
3. Start querying your Azure costs and resources through Claude!