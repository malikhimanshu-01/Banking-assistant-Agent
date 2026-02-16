---
name: create-update-new-agent
description: This skill provides instructions for creating or updating a new agent in the banking assistant project. It covers defining agent behavior, integrating with backend services, and testing the agent.
license: MIT
---

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