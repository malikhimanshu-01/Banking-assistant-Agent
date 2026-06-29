---
name: local-dev
description: This skill provides instructions for setting up a local development environment for the banking assistant project. It covers installing dependencies, configuring environment variables, and running the application locally.
license: MIT
---

### Prerequisites

Before starting backend development, complete these setup steps:

#### 1. Provision Azure Resources

Deploy the required Azure infrastructure using Azure Developer CLI:

```bash
azd provision
```

This command will:
- Create Azure OpenAI service with GPT-5.4 deployment
- Set up Azure Document Intelligence for invoice scanning
- Configure Azure Storage Account for document storage
- Deploy Application Insights for monitoring
- Create Container Apps environment (if deploying)

**Note:** You'll be prompted to authenticate and select an Azure subscription. The provisioning process may take 10-15 minutes.

> **Skip this step if you already ran `azd up`** when you first downloaded the repository. The `azd up` command performs both provisioning and deployment, so your Azure resources are already created.

#### 2. Configure Environment Variables

check for `app/backend/.env.dev` file. sometimes the file_search tool may not find the file as it doesn't index dotfiles. make sure to check the file system directly.
if not present try to create it your local development environment file:
- copy the example env file to .env.dev
```bash
cd app/backend
cp .env.dev.example .env.dev
```
- run `azd env get-values` to see all provisioned resource values
- Edit `app/backend/.env.dev` and populate value using azd env get-values results.

---

### Start-up instructions

### Components and test to run
1. Business API Services: Account, Transaction, and Payment services that the agents interact with. They both contain REST API and MCP endpoints.
2. Chatkit Server (Primary): Main backend application exposing the chat protocol and hosting agents
3. Smoke Test: A curl command to test the chat endpoint with a sample request.
4. Banking Web: Banking web application that connects to the backend and provides a user interface.

You need to start each component separately on different terminal windows.
- Make sure to set the required environment variables for each component as described in the instructions. 
- The instructions are for shell/bash, so adjust accordingly if you are using a Windows command or PowerShell.


### Business API Development (Python)

#### Account Service
run in a shell terminal as foreground process so you can see logs streaming. use terminal console to stream log, don't forward them to filesystem.
```bash
cd app/business-api/python/account
uv sync                                    # Install dependencies
PROFILE=dev uv run python main.py          # Run with dev profile
```

#### Payment Service
run in a shell terminal as foreground process so you can see logs streaming. use terminal console to stream log, don't forward them to filesystem.
```bash
cd app/business-api/python/payment
uv sync                                    # Install dependencies
PROFILE=dev TRANSACTIONS_API_SERVER_URL=http://localhost:8071 \
  uv run python main.py
```

#### Transaction Service
run in a shell terminal as foreground process so you can see logs streaming. use terminal console to stream log, don't forward them to filesystem.
```bash
cd app/business-api/python/transaction
uv sync                                    # Install dependencies
PROFILE=dev uv run python main.py          # Run with dev profile
```


#### ChatKit Server (Primary)
run in a shell terminal as foreground process so you can see logs streaming. use terminal console to stream log, don't forward them to filesystem.

```bash
cd app/backend
uv sync                                          # Install dependencies
PROFILE=dev ENABLE_SENSITIVE_DATA=true \
  uv run uvicorn app.main_chatkit_server:app \
  --reload --port 8080
```


### Testing the Backend Server

Once the ChatKit or Custom Chat Server is running, you can test it using curl with:

```bash
curl -X POST http://localhost:8080/chatkit \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

the test_request.json file is in .github/skills/local-dev/assets/test_request.json


The response will stream back as Server-Sent Events, showing the agent's processing steps and final response in real-time.

---

### Frontend Development (Banking Web)
Before starting frontend development, ensure the Testing backend server step is successful and the backend server is running.
```bash
cd app/frontend/banking-web
npm install               # Install dependencies
npm run dev               # Start dev server
```
Open http://localhost:5173 in your browser to access the banking web application.

### Debugging with VSCode
The project includes VSCode launch configurations for debugging. Open the Debug panel (Ctrl+Shift+D) and select from:

#### Backend Debug Configurations
- **DEV - Chatkit Backend App** - Debug the ChatKit server (recommended)
  - Runs: `app.main_chatkit_server:app` on port 8080
  - Environment: `PROFILE=dev`, `ENABLE_SENSITIVE_DATA=true`
  

#### Business API Debug Configurations (Python)
- **Account MCP: DEV** - Debug account service
- **Transaction MCP: DEV** - Debug transaction service
- **Payment MCP: DEV** - Debug payment service with transaction API URL