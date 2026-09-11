"""Conditional routing logic and transition edges for the CRAG StateGraph."""

import logging
from typing import Literal

from config.settings import settings
from src.crag.state import CRAGState

logger = logging.getLogger(__name__)


def decide_to_generate(
    state: CRAGState,
) -> Literal["generate", "rewrite", "fallback"]:
    """Determines next node in StateGraph based on Grader assessment and retry count."""
    overall_grade = state.get("overall_grade", "NOT_RELEVANT")
    retry_count = state.get("retry_count", 0)
    max_retries = settings.max_rewrite_retries

    logger.info(
        f"CRAG Edge Decision: grade='{overall_grade}', retries={retry_count}/{max_retries}"
    )

    if overall_grade == "RELEVANT":
        return "generate"

    if overall_grade == "PARTIALLY_RELEVANT":
        if retry_count < max_retries:
            return "rewrite"
        else:
            logger.info("Max rewrite attempts exceeded. Proceeding to generation with available context.")
            return "generate"

    # Default to fallback for NOT_RELEVANT or empty context
    return "fallback"
