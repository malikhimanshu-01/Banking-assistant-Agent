"""Dependency injection container configuration."""

import os

from agent_framework.foundry import FoundryChatClient
from dependency_injector import containers, providers
from azure.ai.projects import AIProjectClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
from app.helpers.blob_proxy import BlobStorageProxy
from app.tools.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper
from app.config.azure_credential import get_azure_credential, get_async_azure_credential
from app.config.settings import settings


#Azure AI Foundry V2 agents for ChatKit protocol
from app.agents.foundry_v2.handoff_orchestrator import HandoffOrchestrator as HandoffOrchestratorChatKit
from app.agents.foundry_v2.account_agent import AccountAgent as AccountAgentChatKit
from app.agents.foundry_v2.transaction_agent import TransactionHistoryAgent as TransactionHistoryAgentChatKit
from app.agents.foundry_v2.payment_agent import PaymentAgent as PaymentAgentChatKit


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""
   
    # Helpers
    blob_service_client = providers.Singleton(
        BlobServiceClient,
        credential = providers.Factory(get_azure_credential),
        account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
    )

    blob_proxy = providers.Singleton(
        BlobStorageProxy,
        client = blob_service_client,
        container_name = settings.AZURE_STORAGE_CONTAINER
    )

    # Document Intelligence client singleton
    document_intelligence_client = providers.Singleton(
        DocumentIntelligenceClient,
        credential=providers.Factory(get_azure_credential),
        endpoint=f"https://{settings.AZURE_DOCUMENT_INTELLIGENCE_SERVICE}.cognitiveservices.azure.com/"
    )

    # Document Intelligence scanner singleton
    document_intelligence_scanner = providers.Singleton(
        DocumentIntelligenceInvoiceScanHelper,
        client=document_intelligence_client,
        blob_storage_proxy=blob_proxy
    )
    

     

    
    #Azure Agent Service based agents

       
       # Foundry v2 Agent Client
    _azure_ai_client = providers.Factory(
        FoundryChatClient,
        credential=providers.Factory(get_async_azure_credential), 
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,model=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME
    )

   
    #Account Agent with Azure chat based agents.
    account_agent_chatkit = providers.Factory(
    AccountAgentChatKit,
    azure_ai_client=_azure_ai_client,
    account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp"
    )

    transaction_agent_chatkit = providers.Factory(
    TransactionHistoryAgentChatKit,
    azure_ai_client=_azure_ai_client,
    account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp",
    transaction_mcp_server_url=f"{settings.TRANSACTION_MCP_URL}/mcp"
    )

    payment_agent_chatkit = providers.Factory(
    PaymentAgentChatKit,
    azure_ai_client=_azure_ai_client,
    account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp",
    transaction_mcp_server_url=f"{settings.TRANSACTION_MCP_URL}/mcp",
    payment_mcp_server_url=f"{settings.PAYMENT_MCP_URL}/mcp",
    document_scanner_helper=document_intelligence_scanner
    )

    # A specialized chatkit Supervisor Agent implemented using agent framework handoff built-in orchestration with Azure chat based agents. 
    # A per request instance is created as based on recommendation from agent framework team about managing workflow instance.
    handoff_orchestrator_chatkit = providers.Factory(
        HandoffOrchestratorChatKit,
        azure_ai_client=_azure_ai_client,
        account_agent=account_agent_chatkit,
        transaction_agent=transaction_agent_chatkit,
        payment_agent=payment_agent_chatkit
    )
   