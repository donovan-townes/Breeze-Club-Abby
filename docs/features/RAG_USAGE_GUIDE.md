# Using RAG with Abby in Discord

This guide explains how to use Abby's RAG (Retrieval-Augmented Generation) system for Discord, including document ingestion, querying, and migrating from Chroma to Qdrant.

---

## Overview

Abby's RAG system allows you to:

- **Ingest reference documents** (label guidelines, artist profiles, submission rules, curated threads)
- **Query the knowledge base** semantically to retrieve relevant context
- **Enhance chatbot responses** with contextual knowledge
- **Migrate from Chroma to Qdrant** for production scale

**Important:** RAG is for _reference-grade knowledge only_. It does not store raw Discord chat logs, inferred user traits, or XP/economy history.

---

## Understanding RAG, Chroma, and Qdrant

### What is RAG?

**RAG (Retrieval-Augmented Generation)** is a technique, not a specific tool. It works in 4 steps:

1. **Store** knowledge as embeddings (vectorized text chunks)
2. **Retrieve** relevant chunks when a user asks a question
3. **Augment** the LLM prompt with retrieved context
4. **Generate** a response using both the question + context

**In Discord context**: When someone asks Abby "What are the submission guidelines?", RAG lets her search her knowledge base, find the 3 most relevant chunks, inject them into the LLM prompt, and answer accurately without hallucinating.

### Chroma vs. Qdrant

Both are **vector databases** that enable RAG. They store embeddings and perform similarity search.

| Feature         | Chroma                  | Qdrant                            |
| --------------- | ----------------------- | --------------------------------- |
| **Type**        | Embedded Python library | Standalone server (Docker/Cloud)  |
| **Setup**       | `pip install chromadb`  | Requires Docker or cloud hosting  |
| **Storage**     | Local SQLite + files    | Disk-based + in-memory indexes    |
| **Performance** | Good for <100k vectors  | Optimized for millions of vectors |
| **Scalability** | Single-machine          | Distributed clusters              |
| **Use case**    | Prototyping, small bots | Production, multiple services     |

### Why Your Setup Has Both

Your implementation uses a **phased approach**:

1. **Phase 1 (now)**: Start with **Chroma**

   - Windows-friendly, zero infrastructure, easy to test
   - Run `/rag ingest` → embeddings stored locally in `chroma_db/` folder
   - Perfect for building and testing RAG workflows

2. **Phase 2 (later)**: Migrate to **Qdrant**
   - When corpus grows (>10k documents) or multiple services need shared knowledge
   - Run migration script → copies all vectors from Chroma → Qdrant
   - Abby queries Qdrant; knowledge base becomes shared/scalable

### When to Migrate

**Stay on Chroma if:**

- Corpus < 5,000 documents
- Only Abby uses the knowledge base
- TServer doesn't run Docker yet
- You're still testing/iterating on RAG workflows

**Migrate to Qdrant if:**

- Corpus > 10,000 documents (performance matters)
- Multiple services need shared knowledge (web app, TDOS jobs)
- You want centralized management (delete/update docs without restarting Abby)
- You're running other Docker services on TServer

**Bottom line**: Start with Chroma for local tests, migrate to Qdrant when you need scale or service sharing.

---

## 1. Installation & Setup

### 1.1 Install Dependencies

```bash
# Activate your virtual environment
.venv\Scripts\activate

# Install RAG dependencies
pip install sentence-transformers chromadb qdrant-client
```

### 1.2 Configure Environment

Add to your `.env`:

```dotenv
# Chroma (initial local RAG)
CHROMA_PERSIST_DIR=chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

# Optional: Enable RAG in chatbot
RAG_CONTEXT_ENABLED=true

# Qdrant (for production migration)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=  # Optional for cloud
```

### 1.3 Create Storage Directory

```bash
mkdir chroma_db
```

---

## 2. Using RAG in Discord

### 2.1 Admin Commands

Abby provides three admin-only slash commands for RAG management:

#### `/rag ingest`

Ingests text into the RAG knowledge base.

**Parameters:**

- `title`: Document title (e.g., "Label Submission Guidelines")
- `text`: Full text content (up to Discord's limit; use attachments for longer docs)
- `source`: Category (label_docs, guidelines, artist_profiles, discord_threads, other)
- `tags`: Optional comma-separated tags (e.g., "submission,demo,quality")

**Example:**

```
/rag ingest
  title: Breeze Club Submission Guidelines
  text: All demos must be properly mixed and mastered...
  source: guidelines
  tags: submission,demo,quality
```

**What happens:**

1. Text is chunked into smaller segments (500 chars with 50 char overlap)
2. Each chunk is embedded using sentence-transformers
3. Embeddings are stored in Chroma vector DB
4. Metadata (title, source, tags, tenant_id) is stored in MongoDB `rag_documents` collection
5. A TDOS event `RAG.QUERY` (tagged "ingest") is emitted

#### `/rag query`

Tests retrieval without invoking the chatbot.

**Parameters:**

- `query`: Question or search phrase
- `top_k`: Number of results (default: 3)

**Example:**

```
/rag query
  query: What are the audio quality requirements for demos?
  top_k: 3
```

**Response:**
Returns top matching chunks with their metadata (source, title, score).

#### `/rag stats`

Shows RAG corpus statistics.

**Example:**

```
/rag stats
```

**Response:**

- Total documents
- Total chunks
- Breakdown by source (label_docs: 5, guidelines: 12, etc.)
- Storage size

---

## 3. RAG-Enhanced Chatbot

When `RAG_CONTEXT_ENABLED=true`, Abby's chatbot can optionally pull relevant context from the knowledge base.

### 3.1 Toggle RAG Context (In-Channel)

Users can enable/disable RAG context per session:

```
rag on
```

Abby responds: "RAG context enabled for chatbot."

```
rag off
```

Abby responds: "RAG context disabled for chatbot."

### 3.2 How It Works

1. User sends a message to Abby (in a channel where chatbot is active)
2. If RAG is enabled, Abby queries the vector store for relevant chunks
3. Top 3 contexts are injected into the LLM prompt:

   ```
   Context from knowledge base:
   - [source: guidelines] "All demos must be properly mixed..."
   - [source: artist_profiles] "Artist X specializes in..."

   User: {user message}
   ```

4. LLM generates response with enhanced context

**When to use RAG context:**

- Questions about label policies, submission requirements, artist bios
- Creative brainstorming informed by past guidelines
- Fact-checking against curated knowledge

**When NOT to use RAG context:**

- Casual conversation (introduces latency)
- Real-time events or user-specific queries (not in corpus)
- Code generation or technical tasks (unless docs ingested)

---

## 4. Migrating from Chroma to Qdrant

As your RAG corpus grows, you may want to migrate to Qdrant for better performance, filtering, and scalability.

### 4.1 Why Qdrant?

- **Performance:** Faster vector search at scale
- **Filtering:** Rich payload filtering (source, tags, tenant_id)
- **Production-ready:** Docker-based, persistent, API-driven
- **Multi-tenancy:** Better tenant isolation for multi-server Abby

### 4.2 Setup Qdrant (Docker)

```bash
# Pull and run Qdrant
docker run -p 6333:6333 -v C:\Abby_Discord_Latest\qdrant_storage:/qdrant/storage qdrant/qdrant

# Verify Qdrant is running
curl http://localhost:6333
```

### 4.3 Run Migration Script

**Dry Run (Preview Only):**

```bash
set MIGRATE_DRY_RUN=true
python scripts/migrate_chroma_to_qdrant.py abby_rag_collection 384
```

- `abby_rag_collection`: Chroma collection name
- `384`: Vector dimension (all-MiniLM-L6-v2 uses 384 dimensions)

**Actual Migration:**

```bash
set MIGRATE_DRY_RUN=false
python scripts/migrate_chroma_to_qdrant.py abby_rag_collection 384
```

**What happens:**

1. Script reads all embeddings from Chroma (`CHROMA_PERSIST_DIR`)
2. Creates/ensures Qdrant collection with same vector size
3. Batches points (128 at a time) and upserts to Qdrant
4. Logs progress and completion

### 4.4 Switch RAG Backend

After migration, update `abby-core/rag/rag_handler.py` to use Qdrant instead of Chroma:

```python
# Replace ChromaClient with QdrantWrapper
from utils.rag_qdrant import QdrantWrapper

# In RagHandler.__init__:
self.vector_store = QdrantWrapper()
```

### 4.5 Verify Migration

```discord
/rag stats
```

Should show same document counts and sources.

```discord
/rag query query: test query top_k: 3
```

Compare results with pre-migration queries to ensure consistency.

---

## 5. Best Practices

### 5.1 Ingestion

- **Chunk size:** Keep documents under 2000 chars per ingest (Discord limit); split longer docs into multiple ingestions
- **Tag consistently:** Use lowercase, no spaces (e.g., `submission,demo,quality`)
- **Source categories:** Stick to predefined sources for filtering:
  - `label_docs`: Official label documentation
  - `guidelines`: Submission/creative guidelines
  - `artist_profiles`: Bios, discographies, styles
  - `discord_threads`: Curated high-value discussions
  - `other`: Miscellaneous reference material

### 5.2 Querying

- **Natural language:** Use full questions, not keywords (e.g., "What are the mastering requirements?" not "mastering requirements")
- **Top-k tuning:** Start with 3; increase to 5 if more context needed
- **Scope filtering:** Future: filter by source/tags for focused retrieval

### 5.3 Maintenance

- **Review corpus:** Periodically audit ingested docs for accuracy and relevance
- **Update docs:** Re-ingest updated versions with same title (creates new chunks; old ones remain)
- **Clean stale data:** Future: add admin command to delete docs by title or source

---

## 6. Troubleshooting

### Chroma not found

```
RuntimeError: chromadb not installed
```

**Fix:** `pip install chromadb sentence-transformers`

### Qdrant connection failed

```
ConnectionRefusedError: [Errno 61] Connection refused
```

**Fix:** Ensure Qdrant is running (`docker ps` should show qdrant container)

### Embeddings dimension mismatch

```
ValueError: dimension mismatch: expected 384, got 768
```

**Fix:** Check `EMBEDDING_MODEL` in `.env`. Different models have different dimensions:

- `all-MiniLM-L6-v2`: 384 dims
- `all-mpnet-base-v2`: 768 dims

### RAG not injecting context in chatbot

**Check:**

1. `RAG_CONTEXT_ENABLED=true` in `.env`
2. User sent `rag on` in channel
3. Query returned results (`/rag query` test)
4. Check logs for RAG handler exceptions

### Migration script fails

```
ImportError: No module named 'chromadb'
```

**Fix:** Ensure both chromadb and qdrant-client installed in same environment

---

## 7. Example Workflow

### Scenario: Ingesting Label Guidelines

1. **Prepare document** (e.g., in a text file `guidelines.txt`):

   ```
   Breeze Club Submission Guidelines

   Audio Quality:
   - All demos must be 320kbps MP3 or 16-bit/44.1kHz WAV
   - Proper gain staging (-6dB headroom minimum)
   - No clipping or distortion

   Metadata:
   - Include artist name, track title, genre
   - Provide BPM and key if applicable
   ```

2. **Ingest via Discord:**

   ```discord
   /rag ingest
     title: Breeze Club Submission Guidelines
     text: [paste content from guidelines.txt]
     source: guidelines
     tags: submission,audio,quality
   ```

3. **Verify ingestion:**

   ```discord
   /rag stats
   ```

   Should show +1 document in "guidelines" source.

4. **Test retrieval:**

   ```discord
   /rag query query: What audio format is required for demos? top_k: 3
   ```

   Should return chunks mentioning "320kbps MP3" and "16-bit/44.1kHz WAV".

5. **Use in chatbot:**
   ```discord
   rag on
   @Abby What are the submission requirements for audio quality?
   ```
   Abby's response will include context from ingested guidelines.

---

## 8. Future Enhancements

- **Bulk ingestion:** Upload `.txt` or `.md` files directly
- **Scoped retrieval:** Filter by source/tags in chatbot queries
- **Delete/update docs:** Admin commands to modify corpus
- **User-level RAG:** Allow non-admins to ingest personal notes (tenant-scoped)
- **Hybrid search:** Combine vector similarity with keyword matching
- **RAG analytics:** Track most-queried topics, coverage gaps

---

## 9. TDOS Integration

RAG emits TDOS events for observability:

**RAG.QUERY (ingestion):**

```json
{
  "event_type": "RAG.QUERY",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "payload": {
    "operation": "ingest",
    "title": "Breeze Club Submission Guidelines",
    "source": "guidelines",
    "chunks": 5,
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

**RAG.QUERY (retrieval):**

```json
{
  "event_type": "RAG.QUERY",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "payload": {
    "operation": "query",
    "query": "What are the audio quality requirements?",
    "top_k": 3,
    "results_count": 3,
    "latency_ms": 45
  }
}
```

These events are logged to `shared/logs/events.jsonl` for TDOS CLERK:ACTIVITY analysis.

---

## 10. Summary

- **Install:** `pip install sentence-transformers chromadb qdrant-client`
- **Configure:** Set `CHROMA_PERSIST_DIR`, `RAG_CONTEXT_ENABLED`, and optional Qdrant settings in `.env`
- **Ingest:** Use `/rag ingest` to add reference documents
- **Query:** Use `/rag query` to test retrieval
- **Chatbot:** Enable with `rag on` in Discord channel
- **Migrate:** Use `scripts/migrate_chroma_to_qdrant.py` when ready for production scale
- **Monitor:** Check `/rag stats` and review TDOS events for corpus health

For questions or issues, refer to [MODERATION_AND_QDRANT.md](./MODERATION_AND_QDRANT.md) or ping the owner in Discord.
