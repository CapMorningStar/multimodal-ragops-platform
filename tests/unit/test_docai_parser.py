"""Unit tests for Document AI parser, table extractor, and chart cropper."""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from PIL import Image

from src.ingestion.chart_cropper import ChartCropper
from src.ingestion.docai_parser import DocumentAIParser, DocumentChunk
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.table_extractor import BoundingBox, ExtractedTable, TableExtractor


def test_table_to_markdown():
    """Verify conversion of 2D grid of strings into standard Markdown table."""
    headers = [["Metric", "2025", "2026"]]
    body = [
        ["Revenue", "$100M", "$120M"],
        ["Operating Margin", "20%", "24%"],
    ]

    md = TableExtractor.table_to_markdown(headers, body)

    assert "| Metric | 2025 | 2026 |" in md
    assert "| --- | --- | --- |" in md
    assert "| Revenue | $100M | $120M |" in md
    assert "| Operating Margin | 20% | 24% |" in md


def test_table_to_markdown_empty():
    """Verify empty input returns empty string."""
    assert TableExtractor.table_to_markdown([], []) == ""


def test_table_pipe_escaping():
    """Verify that pipe characters inside cells are escaped."""
    headers = [["Column A | Sub", "Column B"]]
    body = [["Value | 1", "Value 2"]]

    md = TableExtractor.table_to_markdown(headers, body)
    assert r"Column A \| Sub" in md
    assert r"Value \| 1" in md


def test_chart_cropper_bounding_box():
    """Verify image cropping with bounding box."""
    # Create a 200x200 test RGB image
    img = Image.new("RGB", (200, 200), color="blue")
    cropper = ChartCropper()

    # Bounding box covering center [0.25, 0.25] to [0.75, 0.75]
    bbox = BoundingBox(top=0.25, left=0.25, bottom=0.75, right=0.75)
    cropped = cropper.crop_bounding_box(img, bbox, padding_ratio=0.0)

    assert abs(cropped.width - 100) <= 2
    assert abs(cropped.height - 100) <= 2


def test_chart_cropper_save(tmp_path: Path):
    """Verify saving cropped chart to disk."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    cropper = ChartCropper(output_dir=tmp_path)
    bbox = BoundingBox(top=0.1, left=0.1, bottom=0.9, right=0.9)

    chart = cropper.crop_from_page_image_bytes(
        image_bytes=img_bytes,
        bbox=bbox,
        doc_id="test_doc",
        page_number=1,
        element_index=0,
        caption="Sample Chart",
    )

    assert chart is not None
    assert Path(chart.image_path).exists()
    assert chart.chart_id == "test_doc_p1_visual_0"


def test_mock_document_ai_parser(tmp_path: Path):
    """Verify that DocumentAIParser operates gracefully in mock/offline mode."""
    parser = DocumentAIParser(output_dir=tmp_path)
    mock_pdf_bytes = b"%PDF-1.4 Mock PDF content"

    parsed = parser.process_pdf_bytes(mock_pdf_bytes, doc_id="financial_report")

    assert parsed.doc_id == "financial_report"
    assert len(parsed.chunks) >= 2
    types = [c.content_type for c in parsed.chunks]
    assert "text" in types
    assert "table" in types


def test_ingestion_pipeline_run(tmp_path: Path):
    """Verify end-to-end ingestion pipeline saving to parquet."""
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()

    # Create dummy pdf file
    pdf_file = raw_dir / "sample_statement.pdf"
    pdf_file.write_bytes(b"%PDF-1.5 Dummy Enterprise Financials")

    pipeline = IngestionPipeline(raw_dir=raw_dir, processed_dir=processed_dir)
    results = pipeline.ingest_all()

    assert len(results) == 1
    parquet_path = processed_dir / "sample_statement_chunks.parquet"
    assert parquet_path.exists()

    df = pd.read_parquet(parquet_path)
    assert len(df) >= 2
    assert "chunk_id" in df.columns
    assert "content_type" in df.columns
