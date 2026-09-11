"""Unit tests for the Zero-Idle-Burn Local Vector Store."""

from pathlib import Path

import numpy as np
import pytest

from src.ingestion.docai_parser import DocumentChunk
from src.vector_store.embeddings import VertexMultimodalEmbedder
from src.vector_store.local_store import LocalVectorStore


@pytest.fixture
def sample_chunks() -> list[DocumentChunk]:
    """Provides sample multimodal chunks for indexing tests."""
    return [
        DocumentChunk(
            chunk_id="chunk_1",
            doc_id="report_q3",
            page_number=1,
            content_type="text",
            content="Q3 Revenue was $142M, representing 18% YoY growth.",
            metadata={"topic": "revenue"},
        ),
        DocumentChunk(
            chunk_id="chunk_2",
            doc_id="report_q3",
            page_number=2,
            content_type="table",
            content="| Segment | Growth |\n| --- | --- |\n| Cloud | 32% |",
            metadata={"topic": "segment_growth"},
        ),
        DocumentChunk(
            chunk_id="chunk_3",
            doc_id="report_q3",
            page_number=3,
            content_type="chart",
            content="[Visual Figure: chart_1] Quarterly growth chart",
            image_path="/path/to/chart_1.png",
            metadata={"topic": "visual_chart"},
        ),
    ]


def test_vector_store_add_and_count(tmp_path: Path, sample_chunks: list[DocumentChunk]):
    """Verify adding chunks and counting vectors."""
    store = LocalVectorStore(index_dir=tmp_path)
    embedder = VertexMultimodalEmbedder()

    embeddings = np.vstack([embedder.embed_text(c.content) for c in sample_chunks])
    store.add_chunks(sample_chunks, embeddings)

    assert store.count() == 3


def test_vector_store_similarity_search(tmp_path: Path, sample_chunks: list[DocumentChunk]):
    """Verify similarity search returns relevant top match."""
    store = LocalVectorStore(index_dir=tmp_path)
    embedder = VertexMultimodalEmbedder()

    embeddings = np.vstack([embedder.embed_text(c.content) for c in sample_chunks])
    store.add_chunks(sample_chunks, embeddings)

    query = "What was the revenue growth in Q3?"
    q_vec = embedder.embed_text(query)

    results = store.similarity_search(q_vec, top_k=2)

    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert results[0].chunk_id == "chunk_1" or results[0].chunk_id in ["chunk_1", "chunk_2"]


def test_vector_store_content_type_filter(tmp_path: Path, sample_chunks: list[DocumentChunk]):
    """Verify filtering similarity search by content_type."""
    store = LocalVectorStore(index_dir=tmp_path)
    embedder = VertexMultimodalEmbedder()

    embeddings = np.vstack([embedder.embed_text(c.content) for c in sample_chunks])
    store.add_chunks(sample_chunks, embeddings)

    q_vec = embedder.embed_text("Show me charts and figures")
    results = store.similarity_search(q_vec, top_k=5, content_type="chart")

    assert len(results) == 1
    assert results[0].content_type == "chart"
    assert results[0].chunk_id == "chunk_3"


def test_vector_store_persistence(tmp_path: Path, sample_chunks: list[DocumentChunk]):
    """Verify saving and reloading index from disk."""
    store = LocalVectorStore(index_dir=tmp_path)
    embedder = VertexMultimodalEmbedder()

    embeddings = np.vstack([embedder.embed_text(c.content) for c in sample_chunks])
    store.add_chunks(sample_chunks, embeddings)

    # Re-instantiate store from the same directory
    reloaded_store = LocalVectorStore(index_dir=tmp_path)
    assert reloaded_store.count() == 3

    q_vec = embedder.embed_text("Revenue")
    results = reloaded_store.similarity_search(q_vec, top_k=1)
    assert len(results) == 1


def test_multimodal_indexer_flow(tmp_path: Path, sample_chunks: list[DocumentChunk]):
    """Verify MultimodalIndexer indexes chunks into vector store."""
    from src.vector_store.indexer import MultimodalIndexer

    store = LocalVectorStore(index_dir=tmp_path / "index")
    embedder = VertexMultimodalEmbedder()
    indexer = MultimodalIndexer(vector_store=store, embedder=embedder)

    count = indexer.index_chunks(sample_chunks)
    assert count == 3
    assert store.count() == 3

