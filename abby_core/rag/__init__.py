"""RAG module: embeddings, vector store client, and handlers."""
from abby_core.rag.handler import ingest, query

__all__ = ["ingest", "query"]
