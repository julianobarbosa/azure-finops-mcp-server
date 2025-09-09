#!/bin/bash
# Remove old AWS package directory to fix setuptools conflict

echo "Removing old AWS package directory..."
rm -rf aws_finops_mcp_server/

echo "Cleanup complete!"
echo "Now you can run: uv pip install -e ."
