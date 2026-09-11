"""FastAPI application routes for Multimodal CRAG operations."""

import logging
import shutil
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from config.settings import settings
from src.api.schemas import (
    CitationItem,
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from src.crag.graph import run_crag
from src.ingestion.pipeline import IngestionPipeline
from src.vector_store.indexer import MultimodalIndexer
from src.vector_store.local_store import LocalVectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["CRAG Operations"])

# Shared vector store instance for serving
_vector_store: LocalVectorStore = LocalVectorStore()


def get_vector_store() -> LocalVectorStore:
    """Dependency injector for LocalVectorStore."""
    return _vector_store


@router.get("/health", response_model=HealthResponse)
def health_check(store: LocalVectorStore = Depends(get_vector_store)) -> HealthResponse:
    """Readiness and health probe endpoint."""
    vector_count = len(store.embeddings) if store.embeddings is not None else 0
    return HealthResponse(
        status="healthy",
        service="multimodal-crag-platform",
        version="1.0.0",
        gcp_project=settings.gcp_project_id,
        vector_count=vector_count,
    )


@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    store: LocalVectorStore = Depends(get_vector_store),
) -> QueryResponse:
    """Executes the Corrective RAG (CRAG) graph on indexed enterprise documents."""
    start_time = time.perf_counter()

    try:
        final_state = run_crag(query=request.query, vector_store=store)
    except Exception as e:
        logger.exception(f"CRAG execution failed for query: '{request.query}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRAG execution error: {str(e)}",
        )

    duration_ms = (time.perf_counter() - start_time) * 1000.0

    raw_citations = final_state.get("citations", [])
    formatted_citations: List[CitationItem] = []
    for c in raw_citations:
        formatted_citations.append(
            CitationItem(
                chunk_id=c.get("chunk_id"),
                doc_id=c.get("doc_id"),
                page_number=c.get("page_number"),
                content_type=c.get("content_type"),
                score=c.get("score"),
                image_path=c.get("image_path"),
                source=c.get("source"),
            )
        )

    # Collect images referenced in extracted_images or citations
    images = list(final_state.get("extracted_images", []))

    trace = list(final_state.get("execution_trace", [])) if request.include_trace else []

    return QueryResponse(
        query=request.query,
        generation=final_state.get("final_response", ""),
        citations=formatted_citations,
        images=images,
        crag_status=final_state.get("overall_grade", "NOT_RELEVANT"),
        retries=final_state.get("retry_count", 0),
        trace=trace,
        latency_ms=round(duration_ms, 2),
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document_file(
    file: UploadFile = File(...),
    store: LocalVectorStore = Depends(get_vector_store),
) -> IngestResponse:
    """Uploads and ingests a PDF document through Document AI and multimodal indexing."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported for multimodal ingestion.",
        )

    raw_dir = settings.raw_data_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    target_path = raw_dir / file.filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store file: {str(e)}",
        )

    try:
        pipeline = IngestionPipeline(raw_dir=raw_dir)
        parsed_doc = pipeline.ingest_document(target_path)

        # Index extracted chunks into the vector store
        indexer = MultimodalIndexer(vector_store=store)
        indexer.index_chunks(parsed_doc.chunks)
    except Exception as e:
        logger.exception(f"Document ingestion failed for {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failed: {str(e)}",
        )

    return IngestResponse(
        status="success",
        doc_id=parsed_doc.doc_id,
        chunks_count=len(parsed_doc.chunks),
        tables_count=len(parsed_doc.tables),
        charts_count=len(parsed_doc.charts),
        message=f"Successfully parsed and indexed {len(parsed_doc.chunks)} multimodal chunks from {file.filename}.",
    )
