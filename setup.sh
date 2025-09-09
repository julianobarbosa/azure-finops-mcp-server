#!/bin/bash

echo "=========================================="
echo "Azure FinOps MCP Server Setup Script"
echo "=========================================="

# Step 1: Create virtual environment
echo ""
echo "Step 1: Creating virtual environment with uv..."
uv venv

# Step 2: Activate virtual environment
echo ""
echo "Step 2: Activating virtual environment..."
echo "Please run: source .venv/bin/activate"
echo "(On Windows: .venv\\Scripts\\activate)"

# Step 3: Install dependencies
echo ""
echo "Step 3: Installing Azure dependencies..."
source .venv/bin/activate && uv pip install -r requirements.txt

# Step 4: Install package in development mode
echo ""
echo "Step 4: Installing package in development mode..."
source .venv/bin/activate && uv pip install -e .

# Step 5: Check Azure CLI
echo ""
echo "Step 5: Checking Azure CLI..."
which az
if [ $? -eq 0 ]; then
    echo "✅ Azure CLI is installed"
    echo ""
    echo "Please login to Azure if not already logged in:"
    echo "  az login"
    echo ""
    echo "List your subscriptions:"
    echo "  az account list"
else
    echo "⚠️  Azure CLI not found. Please install it from:"
    echo "  https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
fi

# Step 6: Test the MCP server
echo ""
echo "Step 6: Testing MCP server..."
echo "To test the server, run:"
echo "  python -m azure_finops_mcp_server.main"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Login to Azure (if needed):"
echo "   az login"
echo ""
echo "3. Configure Claude Desktop by adding to:"
echo "   ~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo '   {
     "mcpServers": {
       "azure_finops": {
         "command": "'$(pwd)'/.venv/bin/python",
         "args": ["-m", "azure_finops_mcp_server.main"]
       }
     }
   }'
echo ""
echo "4. Restart Claude Desktop"
echo ""
echo "5. Test with queries like:"
echo '   "Get Azure costs for all my subscriptions for the last 7 days"'
echo '   "Run a FinOps audit on my Production subscription in eastus"'
