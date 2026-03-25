# RAG System Guide

Comprehensive guide to Abby's Retrieval-Augmented Generation system: ChromaDB (dev), Qdrant (production), ingestion pipeline, migration, and performance optimization.

**Last Updated:** January 31, 2026  
**Deployment:** ChromaDB (development), Qdrant (production)  
**Scaling:** 1–100+ guilds with complete isolation

---

## Executive Summary

RAG (Retrieval-Augmented Generation) enables Abby to ground responses in guild-specific documents:

1. **Ingestion** — Guild documents → chunks → embeddings → vector storage
2. **Query** — User question → embedding → semantic search → format for LLM
3. **Lifecycle** — Document versioning, guild isolation, quota enforcement

### Performance Baseline:

- Development (ChromaDB): p50 latency 300ms, throughput 20 QPS
- Production (Qdrant): p50 latency 80ms, throughput 150 QPS (73% faster, 7.5x throughput)

---

## Architecture Overview

### Development vs. Production

| Aspect | ChromaDB | Qdrant |
| -------- | ---------- | -------- |
| **Deployment** | Local persistent storage | Managed cloud service |
| **Latency** | ~300ms p50 | ~80ms p50 |
| **Throughput** | 20 QPS | 150 QPS |
| **Scalability** | Single guild or small testing | 100+ guilds in production |
| **Data Persistence** | `chroma_db/` directory | Qdrant cloud backup |
| **Upgrade Path** | Migrate to Qdrant when scaling | N/A |

### Runtime Selection

```python
from abby_core.config.base import BotConfig

config = BotConfig.load()

if config.environment == "production":
    rag_client = QdrantClient(api_key=config.qdrant_api_key)
else:
    rag_client = ChromaClient(persist_dir="chroma_db/")
```python

---

## Ingestion Pipeline

### Step 1: Document Validation

```python
from abby_core.rag.handler import ingest_document

## Validation checks
document = {
    "guild_id": "123456",
    "document_type": "guidelines",  # Must be defined type
    "scope": "community",            # Must be defined scope
    "content": "Our community rules are...",
    "title": "Community Guidelines",
    "source_url": "https://example.com/rules",
    "created_by": "admin_user_123"
}

## Type validation
VALID_TYPES = [
    "guidelines", "policy", "faq", "documentation",
    "weekly_summary", "artist_bio", "submission_rules", "other"
]
assert document["document_type"] in VALID_TYPES

## Scope validation
VALID_SCOPES = [
    "community", "gameplay", "economy", "moderation",
    "announcements", "canon_reference", "other"
]
assert document["scope"] in VALID_SCOPES
```python

### Step 2: Chunking

Documents are split into semantic chunks:

```python
from abby_core.rag.handler import chunk_document

chunks = chunk_document(
    content=document["content"],
    chunk_size=500,      # Characters per chunk
    chunk_overlap=50,    # Overlap for context preservation
    separator="\n"       # Split on newlines first
)

## Output
## Chunk 0: "Our community rules are...[500 chars]"
## Chunk 1: "...rules are...[500 chars with 50 char overlap]"
## etc.
```python

### Step 3: Embedding Generation

```python
from sentence_transformers import SentenceTransformer

## Use all-MiniLM-L6-v2 for consistency across embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')

embeddings = model.encode(chunks)
## Returns: list[list[float]] with 384 dimensions each

## Each chunk now has dense vector representation for semantic search
```python

### Step 4: Storage

### ChromaDB (Development):
```python
from abby_core.rag.chroma_client import ChromaClient

chroma = ChromaClient(persist_dir="chroma_db/")

collection = chroma.get_or_create_collection(
    name=f"guild_{guild_id}",
    metadata={"hnsw:space": "cosine"}
)

collection.add(
    ids=[f"chunk_{i}" for i in range(len(chunks))],
    embeddings=embeddings,
    metadatas=[
        {
            "guild_id": guild_id,
            "document_type": document_type,
            "scope": scope,
            "chunk_index": i,
            "source_url": source_url
        }
        for i in range(len(chunks))
    ],
    documents=chunks
)
```python

### Qdrant (Production):
```python
from abby_core.rag.qdrant_client import QdrantWrapper
from qdrant_client.models import PointStruct

qdrant = QdrantWrapper(api_key=QDRANT_API_KEY)

points = [
    PointStruct(
        id=hash(f"{guild_id}_{i}"),  # Deterministic ID
        vector=embeddings[i],
        payload={
            "guild_id": guild_id,
            "document_type": document_type,
            "scope": scope,
            "chunk_index": i,
            "source_url": source_url,
            "content": chunks[i]
        }
    )
    for i in range(len(chunks))
]

qdrant.upsert(
    collection_name=f"guild_docs",
    points=points
)
```python

### Complete Ingestion Flow

```python
async def ingest_document(
    guild_id: str,
    document_type: str,
    content: str,
    source_url: str,
    created_by: str
):
    """Full ingestion pipeline."""
    
    # Step 1: Validate
    assert document_type in VALID_TYPES
    assert len(content) > 0
    
    # Step 2: Chunk
    chunks = chunk_document(content)
    
    # Step 3: Embed
    embeddings = model.encode(chunks)
    
    # Step 4: Store
    doc_id = await rag_client.upsert_document(
        guild_id=guild_id,
        document_type=document_type,
        chunks=chunks,
        embeddings=embeddings,
        source_url=source_url,
        created_by=created_by
    )
    
    # Step 5: Log
    logger.info("Document ingested", extra={
        "guild_id": guild_id,
        "document_id": doc_id,
        "chunks": len(chunks),
        "bytes": len(content)
    })
    
    return doc_id
```python

---

## Query Pipeline

### Step 1: User Question Embedding

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

## User question
query = "What are the submission rules?"

## Embed using same model as ingestion
query_embedding = model.encode(query)  # 384-dim vector
```python

### Step 2: Semantic Search

### ChromaDB:
```python
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5,  # Top 5 results
    where={"guild_id": guild_id}  # Guild isolation
)

## Results include: chunk text, metadata, distance
for distance, chunk, metadata in results:
    print(f"Distance: {distance}, Chunk: {chunk}")
```python

### Qdrant:
```python
results = qdrant.search(
    collection_name="guild_docs",
    query_vector=query_embedding,
    query_filter={"guild_id": guild_id},  # Guild isolation
    limit=5,
    score_threshold=0.6
)

## Results: points with payload (content + metadata)
for point in results:
    print(f"Score: {point.score}, Content: {point.payload['content']}")
```python

### Step 3: Reranking (Optional)

For higher accuracy, rerank results with cross-encoder:

```python
from sentence_transformers import CrossEncoder

## Cross-encoder specialized for semantic similarity
reranker = CrossEncoder('cross-encoder/qnli-distilroberta-base')

## Score all results
scores = reranker.predict([
    (query, chunk["content"])
    for chunk in rag_results
])

## Sort by score
ranked_results = sorted(
    zip(scores, rag_results),
    key=lambda x: x[0],
    reverse=True
)

## Return top 3 reranked results
top_results = [chunk for _, chunk in ranked_results[:3]]
```python

### Step 4: Format for LLM

```python
context = "\n\n".join([
    f"**{chunk['metadata']['document_type']}**\n{chunk['content']}"
    for chunk in top_results
])

## Inject into system prompt
system_prompt = f"""You are Abby, a helpful bot.

Use the following guild documents to answer questions:

{context}

Always cite the document type when using guild information."""
```python

### Complete Query Flow

```python
async def query_documents(
    guild_id: str,
    question: str,
    top_k: int = 5
) -> list[dict]:
    """Full query pipeline."""
    
    # Step 1: Embed question
    query_embedding = model.encode(question)
    
    # Step 2: Search
    raw_results = await rag_client.search(
        guild_id=guild_id,
        query_vector=query_embedding,
        limit=top_k * 2  # Over-fetch for reranking
    )
    
    # Step 3: Rerank
    reranked = rerank_results(question, raw_results)
    
    # Step 4: Format
    formatted = format_for_llm(reranked)
    
    # Step 5: Log
    logger.info("Query executed", extra={
        "guild_id": guild_id,
        "question": question,
        "results": len(formatted)
    })
    
    return formatted
```python

---

## Guild Isolation

Each guild's documents are completely isolated:

```python
## Guild A cannot see Guild B's documents
results_a = await rag_client.search(
    guild_id="guild_a",
    query_vector=embedding,
    # Metadata filter ensures only this guild's docs returned
)

results_b = await rag_client.search(
    guild_id="guild_b",
    query_vector=embedding,
    # Different filter, different results
)

## Verification: cross-guild query blocked
## If Guild B user tries to access Guild A docs, search returns []
```python

### Metadata Filters (Qdrant):
```json
{
    "must": [
        {"key": "guild_id", "match": {"value": "guild_123"}}
    ]
}
```python

---

## Document Lifecycle Management

### Version Tracking

```python
## Document version in metadata
{
    "guild_id": "123",
    "document_id": "guidelines_v2",
    "document_type": "guidelines",
    "version": 2,
    "created_at": "2026-01-31T00:00:00Z",
    "updated_at": "2026-01-31T12:00:00Z",
    "status": "ACTIVE",
    "superseded_by": None
}

## When updating document, old version marked as superseded
old_doc = {
    ...
    "version": 1,
    "status": "SUPERSEDED",
    "superseded_by": "guidelines_v2"
}
```python

### Cleanup & Retention

```python
async def cleanup_old_documents(guild_id: str, retention_days: int = 90):
    """Remove documents older than retention period."""
    
    cutoff = now() - timedelta(days=retention_days)
    
    old_docs = await db.rag_documents.find({
        "guild_id": guild_id,
        "status": "SUPERSEDED",
        "updated_at": {$lt: cutoff}
    }).to_list(None)
    
    for doc in old_docs:
        # Delete from vector DB
        await rag_client.delete_document(doc["document_id"])
        
        # Delete from MongoDB
        await db.rag_documents.delete_one({_id: doc._id})
    
    logger.info(f"Cleaned up {len(old_docs)} old documents")
```python

### Quota Enforcement

```python
STORAGE_QUOTA_PER_GUILD = 50 * 1024 * 1024  # 50 MB

async def check_quota(guild_id: str, new_content_bytes: int):
    """Prevent ingestion if quota exceeded."""
    
    # Calculate current usage
    docs = await db.rag_documents.find({
        "guild_id": guild_id,
        "status": "ACTIVE"
    }).to_list(None)
    
    current_usage = sum(len(doc["content"]) for doc in docs)
    
    if current_usage + new_content_bytes > STORAGE_QUOTA_PER_GUILD:
        raise PermissionError(
            f"Guild storage quota exceeded: "
            f"{current_usage}/{STORAGE_QUOTA_PER_GUILD}"
        )
```python

---

## ChromaDB → Qdrant Migration (Production)

### Migration Overview

Nine-step process ensuring zero data loss:

```python
Step 1: Dry-run (validate compatibility)
↓
Step 2: Backup (snapshot current Chroma data)
↓
Step 3: Create Qdrant collections
↓
Step 4: Batch migrate documents
↓
Step 5: Validate record counts
↓
Step 6: Performance test (ensure p50 < 100ms)
↓
Step 7: Switchover (DNS cutover)
↓
Step 8: Monitor (verify no errors)
↓
Step 9: Archive backup (retain for 30 days)
```python

### Migration Procedure

### Step 1: Dry-Run Validation
```python
from abby_core.rag.migration import validate_migration

## Check all collections can be read
errors = await validate_migration(
    source=chroma_client,
    target=qdrant_client,
    sample_size=100  # Test with 100 samples
)

if errors:
    print(f"Migration validation failed: {errors}")
    return False
```python

### Step 2: Backup
```bash
## Backup Chroma data
cp -r chroma_db/ chroma_db.backup.$(date +%s)
## Backup MongoDB RAG documents
mongodump --db abby_bot --collection rag_documents --out backup_$(date +%s)
```python

### Step 3: Create Collections
```python
## Create Qdrant collections with same settings as Chroma
await qdrant.create_collection(
    collection_name="guild_docs",
    vectors_config=VectorConfig(
        size=384,  # all-MiniLM-L6-v2 dimension
        distance=Distance.COSINE
    )
)
```python

### Step 4: Batch Migration
```python
async def migrate_chroma_to_qdrant(batch_size: int = 1000):
    """Migrate all documents from Chroma to Qdrant."""
    
    total_migrated = 0
    
    for guild_id in get_all_guild_ids():
        collection = chroma.get_collection(f"guild_{guild_id}")
        
        # Get all points from Chroma
        all_data = collection.get(
            include=["embeddings", "metadatas", "documents"]
        )
        
        # Convert to Qdrant format
        points = [
            PointStruct(
                id=hash(id),
                vector=embedding,
                payload={**metadata, "content": document}
            )
            for id, embedding, metadata, document
            in zip(
                all_data["ids"],
                all_data["embeddings"],
                all_data["metadatas"],
                all_data["documents"]
            )
        ]
        
        # Batch upsert
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            await qdrant.upsert("guild_docs", batch)
            total_migrated += len(batch)
    
    logger.info(f"Migration complete: {total_migrated} points")
```python

### Step 5-9: Validation, Testing, Switchover, Monitoring
```bash
## Query both databases and compare results
docker run -it qdrant/qdrant --api-key $QDRANT_KEY

## Verify record counts
chroma_count=$(python -c "...")  # Query Chroma
qdrant_count=$(curl -H "api-key: $QDRANT_KEY" $QDRANT_URL/collections/guild_docs)

## Performance test
ab -n 1000 -c 10 $QDRANT_ENDPOINT/search

## DNS switchover (point old endpoint to Qdrant)
## Gradual rollout (10% traffic) monitoring for 24h
## Then full switchover

## Archive backup
tar czf chroma_db.backup.tar.gz chroma_db.backup.* && rm -rf chroma_db.backup.*
```python

---

## Performance Optimization

### Baseline Metrics

| Operation | ChromaDB p50 | Qdrant p50 | Improvement |
| ----------- | ------------- | ----------- | ------------- |
| Query (5 results) | 300ms | 80ms | 73% faster |
| Batch upsert (100) | 2s | 250ms | 8x faster |
| Guild isolation filter | 50ms | 10ms | 5x faster |
| Rerank (3 results) | 150ms | 150ms | Same (CPU-bound) |

### Optimization Strategies

1. **Increase batch size for ingestion:**
   ```python
   # Process multiple documents in parallel
   tasks = [
       ingest_document(doc)
       for doc in guild_documents
   ]
   results = await asyncio.gather(*tasks)
   ```

1. **Cache query results for repeated questions:**
   ```python
   cache = {}
   
   async def cached_query(guild_id, question):
       key = f"{guild_id}:{question}"
       if key in cache:
           return cache[key]
       
       results = await rag_client.search(question)
       cache[key] = results
       return results
   ```

1. **Use reranking selectively (high-stakes queries only):**
   ```python
   if importance == "high":
       results = rerank_results(question, raw_results)
   else:
       results = raw_results  # Skip reranking
   ```

---

## 50-Year RAG Strategy

### Annual Audits

- [ ] Review chunk size/overlap settings (still optimal?)
- [ ] Audit document types/scopes (new categories needed?)
- [ ] Check storage quota allocation (scaling with guilds?)
- [ ] Verify guild isolation is enforced

### 5-Year Reviews

- [ ] Evaluate new embedding models (better accuracy?)
- [ ] Consider hybrid search (BM25 + semantic)
- [ ] Plan multi-region vector DB deployment
- [ ] Design document categorization schema evolution

### 10-Year Reviews

- [ ] Full RAG architecture redesign
- [ ] Evaluate graph-based retrieval (knowledge graphs)
- [ ] Plan quantum-resistant embeddings
- [ ] Multi-language support for embeddings

---

## Related Documents

- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — RAG environment variables
- [QDRANT_MIGRATION_GUIDE.md](QDRANT_MIGRATION_GUIDE.md) — Detailed migration steps
- [OBSERVABILITY_RUNBOOK.md](OBSERVABILITY_RUNBOOK.md) — Monitor RAG performance
