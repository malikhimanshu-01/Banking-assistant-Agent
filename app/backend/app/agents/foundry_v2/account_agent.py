from agent_framework.foundry import FoundryChatClient
from agent_framework import tool,Agent, MCPStreamableHTTPTool
from app.helpers.user_profile_provider import UserProfileProvider

import logging


logger = logging.getLogger(__name__)

@tool(
    name="handoff_to_TriageAgent", description="Handoff to the triage-agent agent."
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"

class AccountAgent :
    instructions = """
    you are a personal financial advisor who help the user to retrieve information about their bank accounts.
    Always use markdown to format your response.
    Always use the logged user details to retrieve account info.
    """
    name = "AccountAgent"
    description = "This agent manages user accounts related information such as balance, credit cards."
   

    def __init__(self, azure_ai_client: FoundryChatClient, account_mcp_server_url: str):
        self.azure_ai_client = azure_ai_client
        self.account_mcp_server_url = account_mcp_server_url



    async def build_af_agent(self)-> Agent:
    
      logger.info("Initializing Account Agent connection for account api ")
      
      logger.info("Initializing Account MCP server tools for AccountAgent ")
      account_mcp_server = MCPStreamableHTTPTool(
                name="Account MCP server client",
                url=self.account_mcp_server_url)
      await account_mcp_server.connect()
      agent = Agent(
                client=self.azure_ai_client,
                instructions=AccountAgent.instructions,
                name=AccountAgent.name,
                tools=[account_mcp_server, handoff_to_triage_agent],
                context_providers=[UserProfileProvider()]
            )
      agent.default_options["tools"] = [account_mcp_server, handoff_to_triage_agent]
      return agent
    
