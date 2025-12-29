import os
import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when embedding model is unavailable or encoding fails."""


class Embeddings:
    """Thin wrapper around sentence-transformers for portable embeddings."""

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.device = device or os.getenv("EMBEDDING_DEVICE", "cpu")

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - import-time dependency
            raise EmbeddingError(
                "sentence-transformers not installed. Add 'sentence-transformers' to requirements and reinstall."
            ) from exc

        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as exc:  # pragma: no cover
            raise EmbeddingError(f"Failed to load embedding model {self.model_name}: {exc}") from exc

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        try:
            return self.model.encode(list(texts), convert_to_numpy=False, show_progress_bar=False)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover
            raise EmbeddingError(f"Failed to encode texts: {exc}") from exc
