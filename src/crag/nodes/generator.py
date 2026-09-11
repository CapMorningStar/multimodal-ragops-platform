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
            import vertexai
            from vertexai.generative_models import GenerativeModel, Part

            vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
            model = GenerativeModel(self.model_name)

            prompt = (
                "You are an enterprise document intelligence assistant. Answer the user question strictly using "
                "the provided text, markdown tables, and charts. Always include explicit inline citations in the "
                "format [Doc: <doc_id>, Page: <page>, Type: <type>]. If the information is missing, say so.\n\n"
                f"Question: {query}\n\n"
                "Context:\n" + "\n\n".join(context_blocks)
            )

            contents = [prompt]
            for img_path in image_paths[:3]:  # attach up to 3 charts
                try:
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                    contents.append(Part.from_data(data=img_bytes, mime_type="image/png"))
                except Exception as e:
                    logger.warning(f"Could not load chart {img_path}: {e}")

            response = model.generate_content(contents)
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

        lines = [
            f"Based on the enterprise documents for '{query}':",
            "",
        ]

        for i, block in enumerate(context_blocks[:2], 1):
            lines.append(f"- {block.strip()}")

        if image_paths:
            lines.append(f"\nReferenced Visual Assets: {len(image_paths)} chart(s) inspected.")

        return "\n".join(lines)

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

        if self._is_mock:
            response_text = self._mock_synthesis(query, context_blocks, extracted_images)
        else:
            response_text = self._call_gemini(query, context_blocks, extracted_images)

        return {
            "final_response": response_text,
            "citations": citations,
            "execution_trace": trace,
        }
