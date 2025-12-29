import logging
import uuid
from typing import List, Dict, Any, Optional

from rag.embeddings import Embeddings, EmbeddingError
from rag.chroma_client import ChromaClient, ChromaUnavailable
from utils.mongo_db import get_rag_documents_collection, get_tenant_id
from utils.tdos_events import emit_event

logger = logging.getLogger(__name__)


def chunk_text(text: str, max_words: int = 200) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i : i + max_words]))
    return chunks or [text]


def ingest(
    source: str,
    title: str,
    text: str,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ingest a document into Chroma and MongoDB rag_documents with tenant scoping."""
    tenant_id = get_tenant_id()
    tags = tags or []
    metadata = metadata or {}

    try:
        embedder = Embeddings()
        chroma = ChromaClient()
    except (EmbeddingError, ChromaUnavailable) as exc:
        logger.error("[RAG] Ingest failed: %s", exc)
        raise

    chunks = chunk_text(text)
    embeddings = embedder.encode(chunks)

    doc_ids = [f"doc-{uuid.uuid4()}" for _ in chunks]
    metadatas = [
        {
            "tenant_id": tenant_id,
            "source": source,
            "title": title,
            "chunk_index": idx,
            "tags": tags,
            **metadata,
        }
        for idx in range(len(chunks))
    ]

    chroma.add(ids=doc_ids, embeddings=embeddings, metadatas=metadatas)

    rag_collection = get_rag_documents_collection()
    rag_docs = []
    for chunk_id, chunk, meta in zip(doc_ids, chunks, metadatas):
        rag_docs.append(
            {
                "_id": chunk_id,
                "tenant_id": tenant_id,
                "source": source,
                "title": title,
                "text": chunk,
                "metadata": meta,
            }
        )
    if rag_docs:
        rag_collection.insert_many(rag_docs)

    emit_event(
        "RAG.QUERY",  # Using RAG.QUERY to reuse allowed set; adjust if new event type added
        {
            "action": "ingest",
            "source": source,
            "title": title,
            "chunks": len(chunks),
            "tags": tags,
        },
    )
    return {"ingested_chunks": len(chunks), "doc_ids": doc_ids}


def query(text: str, top_k: int = 3) -> Dict[str, Any]:
    tenant_id = get_tenant_id()
    try:
        embedder = Embeddings()
        chroma = ChromaClient()
    except (EmbeddingError, ChromaUnavailable) as exc:
        logger.error("[RAG] Query failed: %s", exc)
        raise

    embedding = embedder.encode([text])
    results = chroma.query(query_embeddings=embedding, top_k=top_k)

    emit_event(
        "RAG.QUERY",
        {
            "action": "query",
            "top_k": top_k,
            "prompt_length": len(text),
        },
    )

    # Filter by tenant_id in metadata
    filtered = []
    metadatas = results.get("metadatas", [[]])[0]
    documents = results.get("documents", [[]])[0]
    ids = results.get("ids", [[]])[0]
    for doc_id, meta, doc in zip(ids, metadatas, documents):
        if not meta or meta.get("tenant_id") != tenant_id:
            continue
        filtered.append({
            "id": doc_id,
            "text": doc,
            "metadata": meta,
        })

    return {"results": filtered}
