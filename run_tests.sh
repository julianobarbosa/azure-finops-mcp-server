#!/bin/bash

echo "========================================"
echo "Azure FinOps MCP Server Test Suite"
echo "========================================"
echo ""

# Activate virtual environment
echo "🔧 Setting up environment..."
source .venv/bin/activate

# Run compatibility tests
echo ""
echo "📋 Running MCP compatibility tests..."
echo "----------------------------------------"
python test_mcp_compatibility.py
COMPAT_RESULT=$?

# Run integration tests
echo ""
echo "🧪 Running integration tests..."
echo "----------------------------------------"
python test_integration.py
INTEGRATION_RESULT=$?

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"

if [ $COMPAT_RESULT -eq 0 ] && [ $INTEGRATION_RESULT -eq 0 ]; then
    echo "✅ All tests passed successfully!"
    echo ""
    echo "The server is ready to use. To execute:"
    echo "  1. Direct execution: .venv/bin/azure-finops-mcp-server"
    echo "  2. With Claude Desktop: Add to claude_desktop_config.json"
    echo "  3. Test tools: .venv/bin/python -c 'from azure_finops_mcp_server.main import get_cost'"
    exit 0
else
    echo "❌ Some tests failed"
    [ $COMPAT_RESULT -ne 0 ] && echo "  - Compatibility tests failed"
    [ $INTEGRATION_RESULT -ne 0 ] && echo "  - Integration tests failed"
    exit 1
fi