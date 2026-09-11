"""Multimodal Hybrid Retriever Node for CRAG."""

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.crag.state import CRAGState
from src.vector_store.embeddings import VertexMultimodalEmbedder
from src.vector_store.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


class RetrieverNode:
    """Retrieves multimodal text chunks, tables, and charts from vector store."""

    def __init__(
        self,
        vector_store: Optional[LocalVectorStore] = None,
        embedder: Optional[VertexMultimodalEmbedder] = None,
        top_k: Optional[int] = None,
    ):
        self.vector_store = vector_store or LocalVectorStore()
        self.embedder = embedder or VertexMultimodalEmbedder()
        self.top_k = top_k or settings.retrieval_top_k

    def __call__(self, state: CRAGState) -> Dict[str, Any]:
        """Node execution function for LangGraph."""
        # Use transformed query if available from a previous rewrite cycle
        search_query = state.get("transformed_query") or state.get("query", "")
        trace = list(state.get("execution_trace", []))
        trace.append(f"retrieve:{search_query}")

        logger.info(f"CRAG Retriever searching for: '{search_query}'")
        q_vec = self.embedder.embed_text(search_query)

        search_results = self.vector_store.similarity_search(
            query_vector=q_vec,
            top_k=self.top_k,
        )

        retrieved_docs: List[Dict[str, Any]] = []
        extracted_images: List[str] = []

        for res in search_results:
            doc_entry = {
                "chunk_id": res.chunk_id,
                "doc_id": res.doc_id,
                "page_number": res.page_number,
                "content_type": res.content_type,
                "content": res.content,
                "score": res.score,
                "image_path": res.image_path,
                "metadata": res.metadata,
            }
            retrieved_docs.append(doc_entry)

            if res.content_type == "chart" and res.image_path:
                extracted_images.append(res.image_path)

        logger.info(f"Retrieved {len(retrieved_docs)} candidate documents ({len(extracted_images)} images).")

        return {
            "retrieved_docs": retrieved_docs,
            "extracted_images": extracted_images,
            "execution_trace": trace,
        }
