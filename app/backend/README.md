# Banking Assistant Copilot Backend

A FastAPI-based multi-agent orchestration service that powers the banking assistant frontend. This microservice uses Azure OpenAI and the Agent Framework to provide intelligent banking support through specialized agents.

## 🏗️ Architecture

This backend implements a **supervisor agent pattern** where:
- **Supervisor Agent**: Routes user requests to specialized domain agents
- **Account Agent**: Handles account balance, payment methods, and beneficiaries
- **Transaction Agent**: Manages banking movements and payment history
- **Payment Agent**: Processes payment requests and bill uploads

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Azure OpenAI account with API access
- Git with LFS support

### Backend Setup

#### 1. Navigate to the copilot directory

```powershell
cd app/copilot
```

#### 2. Configure Git LFS (if needed)

```powershell
$env:GIT_LFS_SKIP_SMUDGE="1"
```

#### 3. Install dependencies using uv

```powershell
# Install uv if you don't have it
pip install uv

# Create a virtual environment
uv venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install all dependencies
uv sync --active --prerelease=allow 
```

#### 5. Configure environment variables

Update the `.env.dev` file with your Azure OpenAI connection details:

```env
# Azure OpenAI Settings
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5.4

# Azure services (if needed)
AZURE_DOCUMENT_INTELLIGENCE_SERVICE=your-doc-intel-service
AZURE_STORAGE_ACCOUNT=your-storage-account

# MCP Servers (if running)
ACCOUNT_MCP_URL=http://localhost:8070
TRANSACTION_MCP_URL=http://localhost:8071
PAYMENT_MCP_URL=http://localhost:8072
```

#### 6. Run the development server

**Option A: Using uvicorn directly**
```powershell
# Set PROFILE env variable to "dev". This will make the app load .env.dev file instead of .env.
$env:PROFILE="dev"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Option B: Using VS Code debugger**
1. Navigate to **Run & Debug** in VS Code
2. Select **"FastAPI: DEV Debug Copilot App"** from the dropdown
3. Press F5 or click the green play button

The API will be available at:
- **API**: http://localhost:8000

---

## 🎨 Frontend Setup

### 1. Navigate to the frontend directory

```powershell
cd app/frontend
```

### 2. Install dependencies

```powershell
npm install
```

### 3. Start the development server

```powershell
npm run dev
```
The frontend will be available at:
- **Frontend**: http://localhost:8081

---

## 📁 Project Structure

```
app/copilot/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── chat_routers.py     # Chat endpoints with streaming support
│   │   └── content_routers.py  # File upload/download endpoints
│   ├── agents/
│   │   ├── azure_chat/
│   │   │   ├── supervisor_agent.py      # Main routing agent
│   │   │   ├── account_agent.py         # Account management
│   │   │   ├── transaction_agent.py     # Transaction history
│   │   │   └── payment_agent.py         # Payment processing
│   │   └── foundry/            # Alternative foundry-based agents
│   ├── config/
│   │   ├── container_azure_chat.py      # DI container
│   │   └── observability.py             # Logging & monitoring
│   ├── models/
│   │   └── chat.py             # Pydantic models
│   └── helpers/
│       └── utils.py            # Utility functions
├── pyproject.toml              # Project dependencies
├── uv.lock                     # Lock file for reproducible builds
└── .env.dev                    # Environment configuration
```

---

## 🌊 Streaming Support

The backend supports **real-time streaming** responses for a better user experience:

- Enable streaming via the settings panel in the UI
- Toggle "Stream chat completion responses" checkbox
- Responses appear word-by-word in real-time

---
