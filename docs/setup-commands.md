# Setup Commands for Azure FinOps MCP Server

Run these commands in your terminal:

## 1. Create Virtual Environment
```bash
uv venv
```

## 2. Activate Virtual Environment
```bash
source .venv/bin/activate
# On Windows: .venv\Scripts\activate
```

## 3. Install Dependencies
```bash
uv pip install -r requirements.txt
```

## 4. Install Package in Development Mode
```bash
uv pip install -e .
```

## 5. Check Azure CLI Installation
```bash
which az
az --version
```

If Azure CLI is not installed, get it from:
https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

## 6. Login to Azure
```bash
az login
```

## 7. List Your Subscriptions
```bash
az account list --output table
```

## 8. Test the MCP Server
```bash
python -m azure_finops_mcp_server.main
```

You should see output like:
```
Starting FastMCP Azure FinOps server...
```

Press Ctrl+C to stop.

## 9. Run Compatibility Test
```bash
python test_mcp_compatibility.py
```

## 10. Configure Claude Desktop

Add this to your Claude Desktop config file:

**Location:**
- macOS/Linux: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "azure_finops": {
      "command": "/full/path/to/your/project/.venv/bin/python",
      "args": ["-m", "azure_finops_mcp_server.main"]
    }
  }
}
```

Replace `/full/path/to/your/project` with your actual project path.

To get your current path:
```bash
pwd
```

## 11. Restart Claude Desktop

After updating the config, completely restart Claude Desktop.

## 12. Test in Claude Desktop

Try these queries:
- "Get Azure costs for all my subscriptions for the last 7 days"
- "Run a FinOps audit on my Production subscription in eastus"
- "Show me my Azure budget status"

## Troubleshooting

### If uv pip install fails:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Try upgrading pip first
uv pip install --upgrade pip

# Then retry
uv pip install -r requirements.txt
```

### If Azure login fails:
```bash
# Clear Azure CLI cache
az account clear

# Login with specific tenant
az login --tenant YOUR_TENANT_ID
```

### If MCP server doesn't start:
```bash
# Check Python path
which python

# Verify imports work
python -c "from azure.identity import AzureCliCredential; print('Azure SDK OK')"
python -c "from mcp.server.fastmcp import FastMCP; print('MCP OK')"
```
