from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.chatkit import attachment_routers
from app.routers.chatkit import chat_routers
from app.config.settings import settings
from app.config.logging import get_logger, setup_logging
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation


enable_instrumentation()

# Azure Chat based dependency injection container
from app.config.container_azure_chat import Container


if settings.AGENTS_TYPE == "azure_chat":
    from app.config.container_azure_chat import Container
elif settings.AGENTS_TYPE == "foundry_v2":
    from app.config.container_foundry_v2 import Container
else:
    raise ValueError(f"Unsupported AGENTS_TYPE: {settings.AGENTS_TYPE}")

def create_app() -> FastAPI:
    # Initialize logging for the app
    setup_logging()
    # Get logger for this module
    logger = get_logger(__name__)

   
    # Setup agent framework observability (skip when no connection string is configured, e.g. integration tests)
    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        if settings.AGENTS_TYPE == "foundry_v2":
            configure_azure_monitor(
                connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
                resource=create_resource(),
                enable_live_metrics=True,
            )
        else:
            configure_azure_monitor(
                connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
                resource=create_resource(),
                enable_live_metrics=True,
            )
            enable_instrumentation()
    else:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set – telemetry disabled")
    
    logger.info(f"Creating FastAPI application: {settings.APP_NAME}")
    
    app = FastAPI(title=settings.APP_NAME)
   
    # Initialize dependency injection container
    container = Container()
    
    # Wire dependencies to modules that need them
    container.wire(modules=[chat_routers,attachment_routers])
    
    # Store container in app state for potential cleanup
    app.state.container = container

    # Use FastAPI lifespan for startup and shutdown events
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        logger.info("Shutting down application...")
        container.unwire()

    app.router.lifespan_context = lifespan

    # Include routers
    app.include_router(chat_routers.router, tags=["chat"])
    app.include_router(attachment_routers.router, tags=["attachments"])



    logger.info("FastAPI application created successfully")
    logger.info(f"Agents type: {settings.AGENTS_TYPE}")
    app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    return app


app = create_app()
