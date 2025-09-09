#!/usr/bin/env python
"""Setup script for Azure FinOps MCP Server."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="azure-finops-mcp-server",
    version="2.0.0",
    author="Juliano Barbosa",
    author_email="juliano.barbosa@example.com",
    description="An MCP server for Azure FinOps to analyze costs and audit for savings",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/julianobarbosa/azure-finops-mcp-server",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "azure-identity",
        "azure-mgmt-costmanagement",
        "azure-mgmt-compute",
        "azure-mgmt-network",
        "azure-mgmt-consumption",
        "azure-mgmt-resource",
        "mcp",
    ],
    entry_points={
        "console_scripts": [
            "azure-finops-mcp-server=azure_finops_mcp_server.main:run_server",
        ],
    },
    keywords="azure finops cost cloud mcp",
)