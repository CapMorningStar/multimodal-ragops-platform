"""Query Rewriter and Reformulation Node for CRAG."""

import logging
from typing import Any, Dict

from config.settings import settings
from src.crag.state import CRAGState

logger = logging.getLogger(__name__)


class RewriterNode:
    """Reformulates ambiguous or partially relevant queries for secondary retrieval."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries or settings.max_rewrite_retries

    def _rewrite(self, original_query: str, retry_count: int) -> str:
        """Transforms query by focusing on core semantic concepts."""
        # Clean query
        stopwords = {"what", "is", "the", "how", "much", "did", "were", "tell", "me", "about", "can", "you", "show"}
        tokens = original_query.lower().split()
        filtered = [t for t in tokens if t not in stopwords and len(t) > 2]

        if retry_count == 0:
            # First reformulation: focus on core enterprise keywords
            return " ".join(filtered) if filtered else original_query
        else:
            # Subsequent reformulation: expand with financial/operational domain terms
            base = " ".join(filtered) if filtered else original_query
            return f"{base} overview metrics figures"

    def __call__(self, state: CRAGState) -> Dict[str, Any]:
        """Rewrites the query and increments retry count."""
        query = state.get("query", "")
        retries = state.get("retry_count", 0)
        trace = list(state.get("execution_trace", []))

        new_query = self._rewrite(query, retries)
        trace.append(f"rewrite(attempt {retries + 1}):'{query}'->'{new_query}'")

        logger.info(f"CRAG Rewriter (attempt {retries + 1}): '{query}' -> '{new_query}'")

        return {
            "transformed_query": new_query,
            "retry_count": retries + 1,
            "execution_trace": trace,
        }
