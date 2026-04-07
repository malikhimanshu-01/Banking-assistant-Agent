import mimetypes
import logging
from io import BytesIO
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import  StreamingResponse, FileResponse
from starlette.responses import JSONResponse
from dependency_injector.wiring import Provide, inject
from app.config.settings import settings

# Foundry Agent based dependencies
#from app.config.container_foundry import Container

# Azure Chat based agents dependencies
from app.config.container_azure_chat import Container

if settings.AGENTS_TYPE == "azure_chat":
    from app.config.container_azure_chat import Container
elif settings.AGENTS_TYPE == "foundry_v2":
    from app.config.container_foundry_v2 import Container

from app.helpers.blob_proxy import BlobStorageProxy
from app.helpers.user_profile_helper import UserProfileHelper
from .sqllite_store import SQLiteStore
from .cosmosdb_store import CosmosDBStore

router = APIRouter()
logger = logging.getLogger(__name__)

# Fallback SQLite store used when CosmosDB is not configured (local dev / tests)
_fallback_sqlite_store = SQLiteStore()


def _resolve_store(cosmosdb_store: CosmosDBStore | None):
    """Return the injected CosmosDB store when available, otherwise SQLite."""
    return cosmosdb_store if cosmosdb_store is not None else _fallback_sqlite_store


@router.post("/upload/{attachment_id}")
@inject
async def upload_file(attachment_id: str, 
                      file: UploadFile = File(...),
                      blob_proxy: BlobStorageProxy = Depends(Provide[Container.blob_proxy]),
                      cosmosdb_store: CosmosDBStore = Depends(Provide[Container.cosmosdb_store])):
    """Handle file upload for two-phase upload.

    The client POSTs the file bytes here after creating the attachment
    via the ChatKit attachments.create endpoint.
    """
    logger.info(f"Receiving file upload for attachment: {attachment_id}")

    try:
        # Read file contents
        contents = await file.read()

        # Save to azure storage
        blob_proxy.store_file(contents, attachment_id)

        logger.info(f"Saved {len(contents)} bytes for {file.filename} as attachment {attachment_id} in blob storage")

        # Load the attachment metadata from the data store
        store = _resolve_store(cosmosdb_store)
        attachment = await store.load_attachment(attachment_id, {"user_id": UserProfileHelper.get_user_id()})

        # Clear the upload_descriptor since upload is complete
        attachment.upload_descriptor = None

        # Save the updated attachment back to the store
        await store.save_attachment(attachment, {"user_id": UserProfileHelper.get_user_id()})

        # Return the attachment metadata as JSON
        return JSONResponse(content=attachment.model_dump(mode="json"))

    except Exception as e:
        logger.error(f"Error uploading file for attachment {attachment_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Failed to upload file: {str(e)}"})


@router.get("/preview/{attachment_id}")
@inject
async def preview_image(attachment_id: str,
                         blob_proxy: BlobStorageProxy = Depends(Provide[Container.blob_proxy])):
    """Serve image preview/thumbnail.

    For simplicity, this serves the full image. In production, you should
    generate and cache thumbnails.
    """
    logger.debug(f"Serving preview for attachment: {attachment_id}")

    try:
        try:
            file_bytes = blob_proxy.get_file_as_bytes(attachment_id)
        except Exception:
            return JSONResponse(status_code=404, content={"error": "File not found in blob storage for " + attachment_id})

    
        # Guess media type from the attachment_id extension; fall back to octet-stream
        media_type = mimetypes.guess_type(attachment_id)[0] or "application/octet-stream"

        return StreamingResponse(
            BytesIO(file_bytes),
            media_type=media_type
        )
        

    except Exception as e:
        logger.error(f"Error serving preview for attachment {attachment_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})