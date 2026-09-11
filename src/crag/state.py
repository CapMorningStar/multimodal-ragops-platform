"""Typed state definition for the LangGraph Corrective RAG (CRAG) workflow."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class CRAGState(TypedDict, total=False):
    """Execution state passed between nodes in the CRAG StateGraph."""

    # Original user query
    query: str

    # Retrieved candidate multimodal documents
    retrieved_docs: List[Dict[str, Any]]

    # Extracted chart/image paths relevant to the query
    extracted_images: List[str]

    # Grader evaluation results
    relevance_scores: List[float]
    overall_grade: str  # "RELEVANT", "PARTIALLY_RELEVANT", "NOT_RELEVANT"

    # Query reformulation tracking
    transformed_query: Optional[str]
    retry_count: int

    # External fallback results (when local corpus is insufficient)
    web_search_results: Optional[str]

    # Final synthesized answer with citations
    final_response: str
    citations: List[Dict[str, Any]]

    # Observability and execution path trace
    execution_trace: List[str]
