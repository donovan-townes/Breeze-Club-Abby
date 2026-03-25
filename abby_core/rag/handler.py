import logging
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from abby_core.rag.embeddings import Embeddings, EmbeddingError
from abby_core.rag.chroma_client import ChromaClient, ChromaUnavailable
from abby_core.rag.prepare import prepare_rag_text, validate_prepared_text
from abby_core.database.collections.rag_documents import (
    get_document_by_id,
    get_max_version_for_document,
    insert_rag_chunks,
    list_documents_grouped,
    get_documents_for_query,
    delete_documents_by_id,
)
from abby_core.observability.telemetry import emit_event

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:100]  # Limit length


def generate_document_id(document_type: str, title: str, version: int = 1) -> str:
    """Generate canonical document identifier.
    
    Format: {document_type}::{slugified_title}::v{version}
    Example: guidelines::breeze-club-rules::v1
    """
    slug = slugify(title)
    return f"{document_type}::{slug}::v{version}"


def extract_content_only(text: str) -> str:
    """Extract just the CONTENT section from canonical format.
    
    Removes TITLE: and SCOPE: headers to get clean content for embedding.
    Used for ChromaDB storage; metadata contains title/scope separately.
    """
    # If text starts with TITLE:, extract everything after CONTENT:
    if text.startswith("TITLE:"):
        match = re.search(r"CONTENT:\s*\n(.*)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # If no TITLE: prefix, return as-is (already clean)
    return text


def chunk_text(text: str, max_words: int = 200) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i : i + max_words]))
    return chunks or [text]


def ingest(
    document_type: str,
    title: str,
    text: str,
    user_id: Optional[str] = None,
    guild_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    scope: Optional[str] = None,
    version: int = 1,
    auto_prepare: bool = True,
) -> Dict[str, Any]:
    """
    Ingest a document into RAG system with canonical schema.
    
    Args:
        document_type: Document type (e.g., "guidelines", "policy", "faq", "weekly_summary")
        title: Human-readable document title
        text: Raw text content (will be cleaned if auto_prepare=True)
        user_id: User who created this document
        guild_id: Guild scoping for multi-tenant isolation
        tags: Optional tags list for categorization
        scope: Content scope (e.g., "community", "rules", "submissions")
        version: Document version number (default: 1)
        auto_prepare: If True, run prepare_rag_text() on input (default: True)
    
    Returns:
        {"document_id": str, "ingested_chunks": int, "chunk_ids": List[str], "version": int}
    """
    tags = tags or []

    # Prepare text if requested (default behavior)
    if auto_prepare:
        text = prepare_rag_text(text, title=title, scope=scope)
        logger.info("[RAG] Prepared text: %d words", len(text.split()))
    
    # Validate
    validation = validate_prepared_text(text)
    if not validation["valid"]:
        logger.warning("[RAG] Text validation warnings: %s", validation["warnings"])
    
    try:
        embedder = Embeddings()
        chroma = ChromaClient()
    except (EmbeddingError, ChromaUnavailable) as exc:
        logger.error("[RAG] Ingest failed: %s", exc)
        raise

    # Generate canonical document ID
    document_id = generate_document_id(document_type, title, version)
    
    # Idempotency check: if document_id exists, auto-increment version
    existing = get_document_by_id(document_id)
    
    if existing:
        # Find highest version for this document_type + title + guild
        next_version = get_max_version_for_document(document_type, title) + 1
        
        # Regenerate document_id with incremented version
        document_id = generate_document_id(document_type, title, next_version)
        version = next_version
        logger.info("[RAG] Document exists, auto-incremented to v%d", version)
    
    # Extract clean content (without TITLE:/SCOPE: headers) for embedding
    clean_content = extract_content_only(text)
    chunks = chunk_text(clean_content)
    embeddings = embedder.encode(chunks)

    # Generate chunk IDs tied to document
    chunk_ids = [f"{document_id}::chunk_{idx}" for idx in range(len(chunks))]
    
    # Build vector DB metadata (only what's needed for filtering/retrieval)
    metadatas = []
    for idx in range(len(chunks)):
        meta = {
            "document_id": document_id,
            "document_type": document_type,
            "chunk_index": str(idx),
            "scope": scope or "general",
        }
        
        # Only include optional fields if they have values (ChromaDB rejects None)
        if guild_id:
            meta["guild_id"] = guild_id
        if tags:
            meta["tags"] = ",".join(tags)
        
        metadatas.append(meta)

    chroma.add(ids=chunk_ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)

    # MongoDB documents (source of truth)
    now = datetime.now(timezone.utc)
    rag_docs = []
    for idx, (chunk_id, chunk) in enumerate(zip(chunk_ids, chunks)):
        rag_docs.append(
            {
                "_id": chunk_id,
                "document_id": document_id,  # Canonical identifier
                "document_type": document_type,
                "title": title,
                "version": version,
                
                "chunk_index": idx,
                "content": chunk,
                
                "scope": scope or "general",
                "tags": tags,
                
                "guild_id": guild_id,
                "tenant_id": guild_id,  # TDOS compatibility
                
                "created_by": user_id,
                "created_at": now,
                
                "embedding_ref": {
                    "provider": "chroma",
                    "collection": "abby_rag",
                    "vector_id": chunk_id
                }
            }
        )
    
    if rag_docs:
        insert_rag_chunks(rag_docs)

    emit_event(
        "RAG.QUERY",  # Only valid RAG event type
        {
            "action": "ingest",
            "document_id": document_id,
            "document_type": document_type,
            "title": title,
            "chunks": len(chunks),
            "version": version,
        },
    )
    
    logger.info("[RAG] Ingested %s (%d chunks, v%d)", document_id, len(chunks), version)
    
    return {
        "document_id": document_id,
        "ingested_chunks": len(chunks),
        "chunk_ids": chunk_ids,
        "version": version
    }


def query(
    text: str, 
    user_id: Optional[str] = None, 
    guild_id: Optional[str] = None, 
    document_type: Optional[str] = None,
    scope: Optional[str] = None,
    top_k: int = 3
) -> Dict[str, Any]:
    """Query RAG documents with optional filtering.
    
    Args:
        text: Query text
        user_id: Filter by user (currently unused, kept for compatibility)
        guild_id: Filter by guild
        document_type: Filter by document type
        scope: Filter by scope
        top_k: Number of results to return
    
    Returns:
        {"results": [{"id": str, "text": str, "metadata": dict}]}
    """
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

    # Filter by guild_id/document_type/scope in metadata
    filtered = []
    metadatas = results.get("metadatas", [[]])[0]
    documents = results.get("documents", [[]])[0]
    ids = results.get("ids", [[]])[0]
    
    for doc_id, meta, doc in zip(ids, metadatas, documents):
        if not meta:
            continue
        
        # Apply filters
        if guild_id and meta.get("guild_id") != guild_id:
            continue
        if document_type and meta.get("document_type") != document_type:
            continue
        if scope and meta.get("scope") != scope:
            continue
            
        filtered.append({
            "id": doc_id,
            "text": doc,
            "metadata": meta,
        })

    return {"results": filtered}


def list_documents(
    guild_id: Optional[str] = None,
    document_type: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List RAG documents grouped by document_id.
    
    Args:
        guild_id: Filter by guild
        document_type: Filter by document type
        scope: Filter by scope
        limit: Max documents to return (default 50)
    
    Returns:
        List of {document_id, title, document_type, scope, version, chunk_count, tags, created_at}
    """
    # Use collection helper for grouped aggregation
    results = list_documents_grouped(
        guild_id=guild_id,
        document_type=document_type,
        scope=scope,
        limit=limit
    )
    
    documents = []
    for doc in results:
        documents.append({
            "document_id": doc["_id"],
            "title": doc["title"],
            "document_type": doc["document_type"],
            "scope": doc.get("scope", "general"),
            "version": doc.get("version", 1),
            "chunk_count": doc["chunk_count"],
            "tags": doc.get("tags", []),
            "created_by": doc.get("created_by"),
            "created_at": doc.get("created_at"),
            "guild_id": doc.get("guild_id")
        })
    
    query_filter = {}
    if guild_id:
        query_filter["guild_id"] = guild_id
    if document_type:
        query_filter["document_type"] = document_type
    if scope:
        query_filter["scope"] = scope
    
    logger.info("[RAG] Listed %d documents (filter: %s)", len(documents), query_filter)
    return documents


def delete_documents(
    document_id: Optional[str] = None,
    document_type: Optional[str] = None,
    guild_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete RAG documents from both Mongo and Chroma by document_id.
    
    Args:
        document_id: Delete specific document by canonical ID
        document_type: Delete all documents of this type (dangerous!)
        guild_id: Restrict deletion to specific guild
    
    Returns:
        {"deleted_mongo": int, "deleted_chroma": int, "document_ids": List[str]}
    """
    if not any([document_id, document_type]):
        raise ValueError("Must provide document_id or document_type for deletion")
    
    # Build filter
    query_filter = {}
    if document_id:
        query_filter["document_id"] = document_id
    if document_type:
        query_filter["document_type"] = document_type
    if guild_id:
        query_filter["guild_id"] = guild_id
    
    # Get chunk IDs before deletion (need to collect document_ids affected)
    matching_docs = get_documents_for_query(guild_id=guild_id, document_type=document_type)
    if document_id:
        matching_docs = [d for d in matching_docs if d.get("document_id") == document_id]
    
    chunk_ids = [doc["_id"] for doc in matching_docs if "_id" in doc]
    affected_doc_ids = list(set([doc["document_id"] for doc in matching_docs if "document_id" in doc]))
    
    if not chunk_ids:
        logger.warning("[RAG] No documents matched deletion filter: %s", query_filter)
        return {"deleted_mongo": 0, "deleted_chroma": 0, "document_ids": []}
    
    # Delete from Mongo using collection helper
    mongo_deleted_count = 0
    for doc_id in affected_doc_ids:
        mongo_deleted_count += delete_documents_by_id(doc_id)
    
    # Delete from Chroma
    try:
        chroma = ChromaClient()
        chroma.collection.delete(ids=chunk_ids)
        chroma_count = len(chunk_ids)
    except ChromaUnavailable:
        logger.warning("[RAG] Chroma unavailable, skipped vector deletion")
        chroma_count = 0
    
    emit_event(
        "RAG.QUERY",  # Only valid RAG event type
        {
            "action": "delete",
            "filter": query_filter,
            "deleted_count": mongo_deleted_count,
            "document_ids": affected_doc_ids,
        },
    )
    
    logger.info("[RAG] Deleted %d chunks from Mongo (%d document_ids), %d from Chroma", 
                mongo_deleted_count, len(affected_doc_ids), chroma_count)
    
    return {
        "deleted_mongo": mongo_deleted_count,
        "deleted_chroma": chroma_count,
        "document_ids": affected_doc_ids  # Return canonical document IDs
    }

def rebuild_chroma_from_mongodb(guild_id: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild ChromaDB from MongoDB source of truth.
    
    Useful if ChromaDB is corrupted, deleted, or out of sync.
    Pulls all documents from MongoDB and re-embeds them into ChromaDB.
    
    Args:
        guild_id: Optionally rebuild only for a specific guild
        
    Returns:
        {
            "documents_processed": int,
            "chunks_indexed": int,
            "status": "success" | "error",
            "error": Optional[str]
        }
    """
    try:
        chroma = ChromaClient()
        embedder = Embeddings()
    except (ChromaUnavailable, EmbeddingError) as exc:
        logger.error("[RAG] Rebuild failed: %s", exc)
        return {
            "documents_processed": 0,
            "chunks_indexed": 0,
            "status": "error",
            "error": str(exc)
        }
    
    # Query MongoDB for all documents using collection helper
    all_chunks = get_documents_for_query(guild_id=guild_id)
    
    if not all_chunks:
        logger.info("[RAG] No documents found to rebuild")
        return {
            "documents_processed": 0,
            "chunks_indexed": 0,
            "status": "success",
            "error": None
        }
    
    # Group by document_id to count unique documents
    unique_docs = set(doc["document_id"] for doc in all_chunks)
    
    chunk_count = 0
    for chunk_doc in all_chunks:
        try:
            chunk_id = chunk_doc["_id"]
            # Use clean content (without TITLE:/SCOPE: headers)
            content = extract_content_only(chunk_doc["content"])
            
            embedding = embedder.encode([content])[0]
            
            meta = {
                "document_id": chunk_doc["document_id"],
                "document_type": chunk_doc["document_type"],
                "chunk_index": str(chunk_doc.get("chunk_index", 0)),
                "scope": chunk_doc.get("scope", "general"),
            }
            
            if chunk_doc.get("guild_id"):
                meta["guild_id"] = chunk_doc["guild_id"]
            if chunk_doc.get("tags"):
                meta["tags"] = chunk_doc["tags"]
            
            chroma.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[meta],
                documents=[content]
            )
            chunk_count += 1
        except Exception as exc:
            logger.error("[RAG] Failed to rebuild chunk %s: %s", chunk_doc.get("_id"), exc)
            continue
    
    logger.info("[RAG] Rebuilt ChromaDB: %d unique documents → %d chunks indexed", 
                len(unique_docs), chunk_count)
    
    return {
        "documents_processed": len(unique_docs),
        "chunks_indexed": chunk_count,
        "status": "success",
        "error": None
    }
    
    if not all_chunks:
        logger.info("[RAG] No documents found to rebuild")
        return {
            "documents_processed": 0,
            "chunks_indexed": 0,
            "status": "success",
            "error": None
        }
    
    # Group by document_id to count unique documents
    unique_docs = set(doc["document_id"] for doc in all_chunks)
    
    chunk_count = 0
    for chunk_doc in all_chunks:
        try:
            chunk_id = chunk_doc["_id"]
            # Use clean content (without TITLE:/SCOPE: headers)
            content = extract_content_only(chunk_doc["content"])
            
            embedding = embedder.encode([content])[0]
            
            meta = {
                "document_id": chunk_doc["document_id"],
                "document_type": chunk_doc["document_type"],
                "chunk_index": str(chunk_doc.get("chunk_index", 0)),
                "scope": chunk_doc.get("scope", "general"),
            }
            
            if chunk_doc.get("guild_id"):
                meta["guild_id"] = chunk_doc["guild_id"]
            if chunk_doc.get("tags"):
                meta["tags"] = chunk_doc["tags"]
            
            chroma.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[meta],
                documents=[content]
            )
            chunk_count += 1
        except Exception as exc:
            logger.error("[RAG] Failed to rebuild chunk %s: %s", chunk_doc.get("_id"), exc)
            continue
    
    logger.info("[RAG] Rebuilt ChromaDB: %d unique documents → %d chunks indexed", 
                len(unique_docs), chunk_count)
    
    return {
        "documents_processed": len(unique_docs),
        "chunks_indexed": chunk_count,
        "status": "success",
        "error": None
    }


def sync_check(guild_id: Optional[str] = None) -> Dict[str, Any]:
    """Check if MongoDB and ChromaDB are in sync.
    
    Compares document counts and chunk counts between the two databases.
    Useful for debugging sync issues or corruption.
    
    Args:
        guild_id: Optionally check only for a specific guild
        
    Returns:
        {
            "in_sync": bool,
            "mongodb": {
                "total_documents": int,
                "total_chunks": int,
                "unique_doc_ids": int
            },
            "chromadb": {
                "total_chunks": int
            },
            "discrepancies": List[str],
            "status": "ok" | "warning" | "error"
        }
    """
    try:
        chroma = ChromaClient()
    except ChromaUnavailable as exc:
        logger.error("[RAG] Sync check failed: %s", exc)
        return {
            "in_sync": False,
            "mongodb": {},
            "chromadb": {},
            "discrepancies": [f"ChromaDB unavailable: {exc}"],
            "status": "error"
        }
    
    # MongoDB stats using collection helper
    mongo_chunks = get_documents_for_query(guild_id=guild_id)
    mongo_doc_ids = set(doc["document_id"] for doc in mongo_chunks)
    
    # ChromaDB stats
    chroma_results = chroma.collection.get()
    chroma_chunk_count = len(chroma_results.get("ids", []))
    
    # Analysis
    discrepancies = []
    in_sync = True
    
    if len(mongo_chunks) != chroma_chunk_count:
        discrepancies.append(
            f"Chunk count mismatch: MongoDB has {len(mongo_chunks)}, "
            f"ChromaDB has {chroma_chunk_count}"
        )
        in_sync = False
    
    # Check for MongoDB chunks missing from ChromaDB
    if chroma_chunk_count > 0:
        chroma_ids = set(chroma_results.get("ids", []))
        mongo_ids = set(str(doc["_id"]) for doc in mongo_chunks)
        
        missing_in_chroma = mongo_ids - chroma_ids
        missing_in_mongo = chroma_ids - mongo_ids
        
        if missing_in_chroma:
            discrepancies.append(
                f"{len(missing_in_chroma)} MongoDB chunks missing from ChromaDB"
            )
            in_sync = False
        
        if missing_in_mongo:
            discrepancies.append(
                f"{len(missing_in_mongo)} ChromaDB chunks missing from MongoDB (orphaned)"
            )
            in_sync = False
    
    status = "ok" if in_sync else ("error" if not chroma_chunk_count else "warning")
    
    return {
        "in_sync": in_sync,
        "mongodb": {
            "total_documents": len(mongo_chunks),
            "total_chunks": len(mongo_chunks),
            "unique_doc_ids": len(mongo_doc_ids)
        },
        "chromadb": {
            "total_chunks": chroma_chunk_count
        },
        "discrepancies": discrepancies,
        "status": status
    }