"""Pytest configuration, shared fixtures, and mock GCP clients."""

import os
import pytest
from unittest.mock import MagicMock
from pathlib import Path


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Provides a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "processed").mkdir(parents=True)
    (data_dir / "vector_index").mkdir(parents=True)
    return data_dir


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch, test_data_dir: Path):
    """Sets standard test environment variables."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project-123")
    monkeypatch.setenv("GCP_REGION", "us-central1")
    monkeypatch.setenv("DOCUMENT_AI_PROCESSOR_ID", "test-processor-456")
    monkeypatch.setenv("LOCAL_VECTOR_INDEX_DIR", str(test_data_dir / "vector_index"))
    monkeypatch.setenv("PROCESSED_DATA_DIR", str(test_data_dir / "processed"))
    monkeypatch.setenv("RAW_DATA_DIR", str(test_data_dir / "raw"))
