"""Ingestion Pipeline Coordinator.

Orchestrates PDF parsing, table extraction, chart cropping,
and persistence to Parquet / JSONL.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config.logging_config import configure_logging
from config.settings import settings
from src.ingestion.docai_parser import DocumentAIParser, DocumentChunk, ParsedDocument

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Manages end-to-end ingestion and multimodal chunk extraction."""

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
    ):
        self.raw_dir = raw_dir or settings.raw_data_dir
        self.processed_dir = processed_dir or settings.processed_data_dir
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.parser = DocumentAIParser(output_dir=self.processed_dir)

    def ingest_document(self, file_path: Path) -> ParsedDocument:
        """Processes a single PDF document and persists its chunks."""
        logger.info(f"Starting ingestion for: {file_path}")
        parsed_doc = self.parser.process_file(file_path)

        # Save chunks to parquet and jsonl
        chunks_records = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "page_number": c.page_number,
                "content_type": c.content_type,
                "content": c.content,
                "image_path": c.image_path,
                "metadata": json.dumps(c.metadata),
            }
            for c in parsed_doc.chunks
        ]

        df = pd.DataFrame(chunks_records)
        parquet_path = self.processed_dir / f"{parsed_doc.doc_id}_chunks.parquet"
        df.to_parquet(parquet_path, index=False)
        logger.info(f"Saved {len(df)} chunks to: {parquet_path}")

        # Also save master jsonl for easy inspection
        jsonl_path = self.processed_dir / f"{parsed_doc.doc_id}_chunks.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for record in chunks_records:
                f.write(json.dumps(record) + "\n")

        return parsed_doc

    def ingest_all(self) -> List[ParsedDocument]:
        """Ingests all PDFs found in raw_dir."""
        pdf_files = list(self.raw_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"No PDF files found in: {self.raw_dir}")
            return []

        results = []
        for pdf_path in pdf_files:
            parsed = self.ingest_document(pdf_path)
            results.append(parsed)

        logger.info(f"Completed ingestion of {len(results)} documents.")
        return results


def main() -> None:
    """CLI entrypoint for ingestion pipeline."""
    configure_logging()
    parser = argparse.ArgumentParser(description="Multimodal PDF Ingestion Pipeline")
    parser.add_argument("--file", type=str, default=None, help="Path to specific PDF file")
    parser.add_argument("--all", action="store_true", help="Ingest all PDFs in data/raw")
    args = parser.parse_args()

    pipeline = IngestionPipeline()

    if args.file:
        pipeline.ingest_document(Path(args.file))
    elif args.all:
        pipeline.ingest_all()
    else:
        logger.info("No file specified. Ingesting any existing PDFs in data/raw...")
        pipeline.ingest_all()


if __name__ == "__main__":
    main()
