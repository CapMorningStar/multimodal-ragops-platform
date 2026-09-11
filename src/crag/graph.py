"""LangGraph StateGraph assembly and compilation for Corrective RAG (CRAG)."""

import logging
from typing import Optional

from langgraph.graph import END, StateGraph

from src.crag.edges import decide_to_generate
from src.crag.nodes.fallback import FallbackNode
from src.crag.nodes.generator import GeneratorNode
from src.crag.nodes.grader import GraderNode
from src.crag.nodes.retriever import RetrieverNode
from src.crag.nodes.rewriter import RewriterNode
from src.crag.state import CRAGState
from src.vector_store.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


def build_crag_graph(vector_store: Optional[LocalVectorStore] = None):
    """Constructs and compiles the CRAG StateGraph."""
    store = vector_store or LocalVectorStore()

    workflow = StateGraph(CRAGState)

    # Initialize nodes
    retriever_node = RetrieverNode(vector_store=store)
    grader_node = GraderNode()
    rewriter_node = RewriterNode()
    fallback_node = FallbackNode()
    generator_node = GeneratorNode()

    # Add nodes to graph
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("rewriter", rewriter_node)
    workflow.add_node("fallback", fallback_node)
    workflow.add_node("generator", generator_node)

    # Set entry point
    workflow.set_entry_point("retriever")

    # Connect retriever to grader
    workflow.add_edge("retriever", "grader")

    # Add conditional branching from grader
    workflow.add_conditional_edges(
        "grader",
        decide_to_generate,
        {
            "generate": "generator",
            "rewrite": "rewriter",
            "fallback": "fallback",
        },
    )

    # Connect rewriter back to retriever (cyclical CRAG loop)
    workflow.add_edge("rewriter", "retriever")

    # Connect fallback to generator
    workflow.add_edge("fallback", "generator")

    # End from generator
    workflow.add_edge("generator", END)

    return workflow.compile()


def run_crag(query: str, vector_store: Optional[LocalVectorStore] = None) -> CRAGState:
    """Executes the compiled CRAG workflow for a given user query."""
    app = build_crag_graph(vector_store=vector_store)

    initial_state: CRAGState = {
        "query": query,
        "retrieved_docs": [],
        "extracted_images": [],
        "relevance_scores": [],
        "overall_grade": "NOT_RELEVANT",
        "transformed_query": None,
        "retry_count": 0,
        "web_search_results": None,
        "final_response": "",
        "citations": [],
        "execution_trace": [],
    }

    final_state = app.invoke(initial_state)
    return final_state
