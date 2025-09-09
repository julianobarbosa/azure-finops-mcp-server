#!/bin/bash
# Manual PyPI publishing script

echo "🚀 Azure FinOps MCP Server - PyPI Publishing"
echo "============================================"
echo ""

# Check if dist directory exists
if [ ! -d "dist" ]; then
    echo "❌ Error: dist/ directory not found. Run 'python setup.py sdist bdist_wheel' first."
    exit 1
fi

# Check for credentials
echo "📋 Pre-flight checks:"
echo "1. Ensure you have PyPI credentials configured"
echo "2. Run: pip install twine (if not installed)"
echo "3. Configure ~/.pypirc or use twine with --username"
echo ""

read -p "Do you want to upload to Test PyPI first? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 Uploading to Test PyPI..."
    twine upload --repository testpypi dist/*
    echo ""
    echo "✅ Test upload complete!"
    echo "🔗 View at: https://test.pypi.org/project/azure-finops-mcp-server/"
    echo ""
    read -p "Continue with production PyPI upload? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "⏹️  Skipping production upload."
        exit 0
    fi
fi

echo "📦 Uploading to PyPI..."
twine upload dist/*

echo ""
echo "✅ Upload complete!"
echo "🔗 View at: https://pypi.org/project/azure-finops-mcp-server/"
echo ""
echo "Install with: pip install azure-finops-mcp-server==2.0.0"
