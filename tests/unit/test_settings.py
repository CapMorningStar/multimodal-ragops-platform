"""Unit tests for configuration loading and validation."""

import pytest
from pydantic import ValidationError
from config.settings import Settings, VectorStoreBackend


def test_default_settings():
    """Verify that default settings instantiate with expected defaults."""
    cfg = Settings()
    assert cfg.gcp_region == "us-central1"
    assert cfg.vector_store_backend == VectorStoreBackend.LOCAL
    assert cfg.budget_limit_usd == 300.00
    assert cfg.retrieval_top_k == 5
    assert cfg.relevance_threshold_high == 0.75
    assert cfg.relevance_threshold_low == 0.40


def test_custom_settings_override(mock_env):
    """Verify that environment variables properly override settings."""
    cfg = Settings()
    assert cfg.gcp_project_id == "test-project-123"
    assert cfg.document_ai_processor_id == "test-processor-456"


def test_invalid_retrieval_top_k():
    """Verify that invalid top_k values raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(retrieval_top_k=0)

    with pytest.raises(ValidationError):
        Settings(retrieval_top_k=100)


def test_invalid_relevance_thresholds():
    """Verify that threshold values outside [0.0, 1.0] raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(relevance_threshold_high=1.5)

    with pytest.raises(ValidationError):
        Settings(relevance_threshold_low=-0.1)


def test_budget_guardrails():
    """Verify that budget guardrails have logical values."""
    cfg = Settings()
    assert cfg.budget_alert_threshold_warn < cfg.budget_alert_threshold_critical
    assert cfg.budget_alert_threshold_critical <= cfg.budget_limit_usd
