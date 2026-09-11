"""Zero-Idle-Burn Local Vector Store using NumPy Cosine Similarity and Parquet.

Prevents continuous hourly node charges ($150-$300/mo) from Vertex AI Vector Search
endpoints by persisting vectors and metadata directly to local disk / Cloud Storage.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import settings
from src.ingestion.docai_parser import DocumentChunk
from src.vector_store.base import BaseVectorStore, SearchResult

logger = logging.getLogger(__name__)


class LocalVectorStore(BaseVectorStore):
    """File-backed, zero-idle-cost vector store using vectorized cosine similarity."""

    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = index_dir or settings.local_vector_index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.embeddings_path = self.index_dir / "embeddings.npy"
        self.metadata_path = self.index_dir / "metadata.parquet"

        self.embeddings: Optional[np.ndarray] = None  # Shape: (N, D)
        self.metadata_df: Optional[pd.DataFrame] = None

        # Load existing index if present on disk
        if self.embeddings_path.exists() and self.metadata_path.exists():
            self.load()

    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: np.ndarray,
    ) -> None:
        """Appends chunks and embeddings to the store."""
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks count ({len(chunks)}) must match embeddings count ({len(embeddings)})"
            )

        new_records = []
        for c in chunks:
            new_records.append(
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "page_number": c.page_number,
                    "content_type": c.content_type,
                    "content": c.content,
                    "image_path": c.image_path or "",
                    "metadata": json.dumps(c.metadata),
                }
            )

        new_df = pd.DataFrame(new_records)

        # Normalize incoming embeddings to unit length for cosine dot product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized_embeddings = embeddings / np.maximum(norms, 1e-12)

        if self.embeddings is None or self.metadata_df is None:
            self.embeddings = normalized_embeddings.astype(np.float32)
            self.metadata_df = new_df
        else:
            self.embeddings = np.vstack([self.embeddings, normalized_embeddings]).astype(np.float32)
            self.metadata_df = pd.concat([self.metadata_df, new_df], ignore_index=True)

        self.save()
        logger.info(f"Indexed {len(chunks)} chunks. Total vectors: {len(self.embeddings)}")

    def similarity_search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        content_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """Performs fast cosine similarity search across indexed vectors."""
        if self.embeddings is None or self.metadata_df is None or len(self.embeddings) == 0:
            logger.warning("Search called on empty vector store.")
            return []

        # Ensure query vector is unit normalized
        q_norm = np.linalg.norm(query_vector)
        q = (query_vector / max(q_norm, 1e-12)).flatten()

        # Dot product with all normalized vectors yields exact cosine similarities
        scores = np.dot(self.embeddings, q)

        # Apply content_type filter if requested
        if content_type:
            mask = (self.metadata_df["content_type"] == content_type).to_numpy()
            scores = np.where(mask, scores, -np.inf)

        # Retrieve top_k indices sorted descending
        k = min(top_k, len(scores))
        top_indices = np.argsort(-scores)[:k]

        results: List[SearchResult] = []
        for idx in top_indices:
            score = float(scores[idx])
            if np.isneginf(score):
                continue

            row = self.metadata_df.iloc[idx]
            meta_dict = json.loads(row["metadata"]) if row["metadata"] else {}

            results.append(
                SearchResult(
                    chunk_id=str(row["chunk_id"]),
                    doc_id=str(row["doc_id"]),
                    page_number=int(row["page_number"]),
                    content_type=str(row["content_type"]),
                    content=str(row["content"]),
                    image_path=str(row["image_path"]) if row["image_path"] else None,
                    score=score,
                    metadata=meta_dict,
                )
            )

        return results

    def save(self, directory: Optional[Path] = None) -> None:
        """Persists the vector index and metadata to disk."""
        target_dir = directory or self.index_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if self.embeddings is not None and self.metadata_df is not None:
            np.save(str(target_dir / "embeddings.npy"), self.embeddings)
            self.metadata_df.to_parquet(str(target_dir / "metadata.parquet"), index=False)
            logger.debug(f"Saved {len(self.embeddings)} vectors to {target_dir}")

    def load(self, directory: Optional[Path] = None) -> None:
        """Loads index and metadata from disk."""
        target_dir = directory or self.index_dir
        emb_file = target_dir / "embeddings.npy"
        meta_file = target_dir / "metadata.parquet"

        if emb_file.exists() and meta_file.exists():
            self.embeddings = np.load(str(emb_file))
            self.metadata_df = pd.read_parquet(str(meta_file))
            logger.info(f"Loaded {len(self.embeddings)} vectors from {target_dir}")
        else:
            logger.warning(f"No vector index found in {target_dir}")

    def count(self) -> int:
        """Returns the number of indexed vectors."""
        return len(self.embeddings) if self.embeddings is not None else 0

    def clear(self) -> None:
        """Clears memory and disk state."""
        self.embeddings = None
        self.metadata_df = None
        if self.embeddings_path.exists():
            self.embeddings_path.unlink()
        if self.metadata_path.exists():
            self.metadata_path.unlink()
