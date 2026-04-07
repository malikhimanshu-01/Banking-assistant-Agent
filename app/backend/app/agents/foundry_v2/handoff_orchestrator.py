from typing import AsyncGenerator
from collections.abc import AsyncIterable,Sequence
from agent_framework import CheckpointStorage, SupportsAgentRun,FunctionTool,tool,Content,AgentResponseUpdate, Agent,InMemoryCheckpointStorage,WorkflowCheckpoint, WorkflowEvent
from agent_framework.exceptions import AgentFrameworkException
from agent_framework.foundry import FoundryChatClient
from app.agents.foundry_v2.account_agent import AccountAgent
from app.agents.foundry_v2.transaction_agent import TransactionHistoryAgent
from app.agents.foundry_v2.payment_agent import PaymentAgent
from app.helpers.no_history_provider import NoHistoryProvider
from uuid import uuid4
import logging

from agent_framework.orchestrations import (
    HandoffAgentExecutor,
    HandoffBuilder,
    HandoffConfiguration,
    HandoffAgentUserRequest
)

logger = logging.getLogger(__name__)



# Define handoff tools upfront for Azure AI Agents.
# Azure AI Agents require tools to be defined at agent creation time (server-side),
# so we create the handoff tools here and pass them during agent creation.
# The HandoffBuilder's middleware will intercept these tool calls to perform routing.
@tool(
    name="handoff_to_TriageAgent", description="Handoff to the triage-agent agent."
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"

@tool(
    name="handoff_to_AccountAgent", description="Handoff to the account-agent agent."
)
def handoff_to_account_agent(context: str | None = None) -> str:
    """Transfer the conversation to the account agent."""
    return "Handoff to AccountAgent"

@tool(
    name="handoff_to_TransactionHistoryAgent", description="Handoff to the transaction-history-agent agent."
)
def handoff_to_transaction_history_agent(context: str | None = None) -> str:
    """Transfer the conversation to the transaction history agent."""
    return "Handoff to TransactionHistoryAgent"

@tool(
    name="handoff_to_PaymentAgent", description="Handoff to the payment-agent agent."
)
def handoff_to_payment_agent(context: str | None = None) -> str:
    """Transfer the conversation to the payment agent."""
    return "Handoff to PaymentAgent"

class CustomHandoffAgentExecutor(HandoffAgentExecutor):
    """Custom executor with overridden handoff tool generation."""

    def _apply_auto_tools(self, agent: Agent, targets: Sequence[HandoffConfiguration]) -> None:
        default_options = agent.default_options
        existing_tools = list(default_options.get("tools") or [])
        existing_names = {getattr(tool, "name", "") for tool in existing_tools if hasattr(tool, "name")}

        new_tools: list[FunctionTool] = []
        for target in targets:
            tool = self._create_handoff_tool(target.target_id, target.description)
            if tool.name in existing_names:
                # Skip if handoff tool already exists
                continue
            new_tools.append(tool)

        if new_tools:
            default_options["tools"] = existing_tools + new_tools  # type: ignore[operator]
        else:
            default_options["tools"] = existing_tools

class CustomHandoffBuilder(HandoffBuilder):
    """Builder that uses the custom executor."""

    def _resolve_executors(
        self,
        agents: dict[str, SupportsAgentRun],
        handoffs: dict[str, list[HandoffConfiguration]],
    ) -> dict[str, HandoffAgentExecutor]:
        executors: dict[str, HandoffAgentExecutor] = {}

        for id, agent in agents.items():
            resolved_id = self._resolve_to_id(agent)
            autonomous_mode = self._autonomous_mode and (
                not self._autonomous_mode_enabled_agents or id in self._autonomous_mode_enabled_agents
            )

            executors[resolved_id] = CustomHandoffAgentExecutor(
                agent=agent,
                handoffs=handoffs.get(resolved_id, []),
                is_start_agent=(id == self._start_id),
                termination_condition=self._termination_condition,
                autonomous_mode=autonomous_mode,
                autonomous_mode_prompt=self._autonomous_mode_prompts.get(id, None),
                autonomous_mode_turn_limit=self._autonomous_mode_turn_limits.get(id, None),
            )

        return executors
    
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

    """ A simple in-memory store [thread_id, CheckpointStorage] to keep track of workflow instances per user/session.
        In production, this should be replaced with a persistent store like a database or distributed cache.
    """
    thread_checkpoint_store: dict[str, CheckpointStorage] = {}
    checkpoint_storage = InMemoryCheckpointStorage()

    def __init__(self, 
                 azure_ai_client: FoundryChatClient,
                 account_agent: AccountAgent,
                 transaction_agent: TransactionHistoryAgent,
                 payment_agent: PaymentAgent
                                ):
      self.azure_ai_client = azure_ai_client
      self.account_agent = account_agent
      self.transaction_agent = transaction_agent
      self.payment_agent = payment_agent
      self.workflow = None  # Will be initialized in async method

    async def initialize(self, checkpoint_storage: CheckpointStorage ):
      """Initialize the workflow with async operations"""
      triage_agent = Agent(
            client=self.azure_ai_client,
            instructions=HandoffOrchestrator.triage_instructions,
            name="TriageAgent",
            tools=[handoff_to_account_agent, handoff_to_transaction_history_agent, handoff_to_payment_agent],
            # NoHistoryProvider prevents the framework from auto-injecting an
            # InMemoryHistoryProvider.  Inside a HandoffBuilder workflow the
            # executor already tracks the full conversation, so the auto-injected
            # provider would duplicate messages on every turn, eventually causing
            # OpenAI 400 errors due to mismatched tool_calls / tool results.
            context_providers=[NoHistoryProvider()]
        )
      
       # Register handoff tools in default_options so CustomHandoffBuilder sees them
      triage_agent.default_options["tools"] = [
        handoff_to_account_agent,
        handoff_to_transaction_history_agent,
        handoff_to_payment_agent,
    ]
      
      account_agent = await self.account_agent.build_af_agent()
      transaction_agent = await self.transaction_agent.build_af_agent()
      payment_agent = await self.payment_agent.build_af_agent()
      
      self.workflow = (
        CustomHandoffBuilder(
            name="banking_assistant_handoff",
            participants=[triage_agent,account_agent,transaction_agent,payment_agent],
            termination_condition=lambda conv: sum(1 for msg in conv if msg.role == "user") >= 20,
            checkpoint_storage=checkpoint_storage,
        )
        .with_start_agent(triage_agent)
        .add_handoff(
            triage_agent, [account_agent, transaction_agent, payment_agent]
        )  # Triage can hand off to specialists
        .add_handoff(account_agent, [triage_agent])  # Specialists can hand off back to triage
        .add_handoff(transaction_agent, [triage_agent])  # Specialists can hand off back to triage
        .add_handoff(payment_agent, [triage_agent])  # Specialists can hand off
        .build()
    )

    async def _get_or_create_checkpoint_store(self,thread_id: str) -> CheckpointStorage :
        checkpoint_storage = HandoffOrchestrator.thread_checkpoint_store.get(thread_id, None)
        if checkpoint_storage is not None:
            return checkpoint_storage
        
        logger.info(f"Creating new checkpoint storage for thread_id: {thread_id}")
        checkpoint_storage = InMemoryCheckpointStorage()
        HandoffOrchestrator.thread_checkpoint_store[thread_id] = checkpoint_storage
        return checkpoint_storage
            
    
    async def _resume_workflow_with_response(self, checkpoint_storage: CheckpointStorage, checkpoint_id: str, user_message: str) -> AsyncIterable[WorkflowEvent]:
        """Resume a workflow from a checkpoint with a response to a RequestInfoEvent.

        Args:
            checkpoint (WorkflowCheckpoint): The checkpoint to resume from.
            response (dict[str, str]): The response mapping request IDs to user inputs.

        Yields:
            AsyncIterable[WorkflowEvent]: The events generated by resuming the workflow.
        """
        events = self.workflow.run(checkpoint_id=checkpoint_id, checkpoint_storage=checkpoint_storage, stream=True) #type: ignore
        
        responses: dict[str, object] = {}
        
        #We need to collect all workflow events otherwise we get concurrent workflow execution error when trying to resume.
        consumed_events = [event async for event in events]
        for event in consumed_events:
            if event.type == "request_info":
                if isinstance(event.data, HandoffAgentUserRequest):
                        responses[event.request_id] = HandoffAgentUserRequest.create_response(user_message)
                        return self.workflow.run(responses=responses, checkpoint_id=checkpoint_id, checkpoint_storage=checkpoint_storage, stream=True) #type: ignore
                else:
                    raise AgentFrameworkException(f"RequestInfoEvent [{event.request_id}] found in the checkpoint [{checkpoint_id}] that is not a HandoffAgentUserRequest.")
        #if we reach here, something went wrong. For this use case HandoffOrchestrator expected to always trigger a RequestInfoEvent.
        raise AgentFrameworkException(f"No RequestInfoEvent found in the checkpoint [{checkpoint_id}]")
            
    
    async def processMessageStream(self, user_message: str , thread_id : str ) -> AsyncGenerator[WorkflowEvent,None]:
        
        checkpoint_storage = await self._get_or_create_checkpoint_store(thread_id)
       
        #Agents are initialized asynchronously due to the use of MCP tools. So we can't initialize the workflow in __init__. We do it lazily here.
        if self.workflow is None:
                await self.initialize(checkpoint_storage)
              
        checkpoint = None
        events = None

        # try to retrieve checkpoint for the given thread_id. If None, we start a new conversation.
        checkpoint = await checkpoint_storage.get_latest(workflow_name=self.workflow.name) # type: ignore
        workflow_id = self.workflow.id  # type: ignore

        if checkpoint is None:
            # Start a new conversation. This is the first user message.
            async for event in self.workflow.run(user_message, stream=True):# type: ignore
                yield event # type: ignore
        else:
            #Resuming an existing conversation.
            async for event in await self._resume_workflow_with_response(checkpoint_storage,checkpoint.checkpoint_id, user_message):
                yield event

    async def processToolApprovalResponse(self, thread_id: str, approved:bool, call_id: str, request_id: str, tool_name: str) -> AsyncGenerator[WorkflowEvent,None]:
        """Process a tool approval response from the user.

        Args:
            thread_id (str): The thread ID associated with the workflow.
            approved (bool): Whether the user approved the tool execution.

        """
        checkpoint_storage = await self._get_or_create_checkpoint_store(thread_id)

        if self.workflow is None:
               await self.initialize(checkpoint_storage)
       

        checkpoint = await checkpoint_storage.get_latest(workflow_name=self.workflow.name) # type: ignore
        if checkpoint is None:
            raise AgentFrameworkException(f"No checkpoint found for thread_id: {thread_id} when trying to process tool approval response")
        
        events = self.workflow.run(checkpoint_id=checkpoint.checkpoint_id, #type: ignore
                                   checkpoint_storage=checkpoint_storage, stream=True) #type: ignore
        
        responses: dict[str, object] = {}
        #restart the workflow to get the reference to FunctionApprovalRequestEvent
        consumed_events = [event async for event in events]
        for event in consumed_events:
            yield event
            if event.type == "request_info":
                if isinstance(event.data, Content) and event.data.type == "function_approval_request":
                        responses[event.request_id] = event.data.to_function_approval_response(approved=approved)
                        async for event in self.workflow.run(responses=responses, checkpoint_id=checkpoint.checkpoint_id, checkpoint_storage=checkpoint_storage, stream=True) : #type: ignore
                            yield event
                else:
                    raise AgentFrameworkException(f"RequestInfoEvent [{event.request_id}] found in the checkpoint [{checkpoint.checkpoint_id}] that is not a HandoffUserInputRequest.")