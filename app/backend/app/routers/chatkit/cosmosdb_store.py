# Copyright (c) Microsoft. All rights reserved.

"""Azure Cosmos DB (NoSQL) store implementation for ChatKit data persistence.

This module provides a Store implementation backed by Azure Cosmos DB for NoSQL.
It uses the async SDK with AAD/RBAC authentication (DefaultAzureCredential),
follows singleton-client best practices, and partitions data by user_id for
natural tenant isolation and efficient single-partition queries.

Container layout (single Cosmos DB database, three containers):
  - threads:     partition key = /user_id
  - items:       partition key = /user_id
  - attachments: partition key = /user_id
"""

import logging
import uuid
from typing import Any

from azure.cosmos.aio import CosmosClient, ContainerProxy
from chatkit.store import Store, NotFoundError
from chatkit.types import (
    Attachment,
    Page,
    ThreadMetadata,
)
from pydantic import BaseModel

from app.common.chatkit.types import ThreadItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic wrappers – identical to the SQLite store so serialisation round-
# trips through the same schema.
# ---------------------------------------------------------------------------

class ThreadData(BaseModel):
    """Wraps ThreadMetadata for JSON serialisation."""
    thread: ThreadMetadata


class ItemData(BaseModel):
    """Wraps ThreadItem for JSON serialisation."""
    item: ThreadItem


class AttachmentData(BaseModel):
    """Wraps Attachment for JSON serialisation."""
    attachment: Attachment


class CosmosDBStore(Store[dict[str, Any]]):
    """Azure Cosmos DB for NoSQL backed ChatKit store.

    Design decisions
    ================
    * **Partition key = user_id** – every query filters by user_id so all
      operations are single-partition reads/writes (cheapest, fastest).
    * **Async SDK** – the store is consumed from async FastAPI handlers so we
      use ``azure.cosmos.aio``.
    * **RBAC auth** – no connection-string; the caller passes an
      ``azure.identity`` credential (local dev → AzureCliCredential,
      prod → ManagedIdentityCredential with ``AZURE_CLIENT_ID``).
    * **Singleton CosmosClient** – created once in the DI container and shared
      across requests (``sdk-singleton-client`` best practice).

    Required Cosmos DB RBAC role on the identity:
        ``Cosmos DB Built-in Data Contributor`` (00000000-0000-0000-0000-000000000002)
    """

    def __init__(
        self,
        cosmos_client: CosmosClient,
        database_name: str = "chatkit",
    ):
        self._client = cosmos_client
        self._db_name = database_name
        # Lazy-resolved container proxies (set on first use via _ensure_containers)
        self._threads: ContainerProxy | None = None
        self._items: ContainerProxy | None = None
        self._attachments: ContainerProxy | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_containers(self) -> None:
        """Lazily resolve container proxies on first call."""
        if self._threads is not None:
            return
        db = self._client.get_database_client(self._db_name)
        self._threads = db.get_container_client("threads")
        self._items = db.get_container_client("items")
        self._attachments = db.get_container_client("attachments")

    @staticmethod
    def _user_id(context: dict[str, Any]) -> str:
        user_id = context.get("user_id")
        if not user_id:
            raise ValueError("user_id is required in context for CosmosDB store operations")
        return user_id

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def generate_thread_id(self, context: dict[str, Any]) -> str:
        return f"thr_{uuid.uuid4().hex[:8]}"

    def generate_item_id(
        self,
        item_type: str,
        thread: ThreadMetadata,
        context: dict[str, Any],
    ) -> str:
        prefix_map = {
            "message": "msg",
            "tool_call": "tc",
            "task": "tsk",
            "workflow": "wf",
            "attachment": "atc",
        }
        prefix = prefix_map.get(item_type, "itm")
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    async def load_thread(self, thread_id: str, context: dict[str, Any]) -> ThreadMetadata:
        await self._ensure_containers()
        user_id = self._user_id(context)
        try:
            doc = await self._threads.read_item(item=thread_id, partition_key=user_id)
        except Exception:
            raise NotFoundError(f"Thread {thread_id} not found")
        return ThreadData.model_validate_json(doc["data"]).thread

    async def save_thread(self, thread: ThreadMetadata, context: dict[str, Any]) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        thread_data = ThreadData(thread=thread)
        doc = {
            "id": thread.id,
            "user_id": user_id,
            "created_at": thread.created_at.isoformat(),
            "data": thread_data.model_dump_json(),
        }
        await self._threads.upsert_item(doc)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        await self._ensure_containers()
        user_id = self._user_id(context)

        created_after: str | None = None
        if after:
            try:
                after_doc = await self._threads.read_item(item=after, partition_key=user_id)
                created_after = after_doc["created_at"]
            except Exception:
                raise NotFoundError(f"Thread {after} not found")

        comparator = ">" if order == "asc" else "<"
        direction = "ASC" if order == "asc" else "DESC"

        if created_after:
            query = (
                f"SELECT * FROM c WHERE c.user_id = @uid AND c.created_at {comparator} @after "
                f"ORDER BY c.created_at {direction} OFFSET 0 LIMIT @lim"
            )
            params = [
                {"name": "@uid", "value": user_id},
                {"name": "@after", "value": created_after},
                {"name": "@lim", "value": limit + 1},
            ]
        else:
            query = (
                f"SELECT * FROM c WHERE c.user_id = @uid "
                f"ORDER BY c.created_at {direction} OFFSET 0 LIMIT @lim"
            )
            params = [
                {"name": "@uid", "value": user_id},
                {"name": "@lim", "value": limit + 1},
            ]

        results = [doc async for doc in self._threads.query_items(
            query=query,
            parameters=params,
            partition_key=user_id,
        )]

        threads = [ThreadData.model_validate_json(doc["data"]).thread for doc in results]

        has_more = len(threads) > limit
        if has_more:
            threads = threads[:limit]

        return Page[ThreadMetadata](
            data=threads,
            has_more=has_more,
            after=threads[-1].id if threads else None,
        )

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)

        try:
            await self._threads.delete_item(item=thread_id, partition_key=user_id)
        except Exception:
            pass  # Idempotent delete

        # Also delete all items belonging to this thread
        query = "SELECT c.id FROM c WHERE c.user_id = @uid AND c.thread_id = @tid"
        params = [
            {"name": "@uid", "value": user_id},
            {"name": "@tid", "value": thread_id},
        ]
        async for doc in self._items.query_items(query=query, parameters=params, partition_key=user_id):
            await self._items.delete_item(item=doc["id"], partition_key=user_id)

    # ------------------------------------------------------------------
    # Thread items
    # ------------------------------------------------------------------

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadItem]:
        await self._ensure_containers()
        user_id = self._user_id(context)

        created_after: str | None = None
        if after:
            try:
                after_doc = await self._items.read_item(item=after, partition_key=user_id)
                created_after = after_doc["created_at"]
            except Exception:
                raise NotFoundError(f"Item {after} not found")

        comparator = ">" if order == "asc" else "<"
        direction = "ASC" if order == "asc" else "DESC"

        if created_after:
            query = (
                f"SELECT * FROM c WHERE c.user_id = @uid AND c.thread_id = @tid "
                f"AND c.created_at {comparator} @after "
                f"ORDER BY c.created_at {direction} OFFSET 0 LIMIT @lim"
            )
            params = [
                {"name": "@uid", "value": user_id},
                {"name": "@tid", "value": thread_id},
                {"name": "@after", "value": created_after},
                {"name": "@lim", "value": limit + 1},
            ]
        else:
            query = (
                f"SELECT * FROM c WHERE c.user_id = @uid AND c.thread_id = @tid "
                f"ORDER BY c.created_at {direction} OFFSET 0 LIMIT @lim"
            )
            params = [
                {"name": "@uid", "value": user_id},
                {"name": "@tid", "value": thread_id},
                {"name": "@lim", "value": limit + 1},
            ]

        results = [doc async for doc in self._items.query_items(
            query=query,
            parameters=params,
            partition_key=user_id,
        )]

        items = [ItemData.model_validate_json(doc["data"]).item for doc in results]

        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        return Page[ThreadItem](
            data=items,
            has_more=has_more,
            after=items[-1].id if items else None,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        item_data = ItemData(item=item)
        doc = {
            "id": item.id,
            "thread_id": thread_id,
            "user_id": user_id,
            "created_at": item.created_at.isoformat(),
            "data": item_data.model_dump_json(),
        }
        await self._items.upsert_item(doc)

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict[str, Any]) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        item_data = ItemData(item=item)
        doc = {
            "id": item.id,
            "thread_id": thread_id,
            "user_id": user_id,
            "created_at": item.created_at.isoformat(),
            "data": item_data.model_dump_json(),
        }
        await self._items.upsert_item(doc)

    async def load_item(self, thread_id: str, item_id: str, context: dict[str, Any]) -> ThreadItem:
        await self._ensure_containers()
        user_id = self._user_id(context)
        try:
            doc = await self._items.read_item(item=item_id, partition_key=user_id)
        except Exception:
            raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
        return ItemData.model_validate_json(doc["data"]).item

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        try:
            await self._items.delete_item(item=item_id, partition_key=user_id)
        except Exception:
            pass  # Idempotent delete

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def save_attachment(self, attachment: Attachment, context: dict[str, Any]) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        attachment_data = AttachmentData(attachment=attachment)
        doc = {
            "id": attachment.id,
            "user_id": user_id,
            "data": attachment_data.model_dump_json(),
        }
        await self._attachments.upsert_item(doc)

    async def load_attachment(self, attachment_id: str, context: dict[str, Any]) -> Attachment:
        await self._ensure_containers()
        user_id = self._user_id(context)
        try:
            doc = await self._attachments.read_item(item=attachment_id, partition_key=user_id)
        except Exception:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return AttachmentData.model_validate_json(doc["data"]).attachment

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        await self._ensure_containers()
        user_id = self._user_id(context)
        try:
            await self._attachments.delete_item(item=attachment_id, partition_key=user_id)
        except Exception:
            pass  # Idempotent delete
