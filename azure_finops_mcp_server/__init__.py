"""Azure FinOps MCP Server - Cost optimization and audit for Azure resources."""

__version__ = "2.0.0"
__author__ = "Azure FinOps Team"
__email__ = "finops@azure.com"

from .main import run_server

__all__ = ["run_server", "__version__"]