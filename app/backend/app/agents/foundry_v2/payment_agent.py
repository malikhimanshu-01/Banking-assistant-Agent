from agent_framework.azure import AzureAIClient
from agent_framework import tool,Agent, MCPStreamableHTTPTool
from app.tools.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper

from datetime import datetime

import logging


logger = logging.getLogger(__name__)

@tool(
    name="handoff_to_TriageAgent", description="Handoff to the triage-agent agent."
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"

class PaymentAgent :
    instructions = """
    you are a personal financial advisor who help the user with their recurrent bill payments. The user may want to pay the bill uploading a photo of the bill, or it may start the payment checking transactions history for a specific payee.
        For the bill payment you need to know the: bill id or invoice number, payee name, the total amount.
        If you don't have enough information to pay the bill ask the user to provide the missing information.
        If the user upload an invoice image, scan it and always ask the user to confirm the extracted data from the image.
        Always check if the bill has been already paid based on payment history before asking to execute the bill payment.
        Ask for the payment method to use based on the available methods on the user account.
        if the user wants to pay using bank transfer, check if the payee is in account registered beneficiaries list. If not ask the user to provide the payee bank code.
        Check if the payment method selected by the user has enough funds to pay the bill. Don't use the account balance to evaluate the funds.
        Before submitting the payment to the system ask the user confirmation providing the payment details.
        Include in the payment description the invoice id or bill id as following: payment for invoice 1527248.
        Extract a category for the payment based on the payee name (for example utilities, rent, mortgage, insurance, subscriptions, phone, internet, etc..)
        Payment status is 'paid' when submitting a payment with CreditCard. Status is 'pending' when submitting a payment with BankTransfer.
        When submitting payment always use the available functions to retrieve accountId, paymentMethodId.
        If the payment succeeds provide the user with the payment confirmation. If not provide the user with the error message.
        Use markdown list or table to display bill extracted data, payments, account or transaction details.
        Always use the below logged user details to retrieve account info:
       {user_mail}
        Current timestamp:
       {current_date_time}
        Don't try to guess accountId,paymentMethodId from the conversation.When submitting payment always use functions to retrieve accountId, paymentMethodId.
        
        #Upload image example
        user: please help me pay this bill [attachment_id: atc_3a0a727d]
        
        """
    name = "PaymentAgent"
    description = "This agent manages user payments related information such as submitting payment requests and bill payments."

    def __init__(self, azure_ai_client: AzureAIClient,
                  account_mcp_server_url: str,
                  transaction_mcp_server_url: str,
                  payment_mcp_server_url: str,
                  document_scanner_helper : DocumentIntelligenceInvoiceScanHelper):
        self.azure_ai_client = azure_ai_client
        self.account_mcp_server_url = account_mcp_server_url
        self.transaction_mcp_server_url = transaction_mcp_server_url
        self.payment_mcp_server_url = payment_mcp_server_url
        self.document_scanner_helper = document_scanner_helper
        


    async def build_af_agent(self) -> Agent:
    
      logger.info("Building request scoped Payment agent run ")
      
      user_mail="bob.user@contoso.com"
      current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      full_instruction = PaymentAgent.instructions.format(user_mail=user_mail, current_date_time=current_date_time)
      
      logger.info("Initializing Account MCP, Transaction MCP, Payment MCP server tools for PaymentAgent") 
      
      async with (
        MCPStreamableHTTPTool(
          name="Account MCP server client",
          url=self.account_mcp_server_url
        ) as account_mcp_server, 
        MCPStreamableHTTPTool(
          name="Transaction MCP server client",
          url=self.transaction_mcp_server_url
        ) as transaction_mcp_server, 
         MCPStreamableHTTPTool(
          name="Payment MCP server client",
          url=self.payment_mcp_server_url,
          approval_mode = { "always_require_approval": ["processPayment"] }
        ) as payment_mcp_server,
      ):

        agent = Agent(
                client=self.azure_ai_client,
                instructions=full_instruction,
                name=PaymentAgent.name,
                tools=[account_mcp_server,
                    transaction_mcp_server, 
                    payment_mcp_server,
                    self.document_scanner_helper.scan_invoice,
                    handoff_to_triage_agent])
                
        agent.default_options["tools"] = [account_mcp_server, 
                                        transaction_mcp_server, 
                                        payment_mcp_server,
                                        self.document_scanner_helper.scan_invoice,
                                        handoff_to_triage_agent]
        return agent