"""Table extraction and Markdown conversion from Document AI structures."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class BoundingBox:
    """Normalized bounding box coordinates [0.0, 1.0]."""
    top: float = 0.0
    left: float = 0.0
    bottom: float = 0.0
    right: float = 0.0


@dataclass
class ExtractedTable:
    """Structured representation of an extracted table."""
    table_id: str
    page_number: int
    markdown: str
    num_rows: int
    num_cols: int
    bounding_box: BoundingBox
    raw_cells: List[List[str]] = field(default_factory=list)


class TableExtractor:
    """Extracts and standardizes tables from Document AI Page.Table objects."""

    @staticmethod
    def _get_text_from_anchor(document_text: str, text_anchor: Any) -> str:
        """Extracts text slice from Document AI text_anchor."""
        if not text_anchor or not hasattr(text_anchor, "text_segments") or not text_anchor.text_segments:
            return ""
        
        extracted_parts = []
        for segment in text_anchor.text_segments:
            start_index = int(segment.start_index) if hasattr(segment, "start_index") and segment.start_index else 0
            end_index = int(segment.end_index) if hasattr(segment, "end_index") and segment.end_index else len(document_text)
            extracted_parts.append(document_text[start_index:end_index])
        
        # Clean cell text: strip whitespace and replace internal newlines with spaces
        raw_text = "".join(extracted_parts).strip()
        return " ".join(raw_text.split())

    @classmethod
    def _extract_bounding_box(cls, layout: Any) -> BoundingBox:
        """Extracts normalized bounding box from layout bounding polygon."""
        if not layout or not hasattr(layout, "bounding_poly") or not layout.bounding_poly:
            return BoundingBox()
        
        poly = layout.bounding_poly
        vertices = getattr(poly, "normalized_vertices", [])
        if not vertices:
            return BoundingBox()
        
        min_x = min(getattr(v, "x", 0.0) for v in vertices)
        max_x = max(getattr(v, "x", 0.0) for v in vertices)
        min_y = min(getattr(v, "y", 0.0) for v in vertices)
        max_y = max(getattr(v, "y", 0.0) for v in vertices)
        
        return BoundingBox(top=min_y, left=min_x, bottom=max_y, right=max_x)

    @classmethod
    def table_to_markdown(
        cls,
        header_rows: List[List[str]],
        body_rows: List[List[str]],
    ) -> str:
        """Converts raw 2D string grid to GitHub Flavored Markdown."""
        all_rows = header_rows + body_rows
        if not all_rows:
            return ""

        # Determine column count
        max_cols = max(len(row) for row in all_rows)
        if max_cols == 0:
            return ""

        # Normalize row lengths
        normalized_headers = [
            row + [""] * (max_cols - len(row)) for row in header_rows
        ]
        normalized_body = [
            row + [""] * (max_cols - len(row)) for row in body_rows
        ]

        # Escape pipe symbols in cell text
        def clean_cell(text: str) -> str:
            return text.replace("|", "\\|").strip()

        lines: List[str] = []
        if normalized_headers:
            for row in normalized_headers:
                lines.append("| " + " | ".join(clean_cell(c) for c in row) + " |")
            # Separator row
            lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        else:
            # If no header rows are identified, generate generic headers
            lines.append("| " + " | ".join([f"Col {i+1}" for i in range(max_cols)]) + " |")
            lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        for row in normalized_body:
            lines.append("| " + " | ".join(clean_cell(c) for c in row) + " |")

        return "\n".join(lines)

    @classmethod
    def extract_table(
        cls,
        table_obj: Any,
        document_text: str,
        page_number: int,
        table_index: int = 0,
    ) -> ExtractedTable:
        """Processes a single Document AI Table protobuf object into an ExtractedTable."""
        header_rows: List[List[str]] = []
        body_rows: List[List[str]] = []

        # Process Header Rows
        if hasattr(table_obj, "header_rows") and table_obj.header_rows:
            for row in table_obj.header_rows:
                cells = []
                for cell in getattr(row, "cells", []):
                    anchor = getattr(getattr(cell, "layout", None), "text_anchor", None)
                    cells.append(cls._get_text_from_anchor(document_text, anchor))
                header_rows.append(cells)

        # Process Body Rows
        if hasattr(table_obj, "body_rows") and table_obj.body_rows:
            for row in table_obj.body_rows:
                cells = []
                for cell in getattr(row, "cells", []):
                    anchor = getattr(getattr(cell, "layout", None), "text_anchor", None)
                    cells.append(cls._get_text_from_anchor(document_text, anchor))
                body_rows.append(cells)

        layout = getattr(table_obj, "layout", None)
        bbox = cls._extract_bounding_box(layout)
        markdown = cls.table_to_markdown(header_rows, body_rows)
        all_rows = header_rows + body_rows
        num_rows = len(all_rows)
        num_cols = max((len(r) for r in all_rows), default=0)

        return ExtractedTable(
            table_id=f"page_{page_number}_table_{table_index}",
            page_number=page_number,
            markdown=markdown,
            num_rows=num_rows,
            num_cols=num_cols,
            bounding_box=bbox,
            raw_cells=all_rows,
        )
