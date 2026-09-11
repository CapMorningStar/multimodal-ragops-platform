"""Abstract base classes and data contracts for the Multimodal Vector Store."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.ingestion.docai_parser import DocumentChunk


@dataclass
class SearchResult:
    """Standardized search match returned by vector store."""
    chunk_id: str
    doc_id: str
    page_number: int
    content_type: str
    content: str
    score: float
    image_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseVectorStore(ABC):
    """Abstract interface for zero-idle-burn and cloud vector stores."""

    @abstractmethod
    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: np.ndarray,
    ) -> None:
        """Adds document chunks and their corresponding embedding vectors."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        content_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """Performs vector similarity search returning top_k results."""
        pass

    @abstractmethod
    def save(self, directory: Optional[Path] = None) -> None:
        """Persists the vector index and metadata to disk."""
        pass

    @abstractmethod
    def load(self, directory: Optional[Path] = None) -> None:
        """Loads index and metadata from disk."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Returns the total number of indexed vectors."""
        pass
