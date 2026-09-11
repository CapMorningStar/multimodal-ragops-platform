"""Multimodal Document Relevance Grader Node for CRAG."""

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.crag.state import CRAGState

logger = logging.getLogger(__name__)


class GraderNode:
    """Evaluates the factual relevance of retrieved documents to the query."""

    def __init__(
        self,
        threshold_high: Optional[float] = None,
        threshold_low: Optional[float] = None,
    ):
        self.threshold_high = threshold_high or settings.relevance_threshold_high
        self.threshold_low = threshold_low or settings.relevance_threshold_low

    def _grade_document(self, query: str, doc_content: str, doc_score: float) -> float:
        """Computes relevance score combining semantic vector score and lexical match."""
        # Clean terms
        q_terms = set(query.lower().split())
        doc_terms = set(doc_content.lower().split())

        overlap = len(q_terms.intersection(doc_terms)) / max(len(q_terms), 1)

        # Blended relevance score
        blended_score = 0.6 * doc_score + 0.4 * overlap
        return min(max(blended_score, 0.0), 1.0)

    def __call__(self, state: CRAGState) -> Dict[str, Any]:
        """Evaluates all candidate documents and assigns an overall grade."""
        query = state.get("query", "")
        retrieved_docs = state.get("retrieved_docs", [])
        trace = list(state.get("execution_trace", []))

        if not retrieved_docs:
            trace.append("grade:empty_docs->NOT_RELEVANT")
            return {
                "relevance_scores": [],
                "overall_grade": "NOT_RELEVANT",
                "execution_trace": trace,
            }

        scores: List[float] = []
        filtered_docs: List[Dict[str, Any]] = []

        for doc in retrieved_docs:
            raw_score = float(doc.get("score", 0.5))
            content = doc.get("content", "")
            grade = self._grade_document(query, content, raw_score)
            scores.append(grade)

            if grade >= self.threshold_low:
                filtered_docs.append(doc)

        max_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if max_score >= self.threshold_high:
            overall_grade = "RELEVANT"
        elif max_score >= self.threshold_low:
            overall_grade = "PARTIALLY_RELEVANT"
        else:
            overall_grade = "NOT_RELEVANT"

        trace.append(f"grade:max={max_score:.2f},avg={avg_score:.2f}->{overall_grade}")
        logger.info(f"CRAG Grader result: {overall_grade} (max_score={max_score:.2f})")

        return {
            "relevance_scores": scores,
            "retrieved_docs": filtered_docs if filtered_docs else retrieved_docs,
            "overall_grade": overall_grade,
            "execution_trace": trace,
        }
