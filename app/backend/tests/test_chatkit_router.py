"""Integration tests for the /chatkit streaming endpoint.

Tests the full SSE event flow for creating new threads and processing
user messages through the multi-agent banking assistant.

Requirements:
- Azure OpenAI credentials (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)
- MCP servers are started in-process as mock servers with sample data
"""

import asyncio
import json
import logging
import socket
import threading
from typing import List

import pytest
import uvicorn
from fastapi import FastAPI
from fastmcp import FastMCP
from httpx import ASGITransport, AsyncClient

# Suppress noisy MCP client teardown errors (cancel scope / async generator cleanup)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Mock MCP servers with sample data matching business-api services
# ---------------------------------------------------------------------------

def _create_account_mcp_app() -> FastAPI:
    """Create a mock Account MCP server with sample data."""
    mcp = FastMCP("Account MCP Server")

    accounts_by_username = {
        "bob.user@contoso.com": [
            {
                "id": "1010",
                "userName": "bob.user@contoso.com",
                "accountHolderFullName": "Bob User",
                "currency": "EUR",
                "activationDate": "2022-01-01",
                "balance": "10000",
                "paymentMethods": [
                    {"id": "345678", "type": "BankTransfer", "activationDate": "2022-01-01", "expirationDate": "9999-01-01"},
                    {"id": "55555", "type": "Visa", "name": "Primary Platinum", "activationDate": "2024-03-01", "expirationDate": "2027-03-01"},
                    {"id": "66666", "type": "Visa", "name": "Secondary Gold", "activationDate": "2025-11-01", "expirationDate": "2028-11-01"},
                ],
            }
        ],
        "alice.user@contoso.com": [
            {
                "id": "1000",
                "userName": "alice.user@contoso.com",
                "accountHolderFullName": "Alice User",
                "currency": "USD",
                "activationDate": "2022-01-01",
                "balance": "5000",
                "paymentMethods": [
                    {"id": "12345", "type": "Visa", "activationDate": "2022-01-01", "expirationDate": "2025-01-01"},
                    {"id": "23456", "type": "BankTransfer", "activationDate": "2022-01-01", "expirationDate": "9999-01-01"},
                ],
            }
        ],
    }

    account_details = {
        "1010": {
            "id": "1010",
            "userName": "bob.user@contoso.com",
            "accountHolderFullName": "Bob User",
            "currency": "EUR",
            "activationDate": "2022-01-01",
            "balance": "10000",
            "paymentMethods": [
                {"id": "345678", "type": "BankTransfer", "activationDate": "2022-01-01", "expirationDate": "9999-01-01"},
                {"id": "55555", "type": "Visa", "name": "Primary Platinum", "activationDate": "2024-03-01", "expirationDate": "2027-03-01"},
                {"id": "66666", "type": "Visa", "name": "Secondary Gold", "activationDate": "2025-11-01", "expirationDate": "2028-11-01"},
            ],
        },
        "1000": {
            "id": "1000",
            "userName": "alice.user@contoso.com",
            "accountHolderFullName": "Alice User",
            "currency": "USD",
            "activationDate": "2022-01-01",
            "balance": "5000",
            "paymentMethods": [
                {"id": "12345", "type": "Visa", "activationDate": "2022-01-01", "expirationDate": "2025-01-01"},
                {"id": "23456", "type": "BankTransfer", "activationDate": "2022-01-01", "expirationDate": "9999-01-01"},
            ],
        },
    }

    @mcp.tool(name="getAccountsByUserName", description="Get the list of all accounts for a specific user")
    def get_accounts_by_user_name(userName: str) -> list:
        return accounts_by_username.get(userName, [])

    @mcp.tool(name="getAccountDetails", description="Get account details and available payment methods")
    def get_account_details(accountId: str) -> dict | None:
        return account_details.get(accountId)

    @mcp.tool(name="getRegisteredBeneficiary", description="Get list of registered beneficiaries for a specific account")
    def get_registered_beneficiary(accountId: str) -> list:
        return [
            {"id": "1", "fullName": "Mike ThePlumber", "bankCode": "123456789", "bankName": "Intesa Sanpaolo"},
            {"id": "2", "fullName": "Jane TheElectrician", "bankCode": "987654321", "bankName": "UBS"},
        ]

    @mcp.tool(name="getCreditCards", description="Get the list of credit cards bound to an account")
    def get_credit_cards(accountId: str) -> list:
        cards_by_account = {
            "1010": [
                {"id": "55555", "type": "credit", "circuit": "visa", "name": "Primary Platinum", "activationDate": "2024-03-01", "expirationDate": "2027-03-01", "balance": 900.5, "number": "5111222233335555", "limit": 3000.0, "status": "active"},
                {"id": "66666", "type": "recharge", "circuit": "visa", "name": "Virtual Gold", "activationDate": "2025-11-01", "expirationDate": "2028-11-01", "balance": 640.25, "number": "5211222233336666", "limit": 2500.0, "status": "active"},
                {"id": "77777", "type": "credit", "circuit": "amex", "name": "Executive Black", "activationDate": "2024-02-01", "expirationDate": "2029-02-01", "balance": 0, "number": "5311222233337777", "limit": 20000.0, "status": "blocked"},
            ],
        }
        return cards_by_account.get(accountId, [])

    @mcp.tool(name="getCardDetails", description="Get the details of a single credit card")
    def get_card_details(cardId: str) -> dict | None:
        cards = {
            "55555": {"id": "55555", "type": "credit", "circuit": "visa", "name": "Primary Platinum", "balance": 900.5},
            "66666": {"id": "66666", "type": "recharge", "circuit": "visa", "name": "Virtual Gold", "balance": 640.25},
        }
        return cards.get(cardId)

    mcp_app = mcp.http_app(path="/mcp")
    app = FastAPI(title="Mock Account MCP Server", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)
    return app


def _create_transaction_mcp_app() -> FastAPI:
    """Create a mock Transaction MCP server with sample data."""
    mcp = FastMCP("Transaction MCP Server")

    all_transactions = {
        "1010": [
            {"id": "232334", "description": "Payment for office supply services", "type": "payment", "flowType": "outcome", "recipientName": "Contoso", "recipientBankReference": "0002", "accountId": "1010", "paymentType": "CreditCard", "cardId": "55555", "amount": 215.00, "timestamp": "2025-03-02T12:00:00Z", "category": "Supply services", "status": "paid"},
            {"id": "3321432", "description": "Business Lunch with customer", "type": "payment", "flowType": "outcome", "recipientName": "Duff", "accountId": "1010", "paymentType": "CreditCard", "cardId": "66666", "amount": 134.10, "timestamp": "2025-10-03T12:00:00Z", "category": "Meals", "status": "paid"},
            {"id": "884995", "description": "Office Air conditioners. Invoice 355TRA1423FFSSS", "type": "payment", "flowType": "outcome", "recipientName": "Contoso Services", "recipientBankReference": "0003", "accountId": "1010", "paymentType": "DirectDebit", "amount": 300.00, "timestamp": "2025-10-03T12:00:00Z", "category": "Services", "status": "paid"},
            {"id": "3946373", "description": "Metro and Bus subscription 2023-AB56", "type": "payment", "flowType": "outcome", "recipientName": "Speedy Subways", "recipientBankReference": "0005", "accountId": "1010", "paymentType": "CreditCard", "cardId": "66666", "amount": 410.00, "timestamp": "2025-04-05T12:00:00Z", "category": "Retail", "status": "paid"},
            {"id": "2004764", "description": "Medical eyes checkup payment. Ref: MZ23-5567", "type": "payment", "flowType": "outcome", "recipientName": "Contoso Health", "recipientBankReference": "0001", "accountId": "1010", "paymentType": "CreditCard", "cardId": "66666", "amount": 230.00, "timestamp": "2025-11-01T12:00:00Z", "category": "Health", "status": "paid"},
            {"id": "49950598", "description": "Payment of the bill 682222", "type": "payment", "flowType": "outcome", "recipientName": "Contoso Services", "recipientBankReference": "0002", "accountId": "1010", "paymentType": "CreditCard", "cardId": "55555", "amount": 200.00, "timestamp": "2025-11-02T12:00:00Z", "category": "Rent", "status": "paid"},
            {"id": "488624", "description": "Monthly Salary - StartUp.com", "type": "deposit", "flowType": "income", "accountId": "1010", "paymentType": "Transfer", "amount": 3000.00, "timestamp": "2025-10-03T12:00:00Z", "category": "Payroll"},
            {"id": "3004853", "description": "Stocks vesting accreditation. www.traderepublic.com - FY25Q3", "type": "deposit", "flowType": "income", "accountId": "1010", "paymentType": "Transfer", "amount": 400.00, "timestamp": "2025-8-04T12:00:00Z", "category": "Investment"},
            {"id": "5001001", "description": "Home power bill 334398", "type": "payment", "flowType": "outcome", "recipientName": "ACME", "recipientBankReference": "0010", "accountId": "1010", "paymentType": "BankTransfer", "amount": 160.40, "timestamp": "2026-04-07T12:00:00Z", "category": "Utilities", "status": "pending"},
            {"id": "5001002", "description": "Office cleaning services March", "type": "payment", "flowType": "outcome", "recipientName": "ACME Services", "recipientBankReference": "0011", "accountId": "1010", "paymentType": "CreditCard", "cardId": "55555", "amount": 95.00, "timestamp": "2026-03-15T12:00:00Z", "category": "Services", "status": "paid"},
        ],
    }

    last_transactions = {
        "1010": [
            {"id": "11", "description": "Home power bill 334398", "type": "payment", "flowType": "outcome", "recipientName": "ACME", "recipientBankReference": "0001", "accountId": "1010", "paymentType": "BankTransfer", "amount": 160.40, "timestamp": "2026-04-07T12:00:00Z", "category": "Utilities", "status": "pending"},
            {"id": "22", "description": "Payment for office supply services", "type": "payment", "flowType": "outcome", "recipientName": "Contoso Services", "recipientBankReference": "0002", "accountId": "1010", "paymentType": "CreditCard", "cardId": "card-8421", "amount": 215.00, "timestamp": "2025-03-02T12:00:00Z", "category": "Supply services", "status": "paid"},
            {"id": "33", "description": "Business Lunch with customer", "type": "payment", "flowType": "outcome", "recipientName": "Duff", "accountId": "1010", "paymentType": "CreditCard", "cardId": "card-8421", "amount": 134.10, "timestamp": "2025-10-03T12:00:00Z", "category": "Meals", "status": "paid"},
            {"id": "43", "description": "card withdrawal at atm 00987", "type": "withdrawal", "flowType": "outcome", "accountId": "1010", "paymentType": "DirectDebit", "cardId": "card-3311", "amount": 150.00, "timestamp": "2025-8-04T12:00:00Z", "category": "Insurance"},
            {"id": "53", "description": "Refund for invoice 19dee", "type": "deposit", "flowType": "income", "recipientName": "oscorp", "recipientBankReference": "0005", "accountId": "1010", "paymentType": "BankTransfer", "amount": 522.00, "timestamp": "2025-4-05T12:00:00Z", "category": "Refunds", "cardId": "card-0098"},
        ],
    }

    @mcp.tool(name="getTransactionsByRecipientName", description="Get transactions by recipient name")
    def get_transactions_by_recipient_name(accountId: str, recipientName: str) -> list:
        transactions = all_transactions.get(accountId, [])
        name_lower = recipientName.lower() if recipientName else ""
        filtered = [t for t in transactions if t.get("recipientName") and name_lower in t["recipientName"].lower()]
        return sorted(filtered, key=lambda t: t["timestamp"], reverse=True)

    @mcp.tool(name="getCardTransactions", description="Get credit and debit card transactions")
    def get_card_transactions(accountId: str, cardId: str) -> list:
        transactions = all_transactions.get(accountId, [])
        return [t for t in transactions if t.get("cardId") == cardId]

    @mcp.tool(name="getLastTransactions", description="Get the last transactions for an account")
    def get_last_transactions(accountId: str) -> list:
        return sorted(
            last_transactions.get(accountId, []),
            key=lambda t: t["timestamp"],
            reverse=True,
        )

    mcp_app = mcp.http_app(path="/mcp")
    app = FastAPI(title="Mock Transaction MCP Server", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)
    return app


def _create_payment_mcp_app() -> FastAPI:
    """Create a mock Payment MCP server with a single processPayment tool."""
    mcp = FastMCP("Payment MCP Server")

    @mcp.tool(name="processPayment", description="Submit a payment request")
    def process_payment(
        account_id: str,
        amount: float,
        description: str,
        timestamp: str,
        recipient_name: str | None = None,
        recipient_bank_code: str | None = None,
        payment_type: str | None = None,
        card_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> dict:
        if not account_id or not account_id.isdigit():
            return {"status": "error", "message": "Invalid accountId"}
        if payment_type == "CreditCard" and not card_id:
            return {"status": "error", "message": "cardId is required for CreditCard payments"}
        return {"status": "ok"}

    mcp_app = mcp.http_app(path="/mcp")
    app = FastAPI(title="Mock Payment MCP Server", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)
    return app


# ---------------------------------------------------------------------------
# Helper: start a uvicorn server in a background thread on a free port
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _BackgroundServer:
    """Run a uvicorn ASGI server in a daemon thread."""

    def __init__(self, app: FastAPI, port: int):
        self.config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.server.run, daemon=True)
        self._thread.start()
        # Wait until the server is accepting connections
        import time
        for _ in range(50):
            if self.server.started:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        self.server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def parse_sse_events(raw_body: str) -> List[dict]:
    """Parse an SSE text body into a list of JSON event dicts.

    Each SSE frame looks like:
        data: {"type":"...", ...}\n\n

    Some frames may contain stream_options or other metadata.
    Lines that are not ``data:`` prefixed are ignored.
    """
    events: List[dict] = []
    for line in raw_body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass  # skip malformed lines
    return events


def get_events_by_type(events: List[dict], event_type: str) -> List[dict]:
    """Filter parsed SSE events by their ``type`` field."""
    return [e for e in events if e.get("type") == event_type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mock_mcp_ports():
    """Allocate free ports for the mock MCP servers."""
    return {
        "account": _find_free_port(),
        "transaction": _find_free_port(),
        "payment": _find_free_port(),
    }


@pytest.fixture(scope="module")
def mock_mcp_servers(mock_mcp_ports):
    """Start mock Account, Transaction, and Payment MCP servers for the whole test module."""
    account_app = _create_account_mcp_app()
    transaction_app = _create_transaction_mcp_app()
    payment_app = _create_payment_mcp_app()

    account_srv = _BackgroundServer(account_app, mock_mcp_ports["account"])
    transaction_srv = _BackgroundServer(transaction_app, mock_mcp_ports["transaction"])
    payment_srv = _BackgroundServer(payment_app, mock_mcp_ports["payment"])

    account_srv.start()
    transaction_srv.start()
    payment_srv.start()

    yield mock_mcp_ports

    account_srv.stop()
    transaction_srv.stop()
    payment_srv.stop()


@pytest.fixture(scope="module")
def chatkit_app(mock_mcp_servers):
    """Create the FastAPI application with MCP URLs pointing to mock servers.

    Settings and the DI container are patched **before** the app is created
    so that agents will connect to the in-process mock MCP servers.
    """
    import os

    # Load configuration from .env.dev via the PROFILE mechanism
    os.environ["PROFILE"] = "dev"

    account_port = mock_mcp_servers["account"]
    transaction_port = mock_mcp_servers["transaction"]
    payment_port = mock_mcp_servers["payment"]

    # Override MCP URLs to point to in-process mock servers
    os.environ["ACCOUNT_MCP_URL"] = f"http://127.0.0.1:{account_port}/mcp"
    os.environ["TRANSACTION_MCP_URL"] = f"http://127.0.0.1:{transaction_port}/mcp"
    os.environ["PAYMENT_MCP_URL"] = f"http://127.0.0.1:{payment_port}/mcp"
    # Disable Application Insights telemetry during tests
    os.environ["ENABLE_OTEL"] = "false"
    os.environ.pop("APPLICATIONINSIGHTS_CONNECTION_STRING", None)

    # Settings will load from .env.dev for Azure OpenAI config; verify it's present
    from app.config.settings import Settings
    test_settings = Settings()

    if not test_settings.AZURE_OPENAI_ENDPOINT:
        pytest.skip(
            "AZURE_OPENAI_ENDPOINT is not configured. "
            "Ensure .env.dev has AZURE_OPENAI_ENDPOINT set to run integration tests."
        )

    # Now import and create the app — settings will read .env.dev + overrides above
    from app.main_chatkit_server import create_app

    return create_app()


@pytest.fixture()
async def client(chatkit_app):
    """Yield an httpx AsyncClient wired to the chatkit ASGI app."""
    from asgi_lifespan import LifespanManager

    async with LifespanManager(chatkit_app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatkitNewThreadFlow:
    """Flow 1 – New Thread first user message.

    Validates the full SSE event sequence:
    1. thread.created
    2. thread.item.done  (echoes the user message)
    3. progress_update(s)
    4. thread.item.added  (tasks: handoff, tool calls, assistant message)
    5. thread.item.updated (text streaming deltas)
    6. thread.item.done  (final assistant message)
    """


    @pytest.mark.asyncio
    async def test_new_thread_event_flow(self, client: AsyncClient) -> None:
        """Validate the full SSE event sequence for a new thread asking about Contoso payments."""
        request_body = {
            "type": "threads.create",
            "params": {
                "input": {
                    "content": [{"type": "input_text", "text": "when was last time I paid contoso?"}],
                    "attachments": [],
                    "quoted_text": "",
                    "inference_options": {},
                },
            },
        }

        response = await client.post("/chatkit", json=request_body, timeout=120)
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        assert len(events) > 0, "Should receive at least one SSE event"

        event_types = [e.get("type") for e in events]
        print(f"\n--- Received {len(events)} SSE events ---")
        for i, evt in enumerate(events):
            evt_type = evt.get("type", "?")
            preview = json.dumps(evt, default=str)[:200]
            print(f"  [{i}] {evt_type}: {preview}")

        # 1) First event must be thread.created
        assert event_types[0] == "thread.created", (
            f"First event should be 'thread.created', got '{event_types[0]}'"
        )
        thread_created = events[0]
        thread_id = thread_created["thread"]["id"]
        assert thread_id, "thread.created must include a thread id"

        # 2) Second event must be thread.item.done echoing the user message
        assert event_types[1] == "thread.item.done", (
            f"Second event should be 'thread.item.done' (user message), got '{event_types[1]}'"
        )
        user_message_event = events[1]
        assert user_message_event["item"]["type"] == "user_message"
        user_text = user_message_event["item"]["content"][0]["text"]
        assert "contoso" in user_text.lower(), "User message should contain the query"

        # 3) At least one progress_update must appear
        progress_events = get_events_by_type(events, "progress_update")
        assert len(progress_events) >= 1, "Expected at least one progress_update event"

        # 4) task events (thread.item.added with type=task) should appear
        task_added_events = [
            e for e in events
            if e.get("type") == "thread.item.added"
            and e.get("item", {}).get("type") == "task"
        ]
        assert len(task_added_events) >= 1, "Expected at least one task event from tool calls"

        # Verify we see agent handoff and tool-call tasks
        task_titles = [
            e["item"].get("task", {}).get("title", "")
            for e in task_added_events
            if "task" in e.get("item", {})
        ]
        print(f"\n--- Task titles ---")
        for t in task_titles:
            print(f"  • {t}")

        # Should see a handoff to TransactionHistoryAgent (or similar)
        # Title may be absent for some agent types (e.g. foundry_v2)
        if any(t for t in task_titles):
            has_handoff = any("Connected to" in t for t in task_titles)
            assert has_handoff, (
                f"Expected a 'Connected to ...' handoff task, got: {task_titles}"
            )

            # Should see account lookup tool call
            has_account_lookup = any(
                "account" in t.lower() or "retrieved" in t.lower()
                for t in task_titles
            )
            assert has_account_lookup, (
                f"Expected an account lookup task, got: {task_titles}"
            )

        # 5) Assistant message events
        assistant_added_events = [
            e for e in events
            if e.get("type") == "thread.item.added"
            and e.get("item", {}).get("type") == "assistant_message"
        ]
        assert len(assistant_added_events) >= 1, "Expected at least one assistant_message added event"

        # Text streaming deltas
        text_delta_events = get_events_by_type(events, "thread.item.updated")
        assert len(text_delta_events) >= 1, "Expected text streaming delta events"
        # Check delta structure
        first_delta = text_delta_events[0]
        assert "update" in first_delta
        assert first_delta["update"]["type"] == "assistant_message.content_part.text_delta"
        assert "delta" in first_delta["update"]

        # 6) Final thread.item.done for the assistant message
        done_events = get_events_by_type(events, "thread.item.done")
        assistant_done_events = [
            e for e in done_events
            if e.get("item", {}).get("type") == "assistant_message"
        ]
        assert len(assistant_done_events) >= 1, "Expected a final thread.item.done for assistant_message"

        final_message = assistant_done_events[-1]
        final_text = final_message["item"]["content"][0]["text"]
        print(f"\n--- Final assistant response (first 500 chars) ---\n{final_text[:500]}")

        # The assistant should mention Contoso in its response
        assert "contoso" in final_text.lower(), (
            "Assistant response should mention 'Contoso' since we asked about Contoso payments"
        )


class TestChatkitMultiTurnConversation:
    """Flow 2 – Multi-turn conversation within the same thread.

    Validates that a follow-up message (threads.add_user_message) on an
    existing thread preserves conversation context:
    1. First message creates the thread and asks about Contoso payments.
    2. Second message says "what about ACME" and the agent should
       understand the user still means *transactions* related to ACME.
    """

    @pytest.mark.asyncio
    async def test_follow_up_message_preserves_context(self, client: AsyncClient) -> None:
        """Send two messages in the same thread and verify the agent keeps context."""

        # ── Turn 1: create thread with initial question ──────────────
        create_body = {
            "type": "threads.create",
            "params": {
                "input": {
                    "content": [{"type": "input_text", "text": "when was last time I paid contoso?"}],
                    "attachments": [],
                    "quoted_text": "",
                    "inference_options": {},
                },
            },
        }

        turn1_response = await client.post("/chatkit", json=create_body, timeout=120)
        assert turn1_response.status_code == 200

        turn1_events = parse_sse_events(turn1_response.text)
        assert len(turn1_events) > 0, "Turn 1 should produce SSE events"

        # Extract thread_id from thread.created
        thread_created = turn1_events[0]
        assert thread_created.get("type") == "thread.created"
        thread_id = thread_created["thread"]["id"]
        assert thread_id, "thread.created must include a thread id"

        print(f"\n--- Turn 1: thread created {thread_id}, {len(turn1_events)} events ---")

        # ── Turn 2: follow-up in same thread ─────────────────────────
        follow_up_body = {
            "type": "threads.add_user_message",
            "params": {
                "input": {
                    "content": [{"type": "input_text", "text": "what about ACME"}],
                    "attachments": [],
                    "quoted_text": "",
                    "inference_options": {},
                },
                "thread_id": thread_id,
            },
        }

        turn2_response = await client.post("/chatkit", json=follow_up_body, timeout=120)
        assert turn2_response.status_code == 200

        turn2_events = parse_sse_events(turn2_response.text)
        assert len(turn2_events) > 0, "Turn 2 should produce SSE events"

        turn2_types = [e.get("type") for e in turn2_events]
        print(f"\n--- Turn 2: {len(turn2_events)} SSE events ---")
        for i, evt in enumerate(turn2_events):
            evt_type = evt.get("type", "?")
            preview = json.dumps(evt, default=str)[:200]
            print(f"  [{i}] {evt_type}: {preview}")

        # Turn 2 should NOT have thread.created (thread already exists)
        assert "thread.created" not in turn2_types, (
            "Follow-up message should not create a new thread"
        )

        # First event should echo the user message
        assert turn2_types[0] == "thread.item.done", (
            f"First turn-2 event should be 'thread.item.done' (user message), got '{turn2_types[0]}'"
        )
        user_msg = turn2_events[0]
        assert user_msg["item"]["type"] == "user_message"
        assert user_msg["item"]["thread_id"] == thread_id, "User message must be on the same thread"
        assert "acme" in user_msg["item"]["content"][0]["text"].lower()

        # Should have progress updates
        progress_events = get_events_by_type(turn2_events, "progress_update")
        assert len(progress_events) >= 1, "Expected at least one progress_update in turn 2"

        # Should have task events (tool calls for ACME lookup)
        task_events = [
            e for e in turn2_events
            if e.get("type") == "thread.item.added"
            and e.get("item", {}).get("type") == "task"
        ]
        assert len(task_events) >= 1, "Expected at least one task event in turn 2"

        # Should have an assistant message
        assistant_done_events = [
            e for e in get_events_by_type(turn2_events, "thread.item.done")
            if e.get("item", {}).get("type") == "assistant_message"
        ]
        assert len(assistant_done_events) >= 1, "Expected a final assistant_message in turn 2"

        final_text = assistant_done_events[-1]["item"]["content"][0]["text"]
        print(f"\n--- Turn 2 final response (first 500 chars) ---\n{final_text[:500]}")

        # The agent should understand "what about ACME" means transactions for ACME
        assert "acme" in final_text.lower(), (
            "Assistant response should mention 'ACME' — the agent must carry forward "
            "the transaction inquiry context from turn 1"
        )


class TestChatkitPaymentFlow:
    """Flow 3 – Multi-turn payment with human-in-the-loop approval.

    Canonical flow:
    1. User requests to pay a bill (amount, payee, invoice id, date).
    2. Server checks bill hasn't been paid, asks for payment method.
    3. User selects rechargeable visa card.
    4. Server validates card funds, asks confirmation → may emit client_widget
       (tool_approval_request) directly after method selection.
    5. If the agent asks for textual confirmation first, user says "proceed".
    6. Server emits client_widget (tool_approval_request) for processPayment.
    7. User approves via threads.custom_action.
    8. Server confirms payment was processed.

    The LLM may compress steps 2-4 so the test is flexible about when the
    approval widget appears.
    """

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _send_message(thread_id: str, text: str) -> dict:
        """Build a threads.add_user_message request body."""
        return {
            "type": "threads.add_user_message",
            "params": {
                "input": {
                    "content": [{"type": "input_text", "text": text}],
                    "attachments": [],
                    "quoted_text": "",
                    "inference_options": {},
                },
                "thread_id": thread_id,
            },
        }

    @staticmethod
    def _find_approval_widget(events: list[dict]) -> dict | None:
        """Return the first client_widget / tool_approval_request event, or None."""
        for e in events:
            if (
                e.get("type") == "thread.item.done"
                and e.get("item", {}).get("type") == "client_widget"
                and e.get("item", {}).get("name") == "tool_approval_request"
            ):
                return e
        return None

    @staticmethod
    def _build_approval_action(widget_event: dict, thread_id: str) -> dict:
        """Build a threads.custom_action approval request from a widget event."""
        item = widget_event["item"]
        args = item["args"]
        return {
            "type": "threads.custom_action",
            "params": {
                "item_id": item["id"],
                "action": {
                    "type": "approval",
                    "payload": {
                        "tool_name": args["tool_name"],
                        "tool_args": args["tool_args"],
                        "approved": True,
                        "call_id": args["call_id"],
                        "request_id": args.get("request_id"),
                    },
                    "handler": "server",
                    "loadingBehavior": "auto",
                },
                "thread_id": thread_id,
            },
        }

    # -- test -------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_payment_approval_flow(self, client: AsyncClient) -> None:
        """Full payment flow: bill request → method selection → approval → confirmation."""

        # ── Turn 1: create thread – user wants to pay a bill ─────────
        create_body = {
            "type": "threads.create",
            "params": {
                "input": {
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "I need to pay a bill. "
                                "Payee: Mario The Plumber, "
                                "Invoice ID: 1561672, "
                                "Invoice date: 2026-03-28, "
                                "Amount: 100 EUR"
                            ),
                        }
                    ],
                    "attachments": [],
                    "quoted_text": "",
                    "inference_options": {},
                },
            },
        }

        turn1 = await client.post("/chatkit", json=create_body, timeout=120)
        assert turn1.status_code == 200
        turn1_events = parse_sse_events(turn1.text)
        assert len(turn1_events) > 0

        thread_id = turn1_events[0]["thread"]["id"]
        print(f"\n--- Payment Turn 1: thread {thread_id}, {len(turn1_events)} events ---")

        # Collect all events across turns to find the approval widget
        all_events = list(turn1_events)
        approval_widget = self._find_approval_widget(turn1_events)

        # ── Turn 2: select payment method (if agent asked) ───────────
        if approval_widget is None:
            turn2 = await client.post(
                "/chatkit",
                json=self._send_message(thread_id, "use my rechargeable visa card"),
                timeout=120,
            )
            assert turn2.status_code == 200
            turn2_events = parse_sse_events(turn2.text)
            all_events.extend(turn2_events)
            print(f"--- Payment Turn 2 (card selection): {len(turn2_events)} events ---")
            approval_widget = self._find_approval_widget(turn2_events)

        # ── Turn 3: confirm payment (if agent asked for text confirm) ─
        if approval_widget is None:
            turn3 = await client.post(
                "/chatkit",
                json=self._send_message(thread_id, "Yes, proceed with the payment"),
                timeout=120,
            )
            assert turn3.status_code == 200
            turn3_events = parse_sse_events(turn3.text)
            all_events.extend(turn3_events)
            print(f"--- Payment Turn 3 (proceed): {len(turn3_events)} events ---")
            approval_widget = self._find_approval_widget(turn3_events)

        # ── Turn 4: additional nudge if agent still hasn't triggered approval ─
        if approval_widget is None:
            turn4 = await client.post(
                "/chatkit",
                json=self._send_message(thread_id, "go ahead and submit the payment now"),
                timeout=120,
            )
            assert turn4.status_code == 200
            turn4_events = parse_sse_events(turn4.text)
            all_events.extend(turn4_events)
            print(f"--- Payment Turn 4 (nudge): {len(turn4_events)} events ---")
            approval_widget = self._find_approval_widget(turn4_events)

        # At this point we MUST have an approval widget
        assert approval_widget is not None, (
            "Expected a tool_approval_request client_widget for processPayment "
            "but none appeared across all turns. Event types seen: "
            + str([e.get("type") for e in all_events])
        )

        widget_args = approval_widget["item"]["args"]
        print(f"\n--- Approval widget received ---")
        print(f"  tool_name: {widget_args['tool_name']}")
        print(f"  tool_args: {widget_args['tool_args']}")
        print(f"  call_id:   {widget_args['call_id']}")

        # Validate the approval widget contents
        assert widget_args["tool_name"] == "processPayment"
        # tool_args may be a JSON string or dict
        tool_args = widget_args["tool_args"]
        if isinstance(tool_args, str):
            tool_args = json.loads(tool_args)
        assert float(tool_args["amount"]) == 100.0, (
            f"Expected payment amount 100, got {tool_args['amount']}"
        )

        # ── Approval: user approves the payment ─────────────────────
        approval_body = self._build_approval_action(approval_widget, thread_id)
        approval_response = await client.post("/chatkit", json=approval_body, timeout=120)
        assert approval_response.status_code == 200

        approval_events = parse_sse_events(approval_response.text)
        print(f"\n--- Approval response: {len(approval_events)} events ---")
        for i, evt in enumerate(approval_events):
            evt_type = evt.get("type", "?")
            preview = json.dumps(evt, default=str)[:200]
            print(f"  [{i}] {evt_type}: {preview}")

        # Should have a processPayment task event
        task_events = [
            e for e in approval_events
            if e.get("type") == "thread.item.added"
            and e.get("item", {}).get("type") == "task"
        ]
        task_titles = [
            e["item"]["task"]["title"]
            for e in task_events
            if "task" in e.get("item", {})
        ]
        print(f"\n--- Approval task titles ---")
        for t in task_titles:
            print(f"  • {t}")

        # Should have a final assistant message confirming payment
        assistant_done = [
            e for e in get_events_by_type(approval_events, "thread.item.done")
            if e.get("item", {}).get("type") == "assistant_message"
        ]
        assert len(assistant_done) >= 1, (
            "Expected an assistant_message after payment approval"
        )

        final_text = assistant_done[-1]["item"]["content"][0]["text"]
        print(f"\n--- Payment confirmation (first 500 chars) ---\n{final_text[:500]}")

        # The assistant should confirm the payment was processed
        confirmation_keywords = ["paid", "processed", "confirmed", "successful", "submitted", "completed", "approved"]
        has_confirmation = any(kw in final_text.lower() for kw in confirmation_keywords)
        assert has_confirmation, (
            f"Expected payment confirmation in assistant response. Got: {final_text[:300]}"
        )