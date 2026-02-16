## Technical Stack

### Backend Technologies

#### Core Framework
- **Python 3.11+**: Primary programming language
- **FastAPI 0.116.1**: Modern web framework for building APIs with automatic OpenAPI documentation
- **Uvicorn 0.35.0**: Lightning-fast ASGI server implementation

#### AI & Agent Framework
- **Microsoft Agent Framework (MAF) 1.0.0b260130**: 
  - `agent-framework-core`: Core agent orchestration capabilities
  - `agent-framework-azure-ai`: Azure AI integration for agents
  - `agent-framework-chatkit`: ChatKit protocol implementation for agent-to-chat communication
- **OpenAI ChatKit 1.4.1**: Client-side chat protocol implementation
- **Azure OpenAI (GPT-4.1)**: Large language model for agent intelligence

#### Azure Services Integration
- **Azure Identity 1.24.0**: Authentication and authorization with Azure services
- **Azure Storage Blob 12.26.0**: Document and file storage
- **Azure Document Intelligence 1.0.1**: OCR and invoice/receipt data extraction
- **Azure Monitor OpenTelemetry**: Observability and telemetry

#### Additional Backend Tools
- **dependency-injector 4.48.1**: Dependency injection container for clean architecture
- **pytest 8.4.1**: Testing framework with async support

### Frontend Technologies

#### Banking Web (Primary Frontend)
- **React 18.2+**: Modern UI library
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Next-generation frontend build tool
- **shadcn/ui**: Re-usable component library built on:
  - **Radix UI**: Accessible component primitives
  - **Tailwind CSS**: Utility-first CSS framework
  - **class-variance-authority**: Type-safe component variants
- **TanStack Query 5.56.2**: Powerful data synchronization
- **Lucide React 0.462.0**: Beautiful icon library
- **React Hook Form & Zod**: Form handling and validation

#### Simple Chat (Alternative Frontend)
- **React 18.2**: UI library
- **Fluent UI**: Microsoft's design system
- **Azure MSAL**: Microsoft Authentication Library for browser authentication
- **React Router DOM**: Client-side routing

### Infrastructure & DevOps

#### Cloud Platform
- **Azure Container Apps**: Serverless container hosting platform
- **Azure AI Foundry**: AI model deployment and management
- **Azure Cognitive Services**: AI capabilities (Document Intelligence)
- **Azure Monitor & Application Insights**: Observability and monitoring

#### Infrastructure as Code
- **Bicep**: Azure's domain-specific language for declarative infrastructure
- **Azure Developer CLI (azd)**: Automated deployment and provisioning
- **Docker**: Containerization with multi-stage builds

#### Build Tools
- **uv**: Fast Python package installer and resolver
- **npm/pnpm**: Package management (simple-chat, banking-web)

### Communication Protocols

- **Model Context Protocol (MCP)**: Exposing business APIs as agent tools via [fastmcp](https://gofastmcp.com/)
- **OpenAI ChatKit Protocol**: Extended implementation supporting:
  - Server-Sent Events (SSE) streaming
  - Client-managed widgets
  - Multi-agent workflows
  - Human-in-the-loop (HITL) patterns

---

## Repository Structure

### Root Level Files

```
📄 azure.yaml              # Azure Developer CLI configuration defining all services
📄 README.md               # Project overview and getting started guide
📄 CHANGELOG.md            # Version history and release notes
📄 CONTRIBUTING.md         # Contribution guidelines
📄 LICENSE.md              # MIT License
📄 SECURITY.md             # Security policy and reporting guidelines
📄 CODEOWNERS              # GitHub code owners configuration
```

### `/app` - Application Source Code

Main application directory containing all backend, frontend, and business API components.

#### `/app/backend` - Agent Backend Service
The core multi-agent orchestration service that exposes chat API endpoints.

```
📁 app/backend/
├── 📄 pyproject.toml                    # Python project dependencies and metadata
├── 📄 Dockerfile                        # Container image definition
├── 📄 README.md                         # Backend-specific documentation
├── 📄 applicationinsights.json          # Application Insights configuration
│
├── 📁 app/                              # Main application package
│   ├── 📄 main_chatkit_server.py        # Entry point for ChatKit server mode
│   ├── 📄 logging-default.yaml          # Logging configuration
│   │
│   ├── 📁 agents/                       # Agent implementations
│   │   │                                # Two implementation versions available:
│   │   ├── 📁 azure_chat/               # Azure OpenAI Chat-based agents
│   │   │   │                            #   - Uses Azure OpenAI Chat client based agents
│   │   │   │                            #   - Agents are optimized for ChatKit protocol implementations
│   │   │   │                            #   - Includes simple/ subfolder with basic handoff agents
│   │   │   │                            #   - Files: account_agent.py, payment_agent.py, 
│   │   │   │                            #     transaction_agent.py, handoff_orchestrator.py
│   │   └── 📁 foundry_v2/               # Azure AI Foundry v2 agents
│   │       │                            #   - Uses Azure AI Foundry client (AzureAIClient) based agents
│   │       │                            #   - Agents are optimized for ChatKit protocol implementations
│   │       │                            #   - Files: account_agent.py, payment_agent.py,
│   │       │                            #     transaction_agent.py, handoff_orchestrator.py
│   │
│   ├── 📁 common/                       # Shared utilities and base classes
│   │
│   ├── 📁 config/                       # Configuration management
│   │   ├── 📄 azure_credential.py       # Azure authentication credential provider
│   │   │                                #   - Provides environment-aware credential selection
│   │   │                                #   - Dev: Azure CLI credentials for local development
│   │   │                                #   - Prod: Managed Identity for Azure-hosted environments
│   │   │                                #   - Supports both sync and async credential instances
│   │   ├── 📄 settings.py               # Application settings and environment variable management
│   │   │                                #   - Pydantic-based settings with validation
│   │   │                                #   - Loads from environment variables and .env files
│   │   │                                #   - Azure service configurations (OpenAI, Storage, Document Intelligence)
│   │   │                                #   - MCP server URLs for business API integration
│   │   │                                #   - Profile-based configuration (dev/prod)
│   │   ├── 📄 logging.py                # Logging configuration and OpenTelemetry setup
│   │   │                                #   - Profile-based logging configuration (logging-{profile}.yaml)
│   │   │                                #   - OpenTelemetry integration for distributed tracing
│   │   │                                #   - Application Insights log export
│   │   │                                #   - Structured logging with custom formatters
│   │   ├── 📄 container_azure_chat.py   # DI container for Azure OpenAI Chat agents
│   │   │                                #   - Dependency injection using dependency-injector
│   │   │                                #   - Configures Azure OpenAI Chat client instances
│   │   │                                #   - Wires agents with Azure services (Blob Storage, Document Intelligence)
│   │   │                                #   - Supports both simple handoff and ChatKit protocol agents
│   │   └── 📄 container_foundry_v2.py   # DI container for Azure AI Foundry v2 agents
│   │       │                            #   - Alternative configuration for Azure AI Foundry deployments
│   │       │                            #   - Uses AzureAIClient for agent framework integration
│   │       │                            #   - Provides same agent wiring with Foundry-specific clients
│   │
│   ├── 📁 helpers/                      # Azure service proxies and utilities
│   │   │                                #   - Simplifies interaction with Azure services (blob, cosmosdb, other Azure AI services)
│   │
│   ├── 📁 models/                       # Data models and schemas
│   ├── 📁 routers/                      # FastAPI route handlers
│   └── 📁 tools/                        # Agent tools and plugins
│       └── 📄 invoice_scanner_plugin.py # Document Intelligence integration
│
└── 📁 tests/                            # Unit and integration tests
    └── 📄 test_account_agent_chatkit.py # Agent testing with ChatKit
```

#### `/app/business-api` - Business Domain Services

Microservices exposing business logic as REST APIs and MCP tools.

```
📁 business-api/
├── 📁 java/                             # Java implementations (alternative)
│   ├── 📁 account/                      # Java account service
│   ├── 📁 payment/                      # Java payment service
│   └── 📁 transactions-history/         # Java transaction service
│
└── 📁 python/                           # Python implementations (primary)
    ├── 📄 README.md                     # Business API documentation
    ├── 📁 account/                      # Account management service
    ├── 📁 payment/                      # Payment processing service
    └── 📁 transaction/                  # Transaction history service
```

**Key Responsibilities:**
- Domain-specific business logic
- RESTful API endpoints
- MCP tool exposure for agent consumption
- Mock data generation for demo scenarios
- Integration with backend data stores

#### `/app/frontend` - User Interface Applications

Two frontend implementations providing different UX approaches.

##### `/app/frontend/banking-web` - Primary Modern UI
```
📁 banking-web/
├── 📄 package.json                      # Node.js dependencies
├── 📄 bun.lockb                         # Bun lock file
├── 📄 vite.config.ts                    # Vite build configuration
├── 📄 tsconfig.json                     # TypeScript configuration
├── 📄 tailwind.config.ts                # Tailwind CSS configuration
├── 📄 components.json                   # shadcn/ui components config
├── 📄 Dockerfile                        # Container image definition
├── 📄 index.html                        # HTML entry point
│
├── 📁 src/                              # Source code
│   ├── 📁 components/                   # React components
│   ├── 📁 hooks/                        # Custom React hooks
│   ├── 📁 lib/                          # Utility libraries
│   ├── 📁 pages/                        # Page components
│   └── 📁 styles/                       # CSS/styling files
│
├── 📁 public/                           # Static assets
└── 📁 nginx/                            # Nginx configuration for production
```

**Features:**
- Modern banking UI with shadcn/ui components
- Reusable chat widget component
- Image upload support for invoices/receipts
- Responsive design with Tailwind CSS
- Type-safe with TypeScript

##### `/app/frontend/simple-chat` - Alternative Fluent UI
```
📁 simple-chat/
├── 📄 package.json                      # Node.js dependencies
├── 📄 vite.config.ts                    # Vite configuration
├── 📄 tsconfig.json                     # TypeScript configuration
├── 📄 Dockerfile                        # Container image definition
├── 📄 Dockerfile-aks                    # AKS-specific Dockerfile
│
├── 📁 src/                              # Source code
│   ├── 📁 components/                   # Fluent UI components
│   ├── 📁 api/                          # API client implementations
│   └── 📁 pages/                        # Application pages
│
├── 📁 public/                           # Static assets
├── 📁 nginx/                            # Nginx server configuration
└── 📁 manifests/                        # Kubernetes manifests
```

**Features:**
- Fluent UI-based interface
- Azure MSAL authentication
- Simplified chat experience
- Kubernetes deployment ready

### `/data` - Sample Data & Assets

Contains sample invoices, receipts, and banking data for demonstration purposes.

```
📁 data/
├── 📁 invoices/                         # Sample invoice PDFs/images
├── 📁 receipts/                         # Sample receipt images
└── 📁 transactions/                     # Mock transaction data
```

### `/docs` - Documentation

Comprehensive technical and user documentation.

```
📁 docs/
├── 📄 technical-architecture.md         # Detailed architecture documentation
├── 📄 chat-server-protocol.md           # ChatKit protocol implementation details
├── 📄 deployment-guide.md               # Step-by-step deployment instructions
├── 📄 client-managed-widgets.md         # Client-side widget documentation
├── 📄 server-managed-widgets.md         # Server-side widget documentation
├── 📄 faq.md                            # Frequently asked questions
├── 📄 troubleshooting.md                # Common issues and solutions
│
├── 📁 assets/                           # Documentation images and diagrams

```

### `/infra` - Infrastructure as Code

Bicep templates for Azure resource provisioning.

```
📁 infra/
├── 📄 main.bicep                        # Main infrastructure orchestration
├── 📄 main.parameters.json              # Environment-specific parameters
│
├── 📁 app/                              # Application-specific resources
│   ├── 📄 account.bicep                 # Account service infrastructure
│   ├── 📄 backend.bicep                 # Backend service infrastructure
│   ├── 📄 payment.bicep                 # Payment service infrastructure
│   ├── 📄 transaction.bicep             # Transaction service infrastructure
│   └── 📄 web.bicep                     # Web frontend infrastructure
│
└── 📁 shared/                           # Shared infrastructure components
    ├── 📄 abbreviations.json            # Azure resource naming conventions
    ├── 📄 backend-dashboard.bicep       # Application Insights dashboard
    │
    ├── 📁 ai/                           # AI service infrastructure
    │   ├── 📄 cognitiveservices.bicep   # Cognitive Services setup
    │   ├── 📄 foundry.bicep             # AI Foundry hub/project setup
    │   └── 📄 foundry-model-deployment.bicep # Model deployment configs
    │
    ├── 📁 host/                         # Container hosting infrastructure
    │   ├── 📄 container-app.bicep       # Individual container app definition
    │   ├── 📄 container-apps.bicep      # Multiple container apps
    │   ├── 📄 container-app-upsert.bicep # Container app update logic
    │   ├── 📄 container-apps-environment.bicep # Container Apps environment
    │   └── 📄 container-registry.bicep  # Azure Container Registry
    │
    ├── 📁 monitor/                      # Monitoring and observability
    │   └── 📄 applicationinsights-dashboard.bicep # Monitoring dashboards
    │
    ├── 📁 security/                     # Security and identity
    │   └── [Key Vault, Managed Identity configs]
    │
    └── 📁 storage/                      # Storage resources
        └── [Blob Storage, File Share configs]
```

**Key Infrastructure Components:**
- **Container Apps Environment**: Serverless container hosting
- **Azure AI Foundry**: GPT-4.1 model deployment
- **Cognitive Services**: Document Intelligence for OCR
- **Application Insights**: Distributed tracing and monitoring
- **Container Registry**: Docker image storage
- **Managed Identity**: Secure service-to-service authentication


---

## Deployment Model

### Container-Based Architecture

All services run as containers on Azure Container Apps:
- **Backend**: Agent orchestration service (Python/FastAPI)
- **Account API**: Account management microservice
- **Payment API**: Payment processing with Document Intelligence
- **Transaction API**: Transaction history service
- **Web**: Frontend application (nginx serving React app)

### Infrastructure Provisioning

```bash
# Single command deployment
azd up
```

This command:
1. Creates Azure resource group
2. Provisions all infrastructure via Bicep
3. Builds Docker images
4. Pushes images to Azure Container Registry
5. Deploys containers to Container Apps
6. Configures networking and secrets

### Observability

- **Application Insights**: Request tracing, dependency tracking
- **OpenTelemetry**: Distributed tracing across agents and services

---