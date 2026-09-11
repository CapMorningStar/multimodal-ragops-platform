"""Chart and visual element cropping from Document AI pages."""

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PIL import Image

from src.ingestion.table_extractor import BoundingBox


@dataclass
class ExtractedChart:
    """Structured representation of a cropped chart or visual figure."""
    chart_id: str
    page_number: int
    image_path: str
    bounding_box: BoundingBox
    width_px: int
    height_px: int
    caption: str = ""
    visual_type: str = "CHART"


class ChartCropper:
    """Crops visual elements from Document AI page representations."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./data/processed/charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _extract_bounding_box(layout: Any) -> BoundingBox:
        """Extracts normalized bounding box from layout bounding polygon."""
        if not layout or not hasattr(layout, "bounding_poly") or not layout.bounding_poly:
            return BoundingBox()

        poly = layout.bounding_poly
        vertices = getattr(poly, "normalized_vertices", [])
        if not vertices:
            return BoundingBox()

        min_x = max(0.0, min(getattr(v, "x", 0.0) for v in vertices))
        max_x = min(1.0, max(getattr(v, "x", 0.0) for v in vertices))
        min_y = max(0.0, min(getattr(v, "y", 0.0) for v in vertices))
        max_y = min(1.0, max(getattr(v, "y", 0.0) for v in vertices))

        return BoundingBox(top=min_y, left=min_x, bottom=max_y, right=max_x)

    def crop_bounding_box(
        self,
        page_image: Image.Image,
        bbox: BoundingBox,
        padding_ratio: float = 0.02,
    ) -> Image.Image:
        """Crops page image using normalized bounding coordinates with optional padding."""
        img_w, img_h = page_image.size

        # Apply padding ratio to ensure axis labels/legends are preserved
        pad_x = (bbox.right - bbox.left) * padding_ratio
        pad_y = (bbox.bottom - bbox.top) * padding_ratio

        left = max(0, int((bbox.left - pad_x) * img_w))
        top = max(0, int((bbox.top - pad_y) * img_h))
        right = min(img_w, int((bbox.right + pad_x) * img_w))
        bottom = min(img_h, int((bbox.bottom + pad_y) * img_h))

        # Enforce minimum dimension of 10x10 px to avoid invalid crops
        if right - left < 10:
            right = min(img_w, left + 10)
        if bottom - top < 10:
            bottom = min(img_h, top + 10)

        return page_image.crop((left, top, right, bottom))

    def process_visual_element(
        self,
        page_image: Image.Image,
        visual_element: Any,
        doc_id: str,
        page_number: int,
        element_index: int = 0,
        caption: str = "",
    ) -> Optional[ExtractedChart]:
        """Crops and saves a single visual element to disk."""
        layout = getattr(visual_element, "layout", None)
        bbox = self._extract_bounding_box(layout)

        # Skip zero-sized elements
        if (bbox.right - bbox.left) <= 0.01 or (bbox.bottom - bbox.top) <= 0.01:
            return None

        visual_type = getattr(visual_element, "type_", "CHART")
        chart_id = f"{doc_id}_p{page_number}_visual_{element_index}"
        filename = f"{chart_id}.png"
        save_path = self.output_dir / filename

        cropped_img = self.crop_bounding_box(page_image, bbox)
        cropped_img.save(str(save_path), format="PNG")

        return ExtractedChart(
            chart_id=chart_id,
            page_number=page_number,
            image_path=str(save_path.resolve()),
            bounding_box=bbox,
            width_px=cropped_img.width,
            height_px=cropped_img.height,
            caption=caption,
            visual_type=str(visual_type),
        )

    def crop_from_page_image_bytes(
        self,
        image_bytes: bytes,
        bbox: BoundingBox,
        doc_id: str,
        page_number: int,
        element_index: int = 0,
        caption: str = "",
    ) -> Optional[ExtractedChart]:
        """Convenience method to crop directly from raw image bytes."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            chart_id = f"{doc_id}_p{page_number}_visual_{element_index}"
            save_path = self.output_dir / f"{chart_id}.png"

            cropped_img = self.crop_bounding_box(img, bbox)
            cropped_img.save(str(save_path), format="PNG")

            return ExtractedChart(
                chart_id=chart_id,
                page_number=page_number,
                image_path=str(save_path.resolve()),
                bounding_box=bbox,
                width_px=cropped_img.width,
                height_px=cropped_img.height,
                caption=caption,
                visual_type="CHART",
            )
        except Exception as e:
            return None
