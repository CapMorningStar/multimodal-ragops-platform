"""External Web Search Fallback Node for CRAG."""

import logging
from typing import Any, Dict, Optional

import requests

from config.settings import settings
from src.crag.state import CRAGState

logger = logging.getLogger(__name__)


class FallbackNode:
    """Executes web search when local enterprise documents lack relevant context."""

    def __init__(self, serper_api_key: Optional[str] = None):
        self.api_key = serper_api_key or settings.serper_api_key

    def _perform_web_search(self, query: str) -> str:
        """Calls Serper API if key is available, else provides safe fallback."""
        if not self.api_key:
            logger.info("No SERPER_API_KEY provided. Using simulated external search fallback.")
            return (
                f"[External Fallback Search] No relevant internal documents found for '{query}'. "
                "External sources indicate standard enterprise benchmarks and regulatory filings."
            )

        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": 3}
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()

            data = response.json()
            organic = data.get("organic", [])
            snippets = [f"- {item.get('title')}: {item.get('snippet')}" for item in organic]
            return "\n".join(snippets)
        except Exception as e:
            logger.warning(f"Serper API call failed: {e}. Falling back to default message.")
            return f"[External Search Error] Could not retrieve live results for '{query}'."

    def __call__(self, state: CRAGState) -> Dict[str, Any]:
        """Node execution function."""
        query = state.get("query", "")
        trace = list(state.get("execution_trace", []))

        trace.append(f"fallback:web_search({query})")
        logger.info(f"CRAG Fallback executing web search for: '{query}'")

        results = self._perform_web_search(query)

        return {
            "web_search_results": results,
            "execution_trace": trace,
        }
