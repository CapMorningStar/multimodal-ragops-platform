"""Vertex AI Multimodal Embeddings wrapper.

Interacts with Vertex AI `multimodalembedding@001` to generate unified 1408-dim
embeddings for text blocks, Markdown tables, and cropped image PNGs.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, List, Optional, Union

import numpy as np
from PIL import Image

from config.settings import settings

logger = logging.getLogger(__name__)


class VertexMultimodalEmbedder:
    """Client for generating multimodal embeddings using Vertex AI or deterministic mock."""

    DIMENSION: int = 1408

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.project_id = project_id or settings.gcp_project_id
        self.location = location or settings.gcp_region
        self.model_name = model_name or settings.vertex_multimodal_embedding_model

        self._is_mock = (
            self.project_id == "demo-gcp-project"
            or not settings.google_application_credentials and not self._has_adc()
        )
        self._model = None

    @staticmethod
    def _has_adc() -> bool:
        """Checks if GCP Application Default Credentials exist."""
        try:
            import google.auth
            _, _ = google.auth.default()
            return True
        except Exception:
            return False

    def _get_model(self) -> Any:
        """Loads the Vertex AI MultiModalEmbeddingModel on demand."""
        if self._model is None and not self._is_mock:
            try:
                import vertexai
                from vertexai.vision_models import MultiModalEmbeddingModel

                vertexai.init(project=self.project_id, location=self.location)
                self._model = MultiModalEmbeddingModel.from_pretrained(self.model_name)
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI client ({e}). Falling back to mock embedder.")
                self._is_mock = True
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        """Generates a normalized 1408-dim embedding for text."""
        if self._is_mock:
            return self._mock_embed(text)

        try:
            model = self._get_model()
            embeddings = model.get_embeddings(
                contextual_text=text[:1000],  # vertex limit safe slice
                dimension=self.DIMENSION,
            )
            vec = np.array(embeddings.text_embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-12)
        except Exception as e:
            logger.warning(f"Vertex text embedding error: {e}. Using deterministic fallback.")
            return self._mock_embed(text)

    def embed_image(self, image_input: Union[str, Path, Image.Image]) -> np.ndarray:
        """Generates a normalized 1408-dim embedding for an image."""
        if self._is_mock:
            img_desc = str(image_input) if isinstance(image_input, (str, Path)) else "image_object"
            return self._mock_embed(f"image::{img_desc}")

        try:
            from vertexai.vision_models import Image as VertexImage

            if isinstance(image_input, (str, Path)):
                v_img = VertexImage.load_from_file(str(image_input))
            elif isinstance(image_input, Image.Image):
                import io
                buf = io.BytesIO()
                image_input.save(buf, format="PNG")
                v_img = VertexImage(buf.getvalue())
            else:
                raise ValueError(f"Unsupported image input type: {type(image_input)}")

            model = self._get_model()
            embeddings = model.get_embeddings(
                image=v_img,
                dimension=self.DIMENSION,
            )
            vec = np.array(embeddings.image_embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-12)
        except Exception as e:
            logger.warning(f"Vertex image embedding error: {e}. Using deterministic fallback.")
            return self._mock_embed(f"image::{image_input}")

    def embed_batch_texts(self, texts: List[str]) -> np.ndarray:
        """Generates embeddings for a batch of text strings."""
        return np.vstack([self.embed_text(t) for t in texts])

    def _mock_embed(self, seed_text: str) -> np.ndarray:
        """Generates a deterministic, normalized 1408-dim pseudo-vector using sha256."""
        h = hashlib.sha256(seed_text.encode("utf-8")).digest()
        # Seed a pseudo-random generator with the hash
        seed = int.from_bytes(h[:4], "big")
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.DIMENSION).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-12)
