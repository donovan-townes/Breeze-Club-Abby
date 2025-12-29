import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ChromaUnavailable(RuntimeError):
    """Raised when chromadb is not installed or unavailable."""


class ChromaClient:
    """Minimal ChromaDB client wrapper for persistence and search."""

    def __init__(self, collection_name: str = "abby_rag") -> None:
        self.collection_name = collection_name
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma-data")
        try:
            import chromadb  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ChromaUnavailable(
                "chromadb not installed. Add 'chromadb' to requirements and reinstall."
            ) from exc

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        logger.info("[RAG] Chroma collection ready at %s", self.persist_dir)

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]) -> None:
        self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def query(self, query_embeddings: List[List[float]], top_k: int = 3) -> Dict[str, Any]:
        return self.collection.query(query_embeddings=query_embeddings, n_results=top_k)
