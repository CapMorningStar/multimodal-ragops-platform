"""Ragas Multimodal and Text Evaluation Harness for RAGOps."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationSample:
    """A single evaluation record."""
    question: str
    contexts: List[str]
    answer: str
    ground_truth: Optional[str] = None


@dataclass
class EvaluationReport:
    """Aggregated evaluation metrics across a benchmark suite."""
    total_samples: int
    faithfulness: float
    answer_relevance: float
    context_precision: float
    average_score: float
    passed: bool
    sample_scores: List[Dict[str, float]] = field(default_factory=list)


import re


class RagasEvaluator:
    """Evaluates RAG pipeline outputs using Ragas or local grounded metrics."""

    def __init__(self, min_faithfulness: float = 0.75, min_relevance: float = 0.75):
        self.min_faithfulness = min_faithfulness
        self.min_relevance = min_relevance

    @staticmethod
    def _extract_tokens(text: str) -> List[str]:
        """Extracts alphanumeric word tokens."""
        return [t.lower() for t in re.findall(r"\b\w+\b", text)]

    def _compute_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """Computes proportion of answer factual tokens grounded in contexts."""
        if not contexts or not answer:
            return 0.0

        all_context_tokens = set(self._extract_tokens(" ".join(contexts)))
        stopwords = {
            "based", "on", "the", "for", "and", "in", "with", "was", "were", "is", "are", "of", "to", "at",
            "doc", "page", "type", "text", "table", "chart", "documents", "referenced", "visual", "assets",
            "it", "that", "this", "these", "those", "there", "an", "as", "by", "from", "have", "has", "had",
            "not", "no", "or", "but", "however", "do", "does", "did", "be", "been", "being", "can", "could",
            "will", "would", "should", "if", "so", "such", "than", "then", "too", "very", "which", "who",
            "whom", "whose", "why", "how", "what", "when", "where", "our", "your", "my", "its", "their",
            "we", "you", "they", "he", "she", "him", "her", "them", "us", "stated", "mentioned", "provided",
            "information", "according", "also", "represents", "representing"
        }

        answer_tokens = [t for t in self._extract_tokens(answer) if t not in stopwords and len(t) > 1]

        if not answer_tokens:
            return 1.0

        grounded_count = sum(1 for t in answer_tokens if t in all_context_tokens)
        ratio = grounded_count / len(answer_tokens)
        return min(1.0, round(ratio, 4))

    def _compute_answer_relevance(self, question: str, answer: str) -> float:
        """Computes semantic relevance of answer to the question."""
        if not question or not answer:
            return 0.0

        stopwords = {"what", "which", "how", "much", "did", "were", "was", "the", "for", "and", "in", "is", "are", "does", "can", "you", "tell", "about"}
        q_tokens = set(t for t in self._extract_tokens(question) if t not in stopwords and len(t) > 2)
        a_tokens = set(self._extract_tokens(answer))

        if not q_tokens:
            return 1.0

        overlap = len(q_tokens.intersection(a_tokens)) / len(q_tokens)
        return min(1.0, round(overlap, 4))

    def _compute_context_precision(self, question: str, contexts: List[str]) -> float:
        """Computes precision of retrieved context chunks against the question."""
        if not contexts:
            return 0.0

        stopwords = {"what", "which", "how", "much", "did", "were", "was", "the", "for", "and", "in", "is", "are", "does"}
        q_tokens = set(t for t in self._extract_tokens(question) if t not in stopwords and len(t) > 2)

        if not q_tokens:
            return 1.0

        relevant_chunks = 0
        for ctx in contexts:
            ctx_tokens = set(self._extract_tokens(ctx))
            if len(q_tokens.intersection(ctx_tokens)) > 0:
                relevant_chunks += 1

        return round(relevant_chunks / len(contexts), 4)

    def evaluate_sample(self, sample: EvaluationSample) -> Dict[str, float]:
        """Evaluates a single sample."""
        faith = self._compute_faithfulness(sample.answer, sample.contexts)
        rel = self._compute_answer_relevance(sample.question, sample.answer)
        prec = self._compute_context_precision(sample.question, sample.contexts)

        return {
            "faithfulness": round(faith, 4),
            "answer_relevance": round(rel, 4),
            "context_precision": round(prec, 4),
        }

    def evaluate_dataset(self, samples: List[EvaluationSample]) -> EvaluationReport:
        """Evaluates a collection of samples and aggregates scores."""
        if not samples:
            return EvaluationReport(
                total_samples=0,
                faithfulness=0.0,
                answer_relevance=0.0,
                context_precision=0.0,
                average_score=0.0,
                passed=False,
            )

        sample_scores = []
        for s in samples:
            scores = self.evaluate_sample(s)
            sample_scores.append(scores)

        avg_faith = sum(s["faithfulness"] for s in sample_scores) / len(samples)
        avg_rel = sum(s["answer_relevance"] for s in sample_scores) / len(samples)
        avg_prec = sum(s["context_precision"] for s in sample_scores) / len(samples)
        overall_avg = (avg_faith + avg_rel + avg_prec) / 3.0

        passed = avg_faith >= self.min_faithfulness and avg_rel >= self.min_relevance

        return EvaluationReport(
            total_samples=len(samples),
            faithfulness=round(avg_faith, 4),
            answer_relevance=round(avg_rel, 4),
            context_precision=round(avg_prec, 4),
            average_score=round(overall_avg, 4),
            passed=passed,
            sample_scores=sample_scores,
        )
