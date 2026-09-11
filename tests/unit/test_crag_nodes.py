"""Unit tests for LangGraph Corrective RAG (CRAG) nodes and state machine."""

from pathlib import Path

import numpy as np
import pytest

from src.crag.edges import decide_to_generate
from src.crag.graph import build_crag_graph, run_crag
from src.crag.nodes.fallback import FallbackNode
from src.crag.nodes.generator import GeneratorNode
from src.crag.nodes.grader import GraderNode
from src.crag.nodes.retriever import RetrieverNode
from src.crag.nodes.rewriter import RewriterNode
from src.crag.state import CRAGState
from src.ingestion.docai_parser import DocumentChunk
from src.vector_store.embeddings import VertexMultimodalEmbedder
from src.vector_store.local_store import LocalVectorStore


@pytest.fixture
def populated_vector_store(tmp_path: Path) -> LocalVectorStore:
    """Provides a vector store populated with sample chunks."""
    store = LocalVectorStore(index_dir=tmp_path / "crag_index")
    embedder = VertexMultimodalEmbedder()

    chunks = [
        DocumentChunk(
            chunk_id="chunk_financial_1",
            doc_id="sec_10k",
            page_number=14,
            content_type="text",
            content="Total operating revenue expanded by 18.2% to $142.1 million in fiscal 2026.",
            metadata={"section": "Financial Highlights"},
        ),
        DocumentChunk(
            chunk_id="chunk_table_1",
            doc_id="sec_10k",
            page_number=15,
            content_type="table",
            content="| Segment | Revenue | Margin |\n| Cloud | $80M | 28% |\n| Enterprise | $62.1M | 19% |",
            metadata={"section": "Segment Breakdown"},
        ),
        DocumentChunk(
            chunk_id="chunk_chart_1",
            doc_id="sec_10k",
            page_number=16,
            content_type="chart",
            content="[Visual Figure: chart_1] Quarterly revenue growth trajectory bar chart",
            image_path=str(tmp_path / "chart_1.png"),
            metadata={"chart_id": "chart_1"},
        ),
    ]

    embeddings = np.vstack([embedder.embed_text(c.content) for c in chunks])
    store.add_chunks(chunks, embeddings)
    return store


def test_retriever_node(populated_vector_store: LocalVectorStore):
    """Verify RetrieverNode fetches documents and populates CRAGState."""
    retriever = RetrieverNode(vector_store=populated_vector_store, top_k=2)
    state: CRAGState = {"query": "What is total operating revenue?", "execution_trace": []}

    output = retriever(state)

    assert "retrieved_docs" in output
    assert len(output["retrieved_docs"]) == 2
    assert len(output["execution_trace"]) == 1


def test_grader_node_relevant():
    """Verify GraderNode marks highly overlapping docs as RELEVANT."""
    grader = GraderNode(threshold_high=0.6, threshold_low=0.3)
    state: CRAGState = {
        "query": "operating revenue fiscal 2026",
        "retrieved_docs": [
            {
                "chunk_id": "c1",
                "content": "operating revenue expanded in fiscal 2026",
                "score": 0.85,
            }
        ],
        "execution_trace": [],
    }

    output = grader(state)
    assert output["overall_grade"] == "RELEVANT"
    assert len(output["relevance_scores"]) == 1


def test_grader_node_not_relevant():
    """Verify GraderNode marks completely unrelated docs as NOT_RELEVANT."""
    grader = GraderNode(threshold_high=0.75, threshold_low=0.40)
    state: CRAGState = {
        "query": "cryptocurrency mining bitcoin algorithms",
        "retrieved_docs": [
            {
                "chunk_id": "c1",
                "content": "human resources employee vacation policy and sick leave",
                "score": 0.1,
            }
        ],
        "execution_trace": [],
    }

    output = grader(state)
    assert output["overall_grade"] == "NOT_RELEVANT"


def test_rewriter_node():
    """Verify RewriterNode reformulates query and increments retries."""
    rewriter = RewriterNode()
    state: CRAGState = {
        "query": "What did the company make in revenue?",
        "retry_count": 0,
        "execution_trace": [],
    }

    output = rewriter(state)
    assert output["retry_count"] == 1
    assert "company" in output["transformed_query"]
    assert "revenue" in output["transformed_query"]


def test_fallback_node():
    """Verify FallbackNode returns search results."""
    fallback = FallbackNode()
    state: CRAGState = {"query": "Non-existent enterprise topic", "execution_trace": []}

    output = fallback(state)
    assert "web_search_results" in output
    assert len(output["web_search_results"]) > 0


def test_decide_to_generate_edges():
    """Verify conditional edge routing decisions."""
    # Relevant -> generate
    state_rel: CRAGState = {"overall_grade": "RELEVANT", "retry_count": 0}
    assert decide_to_generate(state_rel) == "generate"

    # Partially relevant & retries < max -> rewrite
    state_part: CRAGState = {"overall_grade": "PARTIALLY_RELEVANT", "retry_count": 0}
    assert decide_to_generate(state_part) == "rewrite"

    # Partially relevant & retries >= max -> generate
    state_part_max: CRAGState = {"overall_grade": "PARTIALLY_RELEVANT", "retry_count": 2}
    assert decide_to_generate(state_part_max) == "generate"

    # Not relevant -> fallback
    state_not: CRAGState = {"overall_grade": "NOT_RELEVANT", "retry_count": 0}
    assert decide_to_generate(state_not) == "fallback"


def test_full_crag_graph_execution(populated_vector_store: LocalVectorStore):
    """Verify full end-to-end CRAG state graph execution."""
    final_state = run_crag(
        query="What was the operating revenue in fiscal 2026?",
        vector_store=populated_vector_store,
    )

    assert "final_response" in final_state
    assert len(final_state["final_response"]) > 0
    assert "citations" in final_state
    assert len(final_state["execution_trace"]) >= 3
    assert any("retrieve:" in step for step in final_state["execution_trace"])
    assert any("grade:" in step for step in final_state["execution_trace"])
    assert "generate:grounded_synthesis" in final_state["execution_trace"]
