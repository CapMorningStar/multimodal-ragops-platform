"""Unit tests for Grounded Multimodal Generator and Citations."""

import pytest

from src.crag.nodes.generator import GeneratorNode
from src.crag.state import CRAGState


def test_generator_with_retrieved_docs():
    """Verify Generator synthesizes answer and formats citations."""
    generator = GeneratorNode()
    state: CRAGState = {
        "query": "What was the operating margin in Q3?",
        "retrieved_docs": [
            {
                "chunk_id": "c1",
                "doc_id": "sec_10q",
                "page_number": 5,
                "content_type": "table",
                "content": "| Operating Margin | 24.5% |",
                "image_path": None,
            }
        ],
        "extracted_images": [],
        "execution_trace": [],
    }

    output = generator(state)

    assert "final_response" in output
    assert "citations" in output
    assert len(output["citations"]) == 1
    assert output["citations"][0]["doc_id"] == "sec_10q"
    assert output["citations"][0]["page_number"] == 5
    assert output["citations"][0]["content_type"] == "table"


def test_generator_empty_context_guardrail():
    """Verify Generator explicitly notes lack of grounded data when context is empty."""
    generator = GeneratorNode()
    state: CRAGState = {
        "query": "What are the company's future projections for 2035?",
        "retrieved_docs": [],
        "extracted_images": [],
        "execution_trace": [],
    }

    output = generator(state)

    assert "could not find sufficient grounded information" in output["final_response"].lower()
    assert len(output["citations"]) == 0


def test_generator_with_web_search_fallback():
    """Verify Generator includes web search fallback citation."""
    generator = GeneratorNode()
    state: CRAGState = {
        "query": "What is the global cloud market size?",
        "retrieved_docs": [],
        "extracted_images": [],
        "web_search_results": "Global cloud computing market reached $600B in 2025.",
        "execution_trace": [],
    }

    output = generator(state)

    assert len(output["citations"]) == 1
    assert output["citations"][0]["type"] == "web_search"
    assert "Web Search Fallback Context" in output["final_response"] or "600" in output["final_response"] or "cloud" in output["final_response"].lower()
