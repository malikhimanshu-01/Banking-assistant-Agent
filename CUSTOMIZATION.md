## Development Workflows

### Prerequisites

Before starting backend development, complete these setup steps:

#### 1. Provision Azure Resources

Deploy the required Azure infrastructure using Azure Developer CLI:

```bash
azd provision
```

This command will:
- Create Azure OpenAI service with GPT-4.1 deployment
- Set up Azure Document Intelligence for invoice scanning
- Configure Azure Storage Account for document storage
- Deploy Application Insights for monitoring
- Create Container Apps environment (if deploying)

**Note:** You'll be prompted to authenticate and select an Azure subscription. The provisioning process may take 10-15 minutes.

> **Skip this step if you already ran `azd up`** when you first downloaded the repository. The `azd up` command performs both provisioning and deployment, so your Azure resources are already created.

#### 2. Configure Environment Variables

Create your local development environment file:

```bash
cd app/backend
cp .env.dev.example .env.dev
```

Edit `.env.dev` and populate with your Azure resource values from the provisioning output:

```dotenv
# Azure OpenAI Settings
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4.1

# Azure services
AZURE_DOCUMENT_INTELLIGENCE_SERVICE=your-doc-intel-service
AZURE_STORAGE_ACCOUNT=your-storage-account

# Observability
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...

# MCP Servers (Business API endpoints)
ACCOUNT_MCP_URL=http://localhost:8070
TRANSACTION_MCP_URL=http://localhost:8071/mcp
PAYMENT_MCP_URL=http://localhost:8072

# Agent types - options: azure_chat, foundry_v2
AGENTS_TYPE=azure_chat
```

**Tip:** After `azd provision`, run `azd env get-values` to see all provisioned resource values.

---

### Backend Development

#### ChatKit Server (Primary)
```bash
cd app/backend
uv sync                                          # Install dependencies
PROFILE=dev ENABLE_SENSITIVE_DATA=true \
  uv run uvicorn app.main_chatkit_server:app \
  --reload --port 8080
```

#### Custom Chat Server (Alternative)
```bash
cd app/backend
PROFILE=dev ENABLE_SENSITIVE_DATA=true \
  uv run uvicorn app.main_handoff:app \
  --reload --port 8080
```

**Environment Variables:**
- `PROFILE=dev` - Loads development configuration profile
- `ENABLE_SENSITIVE_DATA=true` - Enable sensitive data flag

### Business API Development (Python)

#### Account Service
```bash
cd app/business-api/python/account
uv sync                                    # Install dependencies
PROFILE=dev uv run python main.py          # Run with dev profile
```

#### Payment Service
```bash
cd app/business-api/python/payment
uv sync                                    # Install dependencies
PROFILE=dev TRANSACTIONS_API_SERVER_URL=http://localhost:8071 \
  uv run python main.py
```

#### Transaction Service
```bash
cd app/business-api/python/transaction
uv sync                                    # Install dependencies
PROFILE=dev uv run python main.py          # Run with dev profile
```

**Environment Variables:**
- `PROFILE=dev` - Loads development configuration profile
- `TRANSACTIONS_API_SERVER_URL` - Transaction service endpoint (for payment service)

### Frontend Development (Banking Web)
```bash
cd app/frontend/banking-web
npm install               # Install dependencies
npm run dev               # Start dev server
```

### Testing
```bash
cd app/backend
uv run pytest             # Run tests
```

### Debugging with VSCode

The project includes VSCode launch configurations for debugging. Open the Debug panel (Ctrl+Shift+D) and select from:

#### Backend Debug Configurations
- **DEV - Chatkit Backend App** - Debug the ChatKit server (recommended)
  - Runs: `app.main_chatkit_server:app` on port 8080
  - Environment: `PROFILE=dev`, `ENABLE_SENSITIVE_DATA=true`
  
- **DevUI** - Debug the development UI
  - Runs: `app/main_dev-ui.py`
  - Environment: `PROFILE=dev`

#### Business API Debug Configurations (Python)
- **Account MCP: DEV** - Debug account service
- **Transaction MCP: DEV** - Debug transaction service
- **Payment MCP: DEV** - Debug payment service with transaction API URL


**To debug:**
1. Set breakpoints in your code
2. Select the appropriate launch configuration from the Debug dropdown
3. Press F5 or click "Start Debugging"

---

## Development Tasks

This section provides step-by-step guidance for common development tasks in the banking assistant project.

### Task 1: Add a New Agent

Follow these steps to create and integrate a new agent into the system:

#### Step 1: Create the Agent File

Choose the implementation version you're working with:
- **Azure Chat version**: `app/backend/app/agents/azure_chat/your_agent_name.py`
- **Foundry v2 version**: `app/backend/app/agents/foundry_v2/your_agent_name.py`

Create a new Python file for your agent:

**For Azure Chat version:**
```python
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import Agent, MCPStreamableHTTPTool
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class YourAgentName:
    """
    Your agent description and purpose.
    """
    
    instructions = """
    You are a specialized agent for [specific domain].
    Your responsibilities include:
    - [Responsibility 1]
    - [Responsibility 2]
    - [Responsibility 3]
    
    """
    
    name = "YourAgentName"
    description = "This agent handles [brief description of agent's purpose]"
    
    def __init__(self, 
                 azure_chat_client: AzureOpenAIChatClient,
                 your_service_mcp_server_url: str):
        self.azure_chat_client = azure_chat_client
        self.your_service_mcp_server_url = your_service_mcp_server_url
    
    async def build_af_agent(self) -> Agent:
        """Build and return the Agent with dynamic context."""
        
        logger.info(f"Initializing MCP server tools for {self.name}")
        
        # Use async context manager for MCP tools
        async with MCPStreamableHTTPTool(
            name="Your Service MCP client",
            url=self.your_service_mcp_server_url
        ) as your_mcp_server:
            
            return Agent(
                client=self.azure_chat_client,
                instructions=YourAgentName.instructions,
                name=YourAgentName.name,
                tools=[your_mcp_server],
            )
```

**For Foundry v2 version:**
```python
from agent_framework.azure import AzureAIClient
from agent_framework import Agent, MCPStreamableHTTPTool
# Similar structure but use AzureAIClient instead of AzureOpenAIChatClient
```

#### Step 2: Define Agent Tools

If your agent needs custom tools, create them in `app/backend/app/tools/`:

```python
# app/backend/app/tools/your_tool.py
from typing import Annotated
from agent_framework._tools import tool
from pydantic import Field

class YourToolHelper:
    """Helper class for your custom tool functionality."""
    
    def __init__(self, dependency_service=None):
        """Initialize the tool helper with any required dependencies."""
        self.dependency_service = dependency_service
    
    @tool
    def your_custom_tool(
        self,
        param1: Annotated[str, Field(description="Description of param1")],
        param2: Annotated[int, Field(description="Description of param2")]
    ) -> Annotated[dict, Field(description="Returns a dictionary with processing results")]:
        """Tool description for the LLM. This docstring explains what the tool does."""
        # Implement tool logic
        result = {"status": "success", "data": f"Processed {param1} with {param2}"}
        return result
```

**Key Points:**
- Use `@tool` decorator from `agent_framework._tools`
- Use `Annotated[type, Field(description="...")]` for parameters and return type
- The docstring serves as the tool description for the LLM
- Wrap tools in a class for better organization and dependency injection

**Register the tool in the DI container:**

Register your tool helper in `app/backend/app/config/container_azure_chat.py` (or `container_foundry_v2.py`):

First, add the import at the top of the file:
```python
from app.tools.your_tool import YourToolHelper
```

Then, add the tool helper as a singleton in the Container class:
```python
class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""
    
    # ... existing providers ...
    
    # Your custom tool helper singleton
    your_tool_helper = providers.Singleton(
        YourToolHelper,
        dependency_service=some_dependency  # Pass any required dependencies
    )
```

Next, pass the tool helper to agents that need it. Update the agent provider:
```python
# In the Container class, update the agent that needs your tool
your_agent = providers.Factory(
    YourAgent,
    azure_chat_client=_azure_chat_client,
    your_service_mcp_server_url=f"{settings.YOUR_SERVICE_MCP_URL}/mcp",
    your_tool_helper=your_tool_helper  # Inject the tool helper
)
```

Finally, update your agent class to receive and use the tool:

```python
# In your_agent.py
class YourAgent:
    def __init__(self, 
                 azure_chat_client: AzureOpenAIChatClient,
                 your_service_mcp_server_url: str,
                 your_tool_helper: YourToolHelper):  # Add tool helper parameter
        self.azure_chat_client = azure_chat_client
        self.your_service_mcp_server_url = your_service_mcp_server_url
        self.your_tool_helper = your_tool_helper  # Store reference
    
    async def build_af_agent(self) -> Agent:
        # ... MCP tool initialization ...
        
        return Agent(
            client=self.azure_chat_client,
            instructions=YourAgent.instructions,
            name=YourAgent.name,
            tools=[
                your_mcp_server,
                self.your_tool_helper.your_custom_tool  # Add tool method to tools list
            ],
        )
```

#### Step 3: Register MCP Tools (if using Business API)

If your agent needs to call business APIs via MCP:

1. Ensure the business API service exposes MCP tools
2. Update `app/backend/app/config/settings.py` to include the MCP server URL:

```python
# In settings.py
YOUR_SERVICE_MCP_SERVER_URL: str = Field(
    default="http://localhost:8081/mcp",
    description="Your service MCP server URL"
)
```

3. Load MCP tools in your agent initialization

#### Step 4: Update the Dependency Injection Container

**For Azure Chat version**, edit `app/backend/app/config/container_azure_chat.py`:

First, add the import at the top of the file:
```python
from app.agents.azure_chat.your_agent_name import YourAgentName
```

Then, add the agent factory in the container class:
```python
# Inside the Container class
your_agent_name = providers.Factory(
    YourAgentName,
    azure_chat_client=_azure_chat_client,
    your_service_mcp_server_url=f"{settings.YOUR_SERVICE_MCP_URL}/mcp"
)
```

**For Foundry v2 version**, edit `app/backend/app/config/container_foundry_v2.py` similarly, but use the foundry client:
```python
your_agent_name = providers.Factory(
    YourAgentName,
    azure_ai_client=_azure_ai_client,
    your_service_mcp_server_url=f"{settings.YOUR_SERVICE_MCP_URL}/mcp"
)
```

#### Step 5: Update the Handoff Orchestrator

Edit the handoff orchestrator to include your new agent:

**File**: `app/backend/app/agents/azure_chat/handoff_orchestrator.py` (or `foundry_v2` version)

1. Update the HandoffOrchestrator class to include your agent in the workflow:
```python
class HandoffOrchestrator:
    triage_instructions = """
    You are a banking customer support agent triaging customer requests...
    
    # Triage rules
    - If request is related to [your domain], call handoff_to_YourAgentName.
    ...
    """
    
    def __init__(self, 
                 azure_chat_client: AzureOpenAIChatClient,
                 account_agent: AccountAgent,
                 transaction_agent: TransactionHistoryAgent,
                 payment_agent: PaymentAgent,
                 your_agent_name: YourAgentName):  # Add parameter
        self.azure_chat_client = azure_chat_client
        self.account_agent = account_agent
        self.transaction_agent = transaction_agent
        self.payment_agent = payment_agent
        self.your_agent_name = your_agent_name  # Store reference
        self.workflow = None
    
    async def initialize(self, checkpoint_storage: CheckpointStorage):
        """Initialize the workflow with async operations"""
        triage_agent = Agent(
            client=self.azure_chat_client,
            instructions=HandoffOrchestrator.triage_instructions,
            name="triage_agent"
        )
        
        self.workflow = (
            HandoffBuilder(
                name="banking_assistant_handoff",
                participants=[
                    triage_agent,
                    await self.account_agent.build_af_agent(),
                    await self.transaction_agent.build_af_agent(),
                    await self.payment_agent.build_af_agent(),
                    await self.your_agent_name.build_af_agent()  # Add here
                ],
            )
            .with_start_agent(triage_agent)
            .with_termination_condition(
                lambda conv: sum(1 for msg in conv if msg.role == "user") >= 20
            )
            .with_checkpointing(checkpoint_storage)
            .build()
        )
```

2. Update the orchestrator factory in your DI container to add the new agent:

**In `app/backend/app/config/container_azure_chat.py`:**

```python
# Update the handoff_orchestrator_chatkit factory
handoff_orchestrator_chatkit = providers.Factory(
    HandoffOrchestratorChatKit,
    azure_chat_client=_azure_chat_client,
    account_agent=account_agent_chatkit,
    transaction_agent=transaction_agent_chatkit,
    payment_agent=payment_agent_chatkit,
    your_agent_name=your_agent_name  # Add your new agent
)
```

#### Step 7: Add Tests

Create a test file: `app/backend/tests/test_your_agent_chatkit.py`

```python
import pytest
from app.agents.azure_chat.your_agent_name import YourAgentName

@pytest.mark.asyncio
async def test_your_agent_initialization():
    """Test agent initializes correctly."""
    agent = YourAgentName(model="gpt-4", tools=[])
    assert agent.name == "your_agent_name"
    assert agent.instructions is not None

```

Run tests:
```bash
cd app/backend
uv run pytest tests/test_your_agent_chatkit.py -v
```

#### Step 8: Test End-to-End

1. Start the backend server:
   ```bash
   cd app/backend
   PROFILE=dev ENABLE_SENSITIVE_DATA=true \
     uv run uvicorn app.main_chatkit_server:app --reload --port 8080
   ```
   
   Or use VSCode debugger: Select **DEV - Chatkit Backend App** and press F5

2. Start the frontend:
   ```bash
   cd app/frontend/banking-web
   npm run dev
   ```

3. Test routing to your new agent through the chat interface

---

### Task 2: Change Agentic Orchestration Logic

Follow these steps to modify how agents are selected and how handoffs occur:

#### Step 1: Locate the Orchestrator File

Navigate to the handoff orchestrator for your implementation:
- **Azure Chat**: `app/backend/app/agents/azure_chat/handoff_orchestrator.py`
- **Foundry v2**: `app/backend/app/agents/foundry_v2/handoff_orchestrator.py`

#### Step 2: Understand Current Orchestration

Review and update actual triage agent instructions from `handoff_orchestrator.py`:

```python
class HandoffOrchestrator:
    
    triage_instructions = """
      You are a banking customer support agent triaging customer requests about their banking account, movements, payments.
      You have to evaluate the whole conversation with the customer and handoff to AccountAgent, TransactionHistoryAgent, PaymentAgent. 
      When delegation is required, call the matching handoff too based on triage rules.
      
      
      # Triage rules
      - If the user request is related to bank account information like account balance, payment methods, cards and beneficiaries book you must call handoff_to_AccountAgent.
      - If the user request is related to banking movements and payments history, you must call handoff_to_TransactionHistoryAgent.
      - If the user request is related to initiate a payment request, upload a bill or invoice image for payment or manage an on-going payment process, you must call handoff_to_PaymentAgent.
      - If the user request is not related to account, transactions or payments you must respond to the user that you are not able to help with the request.

      
    """
```

**Key Points:**
- The triage agent evaluates the entire conversation context
- Routing is based on domain-specific rules (account, transactions, payments)
- Out-of-scope requests are handled by the triage agent itself
- Handoff functions are automatically generated by the framework (`handoff_to_AccountAgent`, etc.)


#### Step 6: Test Routing Changes

Create or update tests in `app/backend/tests/`:

```python
@pytest.mark.asyncio
async def test_orchestrator_routes_to_payment_agent():
    """Test routing logic for payment requests."""
    # Test implementation
    pass

@pytest.mark.asyncio  
async def test_orchestrator_context_passing():
    """Test context is preserved across handoffs."""
    # Test implementation
    pass
```

#### Step 7: Validate End-to-End

1. Test various user queries that should trigger different routing paths
2. Verify context is preserved across handoffs
3. Check logs for correct agent selection:
   ```bash
   # View logs with routing decisions
   cd app/backend
   PROFILE=dev ENABLE_SENSITIVE_DATA=true \
     uv run uvicorn app.main_chatkit_server:app --reload --log-level debug --port 8080
   ```
   
   Or use VSCode debugger with breakpoints for step-by-step debugging

---

### Task 3: Customize Chat Protocol Event Handlers

The Microsoft Agent Framework (MAF) emits generic workflow events during agent execution. To expose agents through different chat protocols, you need to translate these MAF events into protocol-specific events.

**Current Implementation:** The banking assistant includes a built-in ChatKit protocol handler that translates MAF events to [ChatKit protocol events](./docs/chat-server-protocol.md).

#### Step 1: Understand MAF to Protocol Translation

The translation happens in protocol-specific event handlers:

**Example: ChatKit Events Handler** (`app/backend/app/routers/chatkit/_chatkit_events_handler.py`)

```python
class ChatKitEventsHandler:
    """Translates MAF events to ChatKit protocol events."""
    
    async def handle_events(
        self, 
        thread_id: str, 
        af_events: AsyncIterable[WorkflowEvent]
    ) -> AsyncGenerator[ThreadStreamEvent, None]:
        """Process MAF events and yield ChatKit-compatible events."""
        
        async for event in af_events:
            if isinstance(event, AgentResponseUpdate):
                # Translate to ChatKit ThreadItemAddedEvent
                chatkit_event = self._handle_text_content(
                    thread_id, 
                    event.message_id, 
                    event.content
                )
                yield chatkit_event
            
            elif event.type == "output" and all(item.type == "function_call" for item in event.data.contents):
                # Translate to ChatKit ProgressUpdateEvent
                yield ProgressUpdateEvent(
                    type="thread.progress.update",
                    message=f"Processing: {event.tool_name}..."
                )
```

**MAF Events Source:** Review all available MAF events in the [MAF Events Source](https://github.com/microsoft/agent-framework/blob/main/python/packages/core/agent_framework/_workflows/_events.py).


#### Step 2: Add a New Chat Protocol (Example: M365 Agents Activity Protocol)

To support a new chat protocol like Microsoft 365 Agents Activity Protocol:

##### 2.1: Create Protocol Event Handler

Create `app/backend/app/routers/m365/_m365_events_handler.py`:

```python
from typing import AsyncGenerator, AsyncIterable
from agent_framework import AgentResponseUpdate, WorkflowEvent
from datetime import datetime

# M365 Activity Protocol types (pseudo-code - use actual M365 types)
class ActivityStreamEvent:
    """Base class for M365 activity events."""
    pass

class ActivityMessageEvent(ActivityStreamEvent):
    """M365 activity message event."""
    def __init__(self, activity_id: str, text: str, timestamp: datetime):
        self.type = "activity.message"
        self.activity_id = activity_id
        self.text = text
        self.timestamp = timestamp

class ActivityProgressEvent(ActivityStreamEvent):
    """M365 activity progress event."""
    def __init__(self, activity_id: str, status: str, progress: int):
        self.type = "activity.progress"
        self.activity_id = activity_id
        self.status = status
        self.progress = progress


class M365EventsHandler:
    """Translates MAF events to M365 Agents Activity Protocol events."""
    
    def __init__(self) -> None:
        self.activity_started = False
        self.accumulated_text = ""
    
    async def handle_events(
        self, 
        activity_id: str, 
        af_events: AsyncIterable[WorkflowEvent]
    ) -> AsyncGenerator[ActivityStreamEvent, None]:
        """Process MAF events and yield M365-compatible activity events."""
        
        async for event in af_events:
            # Translate MAF events to M365 Activity Protocol
            if isinstance(event, AgentResponseUpdate):
                # Convert text response to M365 activity message
                if event.content:
                    yield ActivityMessageEvent(
                        activity_id=activity_id,
                        text=event.content,
                        timestamp=datetime.now()
                    )
            
            elif event.type == "tool_call_start":
                # Convert tool execution to M365 progress update
                yield ActivityProgressEvent(
                    activity_id=activity_id,
                    status=f"Executing {event.tool_name}",
                    progress=50
                )
            
            elif event.type == "tool_call_end":
                # Tool completed
                yield ActivityProgressEvent(
                    activity_id=activity_id,
                    status=f"Completed {event.tool_name}",
                    progress=100
                )
            
            elif event.type == "error":
                # Error handling for M365
                yield ActivityMessageEvent(
                    activity_id=activity_id,
                    text=f"Error: {event.error}",
                    timestamp=datetime.now()
                )
```

##### 2.2: Create Protocol Router

Create `app/backend/app/routers/m365/m365_server.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.routers.m365._m365_events_handler import M365EventsHandler
from app.config.container_azure_chat import Container
import json

router = APIRouter(prefix="/m365")

@router.post("/activities/run")
async def run_activity(
    request: dict,  # M365 activity request schema
    container: Container = Depends(lambda: Container())
):
    """
    M365 Agents Activity Protocol endpoint.
    Runs an agent activity and streams responses using M365 protocol.
    """
    
    async def stream_m365_events():
        """Stream M365 activity events using Server-Sent Events."""
        
        # Get orchestrator from DI container
        orchestrator = container.handoff_orchestrator_chatkit()
        
        # Run the agent workflow
        af_events = orchestrator.run(
            activity_id=request.get("activityId"),
            user_message=request.get("message")
        )
        
        # Translate MAF events to M365 events
        m365_handler = M365EventsHandler()
        async for m365_event in m365_handler.handle_events(
            activity_id=request.get("activityId"),
            af_events=af_events
        ):
            # Stream as Server-Sent Events
            event_data = json.dumps(m365_event.__dict__)
            yield f"data: {event_data}\n\n"
    
    return StreamingResponse(
        stream_m365_events(),
        media_type="text/event-stream"
    )

@router.get("/activities/{activity_id}/status")
async def get_activity_status(activity_id: str):
    """Get the status of a running activity."""
    # Implementation for status checking
    return {"status": "running", "activity_id": activity_id}
```

##### 2.3: Register Router in Main Application

create `main_m365_server.py`:

```python
from app.routers.m365 import m365_server

# Register the M365 protocol router
app.include_router(m365_server.router, tags=["m365"])
```

##### 2.4: Directory Structure

The final structure for a new protocol:

```
app/backend/app/routers/
├── chatkit/                          # ChatKit protocol implementation
│   ├── _chatkit_events_handler.py    # MAF → ChatKit translation
│   ├── chatkit_server.py             # ChatKit API endpoints
│   └── attachments.py                # ChatKit attachment handling
├── m365/                             # M365 protocol implementation (NEW)
│   ├── _m365_events_handler.py       # MAF → M365 translation
│   └── m365_server.py                # M365 API endpoints
└── simple_chat/                      # Simple chat protocol
    └── ...
```

#### Key Takeaways

- **Protocol independence**: MAF events are protocol-agnostic
- **Event handlers**: Each protocol needs its own translation layer
- **Endpoint structure**: Each protocol gets its own router with protocol-specific endpoints
- **Reusable agents**: The same agent workflows work with any protocol
- **Multiple protocols**: You can support ChatKit, M365, custom protocols simultaneously

