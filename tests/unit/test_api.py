"""Unit tests for FastAPI endpoints."""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from src.api.app import app


@pytest.fixture
def client():
    """Provides a TestClient instance."""
    return TestClient(app)


def test_root_endpoint(client: TestClient):
    """Verify root / returns 200 and operational status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["docs"] == "/docs"


def test_health_check_endpoint(client: TestClient):
    """Verify /v1/health returns healthy status."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "vector_count" in data


def test_query_endpoint(client: TestClient):
    """Verify /v1/query returns structured response."""
    mock_crag_result = {
        "query": "What is the revenue?",
        "final_response": "Operating revenue was $120M in fiscal 2026.",
        "citations": [
            {
                "chunk_id": "chunk_001",
                "doc_id": "report_2026",
                "page_number": 1,
                "content_type": "text",
                "score": 0.88,
            }
        ],
        "extracted_images": [],
        "overall_grade": "RELEVANT",
        "retry_count": 0,
        "execution_trace": ["retrieve:local_search", "grade:relevant", "generate:grounded_synthesis"],
    }

    with patch("src.api.routes.run_crag", return_value=mock_crag_result):
        payload = {"query": "What is the revenue?", "top_k": 3, "include_trace": True}
        response = client.post("/v1/query", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is the revenue?"
        assert "revenue was $120M" in data["generation"]
        assert len(data["citations"]) == 1
        assert data["crag_status"] == "RELEVANT"
        assert len(data["trace"]) == 3
        assert "latency_ms" in data


def test_ingest_rejects_non_pdf(client: TestClient):
    """Verify /v1/ingest rejects non-PDF files."""
    files = {"file": ("test.txt", b"not a pdf", "text/plain")}
    response = client.post("/v1/ingest", files=files)
    assert response.status_code == 400
    assert "Only PDF" in response.json()["detail"]


def test_ingest_valid_pdf_mocked(client: TestClient):
    """Verify /v1/ingest processes PDF successfully with mock pipeline."""
    mock_parsed_doc = MagicMock()
    mock_parsed_doc.doc_id = "test_doc"
    mock_parsed_doc.chunks = []
    mock_parsed_doc.tables = []
    mock_parsed_doc.charts = []

    with patch("src.api.routes.IngestionPipeline.ingest_document", return_value=mock_parsed_doc), \
         patch("src.api.routes.MultimodalIndexer.index_chunks", return_value=0):

        files = {"file": ("test_doc.pdf", b"%PDF-1.5 sample content", "application/pdf")}
        response = client.post("/v1/ingest", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["doc_id"] == "test_doc"
