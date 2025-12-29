import os
import sys
from typing import List, Dict, Any

from utils.log_config import setup_logging, logging
setup_logging()
logger = logging.getLogger(__name__)

DRY_RUN = os.getenv("MIGRATE_DRY_RUN", "false").lower() == "true"

try:
    import chromadb
except Exception:
    chromadb = None

from utils.rag_qdrant import QdrantWrapper


def fetch_chroma_items(collection_name: str) -> List[Dict[str, Any]]:
    if chromadb is None:
        raise RuntimeError("chromadb not installed.")
    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR", "./chroma"))
    col = client.get_or_create_collection(name=collection_name)
    # SDK returns mixed fields; standardize to id, vector, payload
    items = []
    results = col.get()
    for i, _id in enumerate(results.get("ids", [])):
        items.append({
            "id": _id,
            "vector": results.get("embeddings", [])[i],
            "payload": {
                "text": results.get("documents", [])[i],
                "metadata": results.get("metadatas", [])[i] if results.get("metadatas") else {}
            }
        })
    return items


def migrate(collection_name: str, vector_size: int):
    logger.info(f"Starting migration from Chroma -> Qdrant for collection '{collection_name}'")
    qdrant = QdrantWrapper()
    qdrant.ensure_collection(collection_name, vector_size)
    items = fetch_chroma_items(collection_name)
    logger.info(f"Fetched {len(items)} items from Chroma.")
    if DRY_RUN:
        logger.info("Dry run enabled — not writing to Qdrant.")
        return
    # Batch upserts to avoid large payloads
    batch = []
    for p in items:
        batch.append(p)
        if len(batch) >= 128:
            qdrant.upsert(collection_name, batch)
            batch = []
    if batch:
        qdrant.upsert(collection_name, batch)
    logger.info("Migration complete.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/migrate_chroma_to_qdrant.py <collection_name> <vector_size>")
        sys.exit(1)
    migrate(sys.argv[1], int(sys.argv[2]))
