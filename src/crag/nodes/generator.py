"""Grounded Multimodal Generator Node for CRAG using Gemini Flash."""

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.crag.state import CRAGState

logger = logging.getLogger(__name__)


class GeneratorNode:
    """Synthesizes grounded answers with citations from retrieved multimodal content."""

    def __init__(
        self,
        model_name: Optional[str] = None,
    ):
        self.model_name = model_name or settings.gemini_llm_model
        self._is_mock = (
            settings.gcp_project_id == "demo-gcp-project"
            or not settings.google_application_credentials
        )

    def _call_gemini(
        self,
        query: str,
        context_blocks: List[str],
        image_paths: List[str],
    ) -> str:
        """Invokes Gemini Flash model with multimodal context."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
            )

            prompt = (
                "You are an enterprise document intelligence assistant. Answer the user question strictly using "
                "the provided context (text, markdown tables, charts, or web search fallback). Always include explicit inline citations. "
                "For documents, format as [Doc: <doc_id>, Page: <page>, Type: <type>]. For web search fallback context, cite [Source: Web Search Fallback]. "
                "If using web search fallback, incorporate facts directly from the Web Search Fallback Context. "
                "If the information is missing from the provided context, state that you could not find sufficient grounded information.\n\n"
                f"Question: {query}\n\n"
                "Context:\n" + "\n\n".join(context_blocks)
            )

            contents = [prompt]
            for img_path in image_paths[:3]:  # attach up to 3 charts
                try:
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                    contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
                except Exception as e:
                    logger.warning(f"Could not load chart {img_path}: {e}")

            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini API call failed ({e}). Falling back to local grounded synthesis.")
            return self._mock_synthesis(query, context_blocks, image_paths)

    def _mock_synthesis(
        self,
        query: str,
        context_blocks: List[str],
        image_paths: List[str],
    ) -> str:
        """Deterministic grounded synthesis for offline development and CI testing."""
        if not context_blocks:
            return f"I could not find sufficient grounded information in the documents to answer '{query}'."

        cleaned_blocks = []
        for block in context_blocks[:2]:
            # Strip citation header for pure factual content
            lines = [ln for ln in block.splitlines() if not ln.startswith("[Doc:")]
            cleaned_blocks.append("\n".join(lines).strip())

        return "\n".join(cleaned_blocks)

    def __call__(self, state: CRAGState) -> Dict[str, Any]:
        """Generates grounded final response and citations."""
        query = state.get("query", "")
        retrieved_docs = state.get("retrieved_docs", [])
        extracted_images = state.get("extracted_images", [])
        web_search = state.get("web_search_results")
        trace = list(state.get("execution_trace", []))

        trace.append("generate:grounded_synthesis")
        logger.info(f"CRAG Generator producing response for: '{query}'")

        context_blocks: List[str] = []
        citations: List[Dict[str, Any]] = []

        if web_search:
            context_blocks.append(f"Web Search Fallback Context:\n{web_search}")
            citations.append({"type": "web_search", "source": "Google/Serper Search"})

        for doc in retrieved_docs:
            citation = {
                "chunk_id": doc.get("chunk_id"),
                "doc_id": doc.get("doc_id"),
                "page_number": doc.get("page_number"),
                "content_type": doc.get("content_type"),
                "image_path": doc.get("image_path"),
            }
            citations.append(citation)

            block = (
                f"[Doc: {doc.get('doc_id')}, Page: {doc.get('page_number')}, Type: {doc.get('content_type')}]\n"
                f"{doc.get('content')}"
            )
            context_blocks.append(block)

        if not context_blocks:
            return {
                "final_response": f"I could not find sufficient grounded information in the documents to answer '{query}'.",
                "citations": [],
                "execution_trace": trace,
            }

        if self._is_mock:
            response_text = self._mock_synthesis(query, context_blocks, extracted_images)
        else:
            response_text = self._call_gemini(query, context_blocks, extracted_images)

        return {
            "final_response": response_text,
            "citations": citations,
            "execution_trace": trace,
        }
