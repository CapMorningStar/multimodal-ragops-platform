"""Unit tests for Vertex Multimodal Embeddings wrapper."""

import numpy as np
import pytest
from PIL import Image

from src.vector_store.embeddings import VertexMultimodalEmbedder


def test_embedder_dimension():
    """Verify embedder outputs 1408-dimensional vectors."""
    embedder = VertexMultimodalEmbedder()
    vec = embedder.embed_text("Revenue expanded 15% in fiscal year 2026.")

    assert isinstance(vec, np.ndarray)
    assert vec.shape == (1408,)
    assert vec.dtype == np.float32


def test_embedding_normalization():
    """Verify vectors are unit L2-normalized."""
    embedder = VertexMultimodalEmbedder()
    vec = embedder.embed_text("Sample text query")
    norm = np.linalg.norm(vec)

    assert abs(norm - 1.0) < 1e-5


def test_embed_image_pil():
    """Verify embedding a PIL image."""
    embedder = VertexMultimodalEmbedder()
    img = Image.new("RGB", (100, 100), color="green")
    vec = embedder.embed_image(img)

    assert isinstance(vec, np.ndarray)
    assert vec.shape == (1408,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


def test_embed_batch_texts():
    """Verify batch embedding shape."""
    embedder = VertexMultimodalEmbedder()
    texts = ["Quarterly Report", "Operating Margins", "CapEx Forecast"]
    batch_vecs = embedder.embed_batch_texts(texts)

    assert batch_vecs.shape == (3, 1408)
