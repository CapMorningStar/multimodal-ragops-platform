"""Application Settings and Environment Configuration.

Uses pydantic-settings to strictly validate environment variables,
GCP resource identifiers, model parameters, and budget guardrails.
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VectorStoreBackend(str, Enum):
    LOCAL = "local"
    VERTEX_AI = "vertex_ai"


class Settings(BaseSettings):
    """Configuration schema for the Multimodal CRAG Platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # GCP Core Configuration
    # --------------------------------------------------------------------------
    gcp_project_id: str = Field(
        default="demo-gcp-project",
        description="Google Cloud Platform Project ID.",
    )
    gcp_region: str = Field(
        default="us-central1",
        description="GCP Region for Vertex AI and Cloud Run deployment.",
    )
    google_application_credentials: Optional[str] = Field(
        default=None,
        description="Optional path to local service account credentials JSON.",
    )

    # --------------------------------------------------------------------------
    # Document AI Configuration
    # --------------------------------------------------------------------------
    document_ai_location: str = Field(
        default="us",
        description="Location of the Document AI processor ('us' or 'eu').",
    )
    document_ai_processor_id: str = Field(
        default="mock-processor-id",
        description="Document AI Layout / Form Parser Processor ID.",
    )

    # --------------------------------------------------------------------------
    # Vertex AI Model Endpoints
    # --------------------------------------------------------------------------
    vertex_multimodal_embedding_model: str = Field(
        default="multimodalembedding@001",
        description="Vertex AI Multimodal Embeddings model name.",
    )
    gemini_llm_model: str = Field(
        default="gemini-1.5-flash-002",
        description="Gemini model for grounded synthesis and reasoning.",
    )
    gemini_crag_grader_model: str = Field(
        default="gemini-1.5-flash-002",
        description="Gemini model for evaluating document relevance in CRAG.",
    )

    # --------------------------------------------------------------------------
    # Storage & Local Vector Search (Zero Idle Burn)
    # --------------------------------------------------------------------------
    vector_store_backend: VectorStoreBackend = Field(
        default=VectorStoreBackend.LOCAL,
        description="Vector store backend. Default is 'local' (zero idle cost).",
    )
    local_vector_index_dir: Path = Field(
        default=Path("./data/vector_index"),
        description="Local directory for persistent NumPy/ScaNN vector indexes.",
    )
    processed_data_dir: Path = Field(
        default=Path("./data/processed"),
        description="Directory for extracted text chunks, tables, and cropped charts.",
    )
    raw_data_dir: Path = Field(
        default=Path("./data/raw"),
        description="Directory for raw incoming PDFs.",
    )
    gcs_staging_bucket: Optional[str] = Field(
        default=None,
        description="Optional GCS bucket for staging enterprise documents in production.",
    )

    # --------------------------------------------------------------------------
    # CRAG Agent Parameters
    # --------------------------------------------------------------------------
    retrieval_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of multimodal chunks to retrieve per query.",
    )
    relevance_threshold_high: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Confidence threshold above which retrieved chunks directly proceed to synthesis.",
    )
    relevance_threshold_low: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Confidence threshold below which retrieval falls back to web search.",
    )
    max_rewrite_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum query reformulation retries allowed before fallback.",
    )
    serper_api_key: Optional[str] = Field(
        default=None,
        description="Optional Serper / Google Search API key for web fallback.",
    )

    # --------------------------------------------------------------------------
    # Budget Guardrails
    # --------------------------------------------------------------------------
    budget_limit_usd: float = Field(
        default=300.00,
        description="Hard spending limit in USD for cloud resources.",
    )
    budget_alert_threshold_warn: float = Field(
        default=50.00,
        description="Soft warning threshold in USD.",
    )
    budget_alert_threshold_critical: float = Field(
        default=250.00,
        description="Critical spending threshold in USD.",
    )

    # --------------------------------------------------------------------------
    # Server & Logging
    # --------------------------------------------------------------------------
    api_port: int = Field(default=8000, description="FastAPI server port.")
    ui_port: int = Field(default=8501, description="Streamlit UI server port.")
    log_level: str = Field(default="INFO", description="Logging verbosity.")


# Global settings singleton
settings = Settings()
