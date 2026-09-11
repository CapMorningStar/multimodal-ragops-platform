"""FastAPI Application Factory for Multimodal CRAGOps Platform."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.logging_config import configure_logging
from config.settings import settings
from src.api.routes import router

configure_logging(log_level=settings.log_level)
logger = logging.getLogger("multimodal_crag.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for application startup and shutdown."""
    logger.info("Starting Enterprise Multimodal CRAGOps API Service...")
    logger.info(f"GCP Project ID: {settings.gcp_project_id} | Region: {settings.gcp_region}")
    logger.info(f"Document AI Processor: {settings.document_ai_processor_id}")
    logger.info(f"Embedding Model: {settings.vertex_multimodal_embedding_model} (1408-dim)")
    logger.info(f"LLM Generation Model: {settings.gemini_llm_model}")

    # Ensure required directories exist
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.local_vector_index_dir.mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down Multimodal CRAGOps API Service.")


def create_app() -> FastAPI:
    """Builds and configures the main FastAPI application instance."""
    app = FastAPI(
        title="Enterprise Corrective Multimodal RAGOps Platform",
        description=(
            "Production-grade Multimodal Corrective RAG (CRAG) system leveraging Google Cloud "
            "Document AI Layout Parser, Vertex AI Multimodal Embeddings (1408-dim), and Gemini Flash."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(router)

    @app.get("/", tags=["Root"])
    def root():
        return {
            "platform": "Enterprise Corrective Multimodal RAGOps Platform",
            "version": "1.0.0",
            "status": "operational",
            "docs": "/docs",
            "health": "/v1/health",
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled server error at {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "detail": str(exc)},
        )

    return app


app = create_app()
