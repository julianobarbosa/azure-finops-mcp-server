# Documentation Index

Welcome to the Azure FinOps MCP Server documentation. This index provides a comprehensive overview of all available documentation for the project.

## Root Documents

### [Project README](../README.md)

Main project documentation including overview, features, installation instructions, and usage examples. Contains comprehensive information about the MCP server capabilities and integration with AI assistants like Claude Desktop.

### [Migration & Quick Start Guide](./quickstart.md)

Step-by-step guide for quickly setting up the Azure FinOps MCP Server using uv package manager. Ideal for new users wanting to get started quickly.

### [Setup Commands Reference](./setup-commands.md)

Complete reference of all setup commands needed to install, configure, and test the Azure FinOps MCP Server. Includes troubleshooting tips and configuration examples.

## Code Review Issues

Documentation of critical and high-priority issues identified during code review:

### [N+1 Query Pattern Issue](./issues/001-n1-query-pattern.md)

Critical performance issue where VM status checking makes individual API calls for each VM, creating significant performance bottlenecks.

### [Hardcoded Credentials Issue](./issues/002-hardcoded-credentials.md)

Critical security issue with Azure subscription IDs hardcoded in source code, requiring immediate remediation.

### [Sequential Processing Issue](./issues/003-sequential-processing.md)

High-priority performance issue where subscriptions are processed sequentially instead of in parallel, causing unnecessary delays.

### [Poor Testability Issue](./issues/004-poor-testability.md)

High-priority architectural issue with tight Azure SDK coupling preventing effective unit testing.

### [Monolithic Functions Issue](./issues/005-monolithic-functions.md)

High-priority maintainability issue with functions exceeding 160 lines and handling multiple responsibilities.

## API Documentation

### [API Reference](./api/reference.md) *(Coming Soon)*

Detailed documentation of all MCP tools and their parameters:
- `get_cost` - Azure cost analysis tool
- `run_finops_audit` - Comprehensive FinOps audit tool
- `get_budget_status` - Budget monitoring tool

### [Tool Examples](./api/examples.md) *(Coming Soon)*

Practical examples of using each tool with various parameters and common use cases.

## User Guides

### [Integration Guide](./guides/integration.md) *(Coming Soon)*

How to integrate the Azure FinOps MCP Server with different AI assistants:
- Claude Desktop configuration
- Amazon Q CLI setup
- Custom client integration

### [FinOps Best Practices](./guides/finops-practices.md) *(Coming Soon)*

Best practices for using the server to optimize Azure costs and identify waste.

## Development Documentation

### [Architecture Overview](./architecture.md)

Comprehensive technical architecture of the Azure FinOps MCP Server including:
- Component architecture diagrams
- Data flow sequences
- Security architecture
- Performance optimization strategies
- Scalability considerations
- Future enhancements

### [Contributing Guide](./development/contributing.md) *(Coming Soon)*

Guidelines for contributing to the project:
- Development setup
- Code standards
- Pull request process
- Testing requirements

### [Testing Guide](./development/testing.md) *(Coming Soon)*

Comprehensive guide to testing the Azure FinOps MCP Server:
- Unit testing approach
- Integration testing with Azure
- Mock data strategies
- Performance testing

## Configuration

### [Azure IAM Requirements](./configuration/azure-iam.md) *(Coming Soon)*

Detailed Azure IAM permissions required for the server to function properly with different features.

### [Environment Variables](./configuration/environment.md) *(Coming Soon)*

Complete list of supported environment variables and configuration options.

## Troubleshooting

### [Common Issues](./troubleshooting/common-issues.md) *(Coming Soon)*

Solutions to frequently encountered problems:
- Authentication errors
- Permission issues
- Performance problems
- Configuration mistakes

### [Debug Guide](./troubleshooting/debug.md) *(Coming Soon)*

How to debug issues with the MCP server including logging configuration and diagnostic tools.

## Release Notes

### [Changelog](./releases/changelog.md) *(Coming Soon)*

Version history and release notes for all versions of the Azure FinOps MCP Server.

### [Migration Guides](./releases/migration.md) *(Coming Soon)*

Guides for migrating between major versions of the server.

---

## Quick Links

- [GitHub Repository](https://github.com/julianobarbosa/azure-finops-mcp-server)
- [PyPI Package](https://pypi.org/project/azure-finops-mcp-server/)
- [Issue Tracker](https://github.com/julianobarbosa/azure-finops-mcp-server/issues)
- [Azure CLI Documentation](https://docs.microsoft.com/en-us/cli/azure/)
- [MCP Protocol Specification](https://modelcontextprotocol.io)

---

*Last updated: 2025-09-08*