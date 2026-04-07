from agent_framework.foundry import FoundryChatClient
from agent_framework import tool,Agent, MCPStreamableHTTPTool
from app.common.user_profile_provider import UserProfileProvider

import logging


logger = logging.getLogger(__name__)

@tool(
    name="handoff_to_TriageAgent", description="Handoff to the triage-agent agent."
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"
class TransactionHistoryAgent :
    instructions = """
    you are a personal financial advisor who help the user with their recurrent bill payments. To search about the payments history you need to know the payee name.
    By default you should search the last 10 account transactions ordered by date.    
    If the user want to search last account transactions for a specific payee, extract it from the request and use it as filter.
    
    Use markdown list or table to display the transaction information.
    Always use the logged user details to retrieve account info.
    """
    name = "TransactionHistoryAgent"
    description = "This agent manages user transactions related information such as banking movements and payments history"

    def __init__(self, azure_ai_client: FoundryChatClient,
                 account_mcp_server_url: str,
                 transaction_mcp_server_url: str,
                  ):
        self.azure_ai_client = azure_ai_client
        self.account_mcp_server_url = account_mcp_server_url
        self.transaction_mcp_server_url = transaction_mcp_server_url
      


    async def build_af_agent(self) -> Agent:
    
      logger.info("Building request scoped transaction agent run ")
      
      logger.info("Initializing Account MCP, Transaction MCP server tools for TransactionHistoryAgent ")
      
      async with ( 
        MCPStreamableHTTPTool(
          name="Account MCP server client",
          url=self.account_mcp_server_url
       ) as account_mcp_server,
        MCPStreamableHTTPTool(
          name="Transaction MCP server client",
          url=self.transaction_mcp_server_url
     ) as transaction_mcp_server,
      ):

        agent = Agent(
                client=self.azure_ai_client,
                instructions=TransactionHistoryAgent.instructions,
                name=TransactionHistoryAgent.name,
                tools=[account_mcp_server, transaction_mcp_server,handoff_to_triage_agent],
                context_providers=[UserProfileProvider()]
            )
        agent.default_options["tools"] = [account_mcp_server, transaction_mcp_server,handoff_to_triage_agent]
        return agent  