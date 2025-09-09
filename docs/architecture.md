# Azure FinOps MCP Server Architecture

## Overview

The Azure FinOps MCP Server is a Model Context Protocol (MCP) server that provides Azure cost management and optimization capabilities to AI assistants. It follows a modular, layered architecture designed for security, performance, and maintainability.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        A[Claude Desktop]
        B[Amazon Q CLI]
        C[Other MCP Clients]
    end

    subgraph "MCP Protocol Layer"
        D[FastMCP Server<br/>main.py]
        D1[get_cost Tool]
        D2[run_finops_audit Tool]
        D3[get_budget_status Tool]
    end

    subgraph "Business Logic Layer"
        E[Configuration<br/>config.py]
        F[Error Handling<br/>error_handling.py]
        G[Concurrent Processing<br/>concurrent_util.py]
        H[Optimized Cost<br/>optimized_cost.py]
        I[Utilities<br/>util.py]
    end

    subgraph "Azure Integration Layer"
        J[Azure CLI Credential]
        K[Azure SDK]
        L[Cost Management API]
        M[Compute API]
        N[Network API]
        O[Consumption API]
    end

    subgraph "Azure Cloud"
        P[Azure Subscriptions]
        Q[Cost Data]
        R[Resource Data]
        S[Budget Data]
    end

    A --> D
    B --> D
    C --> D

    D --> D1
    D --> D2
    D --> D3

    D1 --> E
    D1 --> F
    D1 --> G
    D1 --> H

    D2 --> E
    D2 --> F
    D2 --> I

    D3 --> E
    D3 --> F
    D3 --> I

    E --> J
    F --> K
    G --> K
    H --> K
    I --> K

    K --> L
    K --> M
    K --> N
    K --> O

    L --> Q
    M --> R
    N --> R
    O --> S

    P --> Q
    P --> R
    P --> S
```

## Component Architecture

```
azure-finops-mcp-server/
├── azure_finops_mcp_server/
│   ├── main.py                    # MCP server entry point and tool definitions
│   ├── config.py                  # Configuration management
│   └── helpers/
│       ├── concurrent_util.py     # Parallel processing utilities
│       ├── error_handling.py      # Error handling framework
│       ├── optimized_cost.py      # Optimized cost processing
│       └── util.py                 # Azure operations utilities
├── docs/                           # Documentation
├── tests/                          # Test suite
└── .env.example                    # Configuration template
```

## Layer Descriptions

### 1. Client Layer
- **Purpose**: AI assistants and MCP-compatible clients
- **Components**: Claude Desktop, Amazon Q CLI, custom clients
- **Protocol**: MCP over stdio/HTTP

### 2. MCP Protocol Layer
- **Purpose**: Expose Azure FinOps capabilities as MCP tools
- **Components**:
  - FastMCP server framework
  - Tool definitions (get_cost, run_finops_audit, get_budget_status)
- **Responsibilities**:
  - Protocol handling
  - Request/response formatting
  - Tool registration

### 3. Business Logic Layer
- **Purpose**: Core application logic and processing
- **Components**:
  - **Configuration** (`config.py`): Environment-based settings
  - **Error Handling** (`error_handling.py`): Consistent error management
  - **Concurrent Processing** (`concurrent_util.py`): Parallel operations
  - **Optimized Cost** (`optimized_cost.py`): Performance-optimized cost queries
  - **Utilities** (`util.py`): Azure resource operations
- **Responsibilities**:
  - Business rules implementation
  - Data processing and aggregation
  - Performance optimization
  - Error recovery

### 4. Azure Integration Layer
- **Purpose**: Interface with Azure services
- **Components**:
  - Azure CLI Credential for authentication
  - Azure SDK clients
  - Service-specific APIs
- **Responsibilities**:
  - Authentication management
  - API call abstraction
  - Response parsing

### 5. Azure Cloud Layer
- **Purpose**: Azure cloud resources and data
- **Components**:
  - Multiple Azure subscriptions
  - Cost and usage data
  - Resource metadata
  - Budget configurations

## Data Flow

### Cost Analysis Flow
```mermaid
sequenceDiagram
    participant Client
    participant MCP
    participant Config
    participant CostProc as Cost Processor
    participant Azure

    Client->>MCP: get_cost(params)
    MCP->>Config: Load configuration
    Config-->>MCP: Config settings
    MCP->>CostProc: Process request

    loop For each subscription (parallel)
        CostProc->>Azure: Query cost data
        Azure-->>CostProc: Cost results
    end

    CostProc->>CostProc: Aggregate results
    CostProc-->>MCP: Formatted data
    MCP-->>Client: Cost report
```

### FinOps Audit Flow
```mermaid
sequenceDiagram
    participant Client
    participant MCP
    participant Audit as Audit Engine
    participant Azure

    Client->>MCP: run_finops_audit(params)
    MCP->>Audit: Initialize audit

    par VM Audit
        Audit->>Azure: List VMs
        Azure-->>Audit: VM data
        Audit->>Audit: Find stopped VMs
    and Disk Audit
        Audit->>Azure: List disks
        Azure-->>Audit: Disk data
        Audit->>Audit: Find orphaned disks
    and IP Audit
        Audit->>Azure: List public IPs
        Azure-->>Audit: IP data
        Audit->>Audit: Find unassociated IPs
    end

    Audit->>Audit: Calculate waste
    Audit-->>MCP: Audit report
    MCP-->>Client: FinOps recommendations
```

## Key Design Decisions

### 1. Security First
- **Local Execution**: Server runs on user's machine
- **Credential Management**: Uses Azure CLI credentials, never stores secrets
- **Read-Only Operations**: Only performs read operations on Azure resources

### 2. Performance Optimization
- **Parallel Processing**: Concurrent subscription processing (5 workers default)
- **Caching**: In-memory cache with configurable TTL
- **Batch Operations**: Minimize API calls through batching

### 3. Error Resilience
- **Comprehensive Error Handling**: Typed exceptions for different failure modes
- **Retry Logic**: Automatic retry with exponential backoff
- **Graceful Degradation**: Partial results on partial failures

### 4. Configuration Management
- **Environment Variables**: All settings externalized
- **Validation**: Configuration validated on load
- **Multi-Environment**: Support for different Azure clouds

### 5. Extensibility
- **Modular Design**: Easy to add new tools and operations
- **Plugin Architecture**: New audit checks can be added independently
- **Standard Interfaces**: Consistent patterns for new components

## Scalability Considerations

### Current Capabilities
- Handles 10+ subscriptions concurrently
- Processes 1000s of resources per audit
- Sub-second response for cached data

### Scaling Strategies
1. **Horizontal**: Increase worker count for more parallelism
2. **Caching**: Redis/external cache for multi-instance deployment
3. **Async Operations**: Full async/await for better concurrency
4. **Resource Pooling**: Connection pool for Azure clients

## Security Architecture

### Authentication Flow
```mermaid
graph LR
    A[User] --> B[Azure CLI]
    B --> C[Azure AD]
    C --> D[Access Token]
    D --> E[MCP Server]
    E --> F[Azure APIs]

    style D fill:#f9f,stroke:#333,stroke-width:2px
```

### Security Layers
1. **Authentication**: Azure CLI/DefaultAzureCredential
2. **Authorization**: Azure RBAC (Reader/Cost Management Reader)
3. **Data Protection**: HTTPS for all API calls
4. **Audit Trail**: Comprehensive logging
5. **Error Sanitization**: Safe error messages to users

## Monitoring & Observability

### Logging Strategy
- **Structured Logging**: JSON-formatted logs
- **Log Levels**: Configurable (DEBUG, INFO, WARNING, ERROR)
- **Context Propagation**: Request IDs for tracing

### Metrics
- API call counts and latencies
- Cache hit/miss rates
- Error rates by type
- Resource processing times

## Future Architecture Enhancements

### Planned Improvements
1. **Service Mesh**: Microservices architecture for scale
2. **Event-Driven**: Pub/sub for real-time cost alerts
3. **ML Integration**: Cost prediction and anomaly detection
4. **Multi-Cloud**: Support for AWS and GCP

### Extension Points
- Custom audit rules engine
- Plugin system for third-party integrations
- Webhook notifications
- Export adapters (CSV, Excel, BI tools)

## Development Workflow

```mermaid
graph LR
    A[Local Development] --> B[Unit Tests]
    B --> C[Integration Tests]
    C --> D[PR Review]
    D --> E[CI/CD Pipeline]
    E --> F[PyPI Release]
    F --> G[Client Update]
```

## Deployment Architecture

### Local Deployment (Current)
```
┌─────────────────┐
│  AI Assistant   │
│ (Claude Desktop)│
└────────┬────────┘
         │ stdio
┌────────▼────────┐
│  MCP Server     │
│   (Python)      │
└────────┬────────┘
         │ HTTPS
┌────────▼────────┐
│   Azure APIs    │
└─────────────────┘
```

### Future Cloud Deployment Option
```
┌─────────────────┐
│  AI Assistants  │
└────────┬────────┘
         │ HTTPS
┌────────▼────────┐
│  API Gateway    │
└────────┬────────┘
         │
┌────────▼────────┐
│  MCP Servers    │
│   (Container)   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Azure APIs    │
└─────────────────┘
```

---

*Last Updated: 2025-01-09*
