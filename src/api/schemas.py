"""Pydantic schemas for the Multimodal CRAG Serving API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Payload for user query invocation."""

    query: str = Field(..., description="User query or question", min_length=2)
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    include_trace: bool = Field(default=True, description="Whether to include LangGraph execution trace")


class CitationItem(BaseModel):
    """Citation metadata for grounded generation."""

    chunk_id: Optional[str] = None
    doc_id: Optional[str] = None
    page_number: Optional[int] = None
    content_type: Optional[str] = None
    score: Optional[float] = None
    image_path: Optional[str] = None
    source: Optional[str] = None


class QueryResponse(BaseModel):
    """CRAG Grounded answer response."""

    query: str
    generation: str
    citations: List[CitationItem] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    crag_status: str
    retries: int = 0
    trace: List[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None


class IngestResponse(BaseModel):
    """Response returned upon document ingestion."""

    status: str = "success"
    doc_id: str
    chunks_count: int
    tables_count: int
    charts_count: int
    message: str


class HealthResponse(BaseModel):
    """System health and readiness probe schema."""

    status: str = "healthy"
    service: str = "multimodal-crag-platform"
    version: str = "1.0.0"
    gcp_project: str
    vector_count: int
