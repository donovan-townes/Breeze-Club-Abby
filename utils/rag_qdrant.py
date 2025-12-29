import os
from typing import List, Optional, Dict, Any
from utils.log_config import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
except Exception as e:
    QdrantClient = None  # type: ignore
    logger.warning("qdrant-client not installed; rag_qdrant will be unavailable.")


class QdrantWrapper:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, api_key: Optional[str] = None):
        if QdrantClient is None:
            raise RuntimeError("qdrant-client missing. Please install qdrant-client.")
        host = host or os.getenv("QDRANT_HOST", "localhost")
        port = port or int(os.getenv("QDRANT_PORT", "6333"))
        api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.client = QdrantClient(host=host, port=port, api_key=api_key)

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine"):
        collections = [c.name for c in self.client.get_collections().collections]
        if name not in collections:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance[distance])
            )

    def upsert(self, collection: str, points: List[Dict[str, Any]]):
        payloads = [PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {})) for p in points]
        self.client.upsert(collection_name=collection, points=payloads)

    def query(self, collection: str, vector: List[float], top_k: int = 3, filters: Optional[Dict[str, Any]] = None):
        return self.client.search(collection_name=collection, query_vector=vector, limit=top_k, query_filter=filters)
