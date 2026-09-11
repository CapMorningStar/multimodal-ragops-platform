"""Google Cloud Document AI Layout Parser Client and Document Processor."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config.settings import settings
from src.ingestion.chart_cropper import ChartCropper, ExtractedChart
from src.ingestion.table_extractor import BoundingBox, ExtractedTable, TableExtractor

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Multimodal document chunk ready for embedding and CRAG retrieval."""
    chunk_id: str
    doc_id: str
    page_number: int
    content_type: str  # 'text', 'table', 'chart'
    content: str       # Text string or Markdown table
    image_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Complete structured output from Document AI layout analysis."""
    doc_id: str
    full_text: str
    total_pages: int
    chunks: List[DocumentChunk] = field(default_factory=list)
    tables: List[ExtractedTable] = field(default_factory=list)
    charts: List[ExtractedChart] = field(default_factory=list)


class DocumentAIParser:
    """Client for processing PDFs through Document AI Layout / Form Parser."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        processor_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        self.project_id = project_id or settings.gcp_project_id
        self.location = location or settings.document_ai_location
        self.processor_id = processor_id or settings.document_ai_processor_id
        self.output_dir = output_dir or settings.processed_data_dir
        self.chart_cropper = ChartCropper(output_dir=self.output_dir / "charts")

        self._client = None
        self._is_mock = (
            self.processor_id == "mock-processor-id"
            or self.project_id == "demo-gcp-project"
            or not settings.google_application_credentials and not self._has_adc()
        )

    @staticmethod
    def _has_adc() -> bool:
        """Checks if Application Default Credentials exist."""
        try:
            import google.auth
            _, _ = google.auth.default()
            return True
        except Exception:
            return False

    def _get_client(self) -> Any:
        """Initializes DocumentProcessorServiceClient on demand."""
        if self._client is None:
            from google.cloud import documentai
            client_options = {"api_endpoint": f"{self.location}-documentai.googleapis.com"}
            credentials = None
            if settings.google_application_credentials:
                cred_path = Path(settings.google_application_credentials).resolve()
                if cred_path.exists():
                    from google.oauth2 import service_account
                    credentials = service_account.Credentials.from_service_account_file(str(cred_path))
            self._client = documentai.DocumentProcessorServiceClient(
                client_options=client_options,
                credentials=credentials,
            )
        return self._client

    def process_pdf_bytes(
        self,
        pdf_bytes: bytes,
        doc_id: str = "document",
    ) -> ParsedDocument:
        """Processes raw PDF bytes through Document AI or mock parser."""
        if self._is_mock:
            logger.info("Using mock/fallback parser for Document AI (offline mode).")
            return self._mock_parse(pdf_bytes, doc_id)

        from google.cloud import documentai

        client = self._get_client()
        name = client.processor_path(self.project_id, self.location, self.processor_id)

        raw_document = documentai.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        )

        request = documentai.ProcessRequest(
            name=name,
            raw_document=raw_document,
        )

        logger.info(f"Submitting document {doc_id} ({len(pdf_bytes)} bytes) to Document AI...")
        result = client.process_document(request=request)
        document = result.document

        return self._extract_structured_document(document, doc_id, pdf_bytes)

    def process_file(self, file_path: Union[str, Path], doc_id: Optional[str] = None) -> ParsedDocument:
        """Processes a local PDF file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at: {path}")

        document_id = doc_id or path.stem
        with open(path, "rb") as f:
            pdf_bytes = f.read()

        return self.process_pdf_bytes(pdf_bytes, doc_id=document_id)

    def _extract_structured_document(
        self,
        document: Any,
        doc_id: str,
        pdf_bytes: bytes,
    ) -> ParsedDocument:
        """Extracts text blocks, tables, and visual elements from Document AI Document proto."""
        full_text = getattr(document, "text", "")
        pages = getattr(document, "pages", [])
        total_pages = len(pages)

        parsed = ParsedDocument(
            doc_id=doc_id,
            full_text=full_text,
            total_pages=total_pages,
        )

        chunk_counter = 0

        # Handle modern Document AI Layout Parser format (document.document_layout)
        document_layout = getattr(document, "document_layout", None)
        if document_layout and hasattr(document_layout, "blocks") and document_layout.blocks:
            logger.info("Extracting structured blocks from Document AI document_layout...")
            all_text_pieces: List[str] = []

            def _extract_text(b: Any) -> str:
                t = []
                if getattr(b, "text_block", None) and b.text_block.text:
                    t.append(b.text_block.text)
                for sub in getattr(getattr(b, "text_block", None), "blocks", []):
                    t.append(_extract_text(sub))
                return " ".join(filter(None, t))

            def _walk_layout_block(block: Any, current_page: int = 1):
                nonlocal chunk_counter
                ps = getattr(block, "page_span", None)
                if ps and ps.page_start:
                    current_page = ps.page_start

                # 1. Process Table Block
                tb = getattr(block, "table_block", None)
                if tb:
                    headers: List[List[str]] = []
                    body: List[List[str]] = []
                    for r in getattr(tb, "header_rows", []):
                        headers.append([" ".join(_extract_text(sub) for sub in c.blocks).strip() for c in r.cells])
                    for r in getattr(tb, "body_rows", []):
                        body.append([" ".join(_extract_text(sub) for sub in c.blocks).strip() for c in r.cells])

                    if headers or body:
                        md_table = TableExtractor.table_to_markdown(headers, body) if headers else TableExtractor.table_to_markdown([body[0]], body[1:])
                        extracted_table = ExtractedTable(
                            table_id=f"{doc_id}_table_{len(parsed.tables) + 1}",
                            page_number=current_page,
                            markdown=md_table,
                            num_rows=len(headers) + len(body),
                            num_cols=len(headers[0]) if headers else (len(body[0]) if body else 0),
                            bounding_box=BoundingBox(),
                        )
                        parsed.tables.append(extracted_table)
                        chunk_counter += 1
                        parsed.chunks.append(
                            DocumentChunk(
                                chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                                doc_id=doc_id,
                                page_number=current_page,
                                content_type="table",
                                content=md_table,
                                metadata={"table_id": extracted_table.table_id, "page_number": current_page},
                            )
                        )

                # 2. Process Text Block
                tx = getattr(block, "text_block", None)
                if tx:
                    txt = tx.text.strip() if tx.text else ""
                    if txt and len(txt) > 15:
                        all_text_pieces.append(txt)
                        chunk_counter += 1
                        parsed.chunks.append(
                            DocumentChunk(
                                chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                                doc_id=doc_id,
                                page_number=current_page,
                                content_type="text",
                                content=txt,
                                metadata={"page_number": current_page},
                            )
                        )
                    for sub in getattr(tx, "blocks", []):
                        _walk_layout_block(sub, current_page)

            for root_b in document_layout.blocks:
                _walk_layout_block(root_b)

            if not parsed.full_text and all_text_pieces:
                parsed.full_text = "\n\n".join(all_text_pieces)

        # Handle legacy document.pages format (Form Parser / OCR)
        elif pages:
            # Attempt to render page images using PyMuPDF if available
            page_images: Dict[int, Any] = {}
            try:
                import fitz
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page_idx in range(len(doc)):
                    page = doc.load_page(page_idx)
                    pix = page.get_pixmap(dpi=150)
                    from PIL import Image
                    import io
                    page_images[page_idx + 1] = Image.open(io.BytesIO(pix.tobytes("png")))
            except Exception as e:
                logger.debug(f"Could not render pages via PyMuPDF: {e}")

            for page_idx, page in enumerate(pages):
                page_num = page_idx + 1
                page_image = page_images.get(page_num)

                # 1. Extract Tables
                if hasattr(page, "tables") and page.tables:
                    for t_idx, table in enumerate(page.tables):
                        extracted_table = TableExtractor.extract_table(
                            table, full_text, page_number=page_num, table_index=t_idx
                        )
                        parsed.tables.append(extracted_table)
                        chunk_counter += 1
                        parsed.chunks.append(
                            DocumentChunk(
                                chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                                doc_id=doc_id,
                                page_number=page_num,
                                content_type="table",
                                content=extracted_table.markdown,
                                metadata={
                                    "table_id": extracted_table.table_id,
                                    "num_rows": extracted_table.num_rows,
                                    "num_cols": extracted_table.num_cols,
                                    "page_number": page_num,
                                },
                            )
                        )

                # 2. Extract Visual Elements (Charts & Figures)
                if hasattr(page, "visual_elements") and page.visual_elements and page_image:
                    for v_idx, visual in enumerate(page.visual_elements):
                        extracted_chart = self.chart_cropper.process_visual_element(
                            page_image=page_image,
                            visual_element=visual,
                            doc_id=doc_id,
                            page_number=page_num,
                            element_index=v_idx,
                        )
                        if extracted_chart:
                            parsed.charts.append(extracted_chart)
                            chunk_counter += 1
                            parsed.chunks.append(
                                DocumentChunk(
                                    chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                                    doc_id=doc_id,
                                    page_number=page_num,
                                    content_type="chart",
                                    content=f"[Visual Figure: {extracted_chart.chart_id}] {extracted_chart.caption}",
                                    image_path=extracted_chart.image_path,
                                    metadata={
                                        "chart_id": extracted_chart.chart_id,
                                        "page_number": page_num,
                                    },
                                )
                            )

                # 3. Extract Text Paragraphs / Blocks
                if hasattr(page, "paragraphs") and page.paragraphs:
                    for p_idx, para in enumerate(page.paragraphs):
                        anchor = getattr(getattr(para, "layout", None), "text_anchor", None)
                        para_text = TableExtractor._get_text_from_anchor(full_text, anchor)
                        if para_text and len(para_text) > 20:
                            chunk_counter += 1
                            parsed.chunks.append(
                                DocumentChunk(
                                    chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                                    doc_id=doc_id,
                                    page_number=page_num,
                                    content_type="text",
                                    content=para_text,
                                    metadata={"page_number": page_num, "paragraph_index": p_idx},
                                )
                            )

        # 3. Always extract embedded chart and figure images directly from the PDF
        charts_dir = self.output_dir / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if parsed.total_pages == 0:
                parsed.total_pages = len(doc)
            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                page = doc.load_page(page_idx)
                for img_idx, img_info in enumerate(page.get_images()):
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    img_ext = base_image.get("ext", "png")
                    chart_filename = f"{doc_id}_p{page_num}_chart_{img_idx}.{img_ext}"
                    chart_path = charts_dir / chart_filename
                    chart_path.write_bytes(image_bytes)

                    from PIL import Image
                    import io
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    extracted_chart = ExtractedChart(
                        chart_id=f"{doc_id}_p{page_num}_chart_{img_idx}",
                        page_number=page_num,
                        image_path=str(chart_path),
                        bounding_box=BoundingBox(),
                        width_px=pil_img.width,
                        height_px=pil_img.height,
                        caption=f"Visual chart extracted from page {page_num}",
                    )
                    parsed.charts.append(extracted_chart)
                    chunk_counter += 1
                    parsed.chunks.append(
                        DocumentChunk(
                            chunk_id=f"{doc_id}_chunk_{chunk_counter}",
                            doc_id=doc_id,
                            page_number=page_num,
                            content_type="chart",
                            content=f"[Visual Figure: {extracted_chart.chart_id}] {extracted_chart.caption}",
                            image_path=str(chart_path),
                            metadata={
                                "chart_id": extracted_chart.chart_id,
                                "page_number": page_num,
                            },
                        )
                    )
        except Exception as e:
            logger.warning(f"Error extracting embedded PDF chart images: {e}")

        return parsed

    def _mock_parse(self, pdf_bytes: bytes, doc_id: str) -> ParsedDocument:
        """Generates realistic structured chunks for offline development and test suites."""
        # Check if PyMuPDF or pypdf can extract raw text
        extracted_text = ""
        total_pages = 1
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            total_pages = len(reader.pages)
            extracted_text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            extracted_text = "Sample extracted document text with financial figures and operational metrics."

        parsed = ParsedDocument(
            doc_id=doc_id,
            full_text=extracted_text,
            total_pages=total_pages,
        )

        # Mock Sample Text Chunk
        parsed.chunks.append(
            DocumentChunk(
                chunk_id=f"{doc_id}_chunk_1",
                doc_id=doc_id,
                page_number=1,
                content_type="text",
                content=extracted_text[:500] if extracted_text else "Enterprise Q3 Financial Overview: Revenue grew 18% YoY.",
                metadata={"page_number": 1, "section": "Executive Summary"},
            )
        )

        # Mock Sample Table
        mock_table_md = "| Metric | Q3 2025 | Q3 2026 | Change |\n| --- | --- | --- | --- |\n| Revenue ($M) | 120.4 | 142.1 | +18.0% |\n| Operating Margin | 22.1% | 24.5% | +240 bps |"
        parsed.chunks.append(
            DocumentChunk(
                chunk_id=f"{doc_id}_chunk_2",
                doc_id=doc_id,
                page_number=1,
                content_type="table",
                content=mock_table_md,
                metadata={"table_id": "table_1", "page_number": 1},
            )
        )

        return parsed
