"""Automated chunk indexing script for multimodal documents."""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from PIL import Image

from config.logging_config import configure_logging
from config.settings import settings
from src.ingestion.docai_parser import DocumentChunk
from src.ingestion.pipeline import IngestionPipeline
from src.vector_store.embeddings import VertexMultimodalEmbedder
from src.vector_store.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


class MultimodalIndexer:
    """Indexes multimodal document chunks into the LocalVectorStore."""

    def __init__(
        self,
        vector_store: Optional[LocalVectorStore] = None,
        embedder: Optional[VertexMultimodalEmbedder] = None,
    ):
        self.vector_store = vector_store or LocalVectorStore()
        self.embedder = embedder or VertexMultimodalEmbedder()

    def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Embeds and indexes a list of document chunks."""
        if not chunks:
            logger.warning("No chunks to index.")
            return 0

        logger.info(f"Generating multimodal embeddings for {len(chunks)} chunks...")
        embeddings_list = []

        for chunk in chunks:
            if chunk.content_type == "chart" and chunk.image_path and Path(chunk.image_path).exists():
                # Embed chart image
                try:
                    img = Image.open(chunk.image_path)
                    vec = self.embedder.embed_image(img)
                except Exception as e:
                    logger.warning(f"Could not load image {chunk.image_path} ({e}). Falling back to text embedding.")
                    vec = self.embedder.embed_text(chunk.content)
            else:
                # Embed text or markdown table
                vec = self.embedder.embed_text(chunk.content)

            embeddings_list.append(vec)

        import numpy as np
        embeddings_matrix = np.vstack(embeddings_list)
        self.vector_store.add_chunks(chunks, embeddings_matrix)
        logger.info(f"Successfully indexed {len(chunks)} chunks.")
        return len(chunks)

    def index_processed_parquet(self, parquet_path: Path) -> int:
        """Loads chunks from parquet and indexes them."""
        df = pd.read_parquet(parquet_path)
        chunks = []
        for _, row in df.iterrows():
            meta = json.loads(row["metadata"]) if row.get("metadata") else {}
            chunks.append(
                DocumentChunk(
                    chunk_id=str(row["chunk_id"]),
                    doc_id=str(row["doc_id"]),
                    page_number=int(row["page_number"]),
                    content_type=str(row["content_type"]),
                    content=str(row["content"]),
                    image_path=str(row["image_path"]) if row.get("image_path") else None,
                    metadata=meta,
                )
            )
        return self.index_chunks(chunks)

    def ingest_and_index_file(self, pdf_path: Path) -> int:
        """Full pipeline: parses PDF, extracts tables/charts, and indexes them."""
        pipeline = IngestionPipeline()
        parsed_doc = pipeline.ingest_document(pdf_path)
        return self.index_chunks(parsed_doc.chunks)


def main() -> None:
    """CLI entrypoint for multimodal indexer."""
    configure_logging()
    parser = argparse.ArgumentParser(description="Multimodal Vector Indexer")
    parser.add_argument("--file", type=str, default=None, help="Path to raw PDF file to ingest and index")
    parser.add_argument("--parquet", type=str, default=None, help="Path to processed parquet chunks file")
    args = parser.parse_args()

    indexer = MultimodalIndexer()

    if args.file:
        indexer.ingest_and_index_file(Path(args.file))
    elif args.parquet:
        indexer.index_processed_parquet(Path(args.parquet))
    else:
        logger.info("Scanning data/processed for unindexed parquet files...")
        parquet_files = list(settings.processed_data_dir.glob("*_chunks.parquet"))
        total = 0
        for p in parquet_files:
            total += indexer.index_processed_parquet(p)
        logger.info(f"Total chunks indexed: {total}")


if __name__ == "__main__":
    main()
