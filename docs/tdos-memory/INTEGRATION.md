# TDOS Memory Integration Guide for Abby

This document explains how TDOS Memory integrates with Abby and how to use it in your code.

## Overview

**TDOS Memory** (Typed, Decaying, Observable Storage) is a sophisticated memory system for AI agents that provides:

- **Typed** memory envelopes with confidence scoring
- **Decaying** information (older facts matter less)
- **Observable** metrics and extraction insights
- **Guild-scoped** storage for Discord multi-tenant scenarios

It's now published to PyPI as [`tdos-memory`](https://pypi.org/project/tdos-memory/).

## Architecture

```
Abby Discord Bot
│
├─ abby_adapters/discord/cogs/creative/chatbot.py
│  └─ Uses MemoryService from TDOS Memory
│     ├─ Stores conversation context
│     ├─ Extracts facts from summaries
│     ├─ Manages shared narratives
│     └─ Applies decay to old memories
│
├─ abby_core/database/mongodb.py
│  └─ Manages MongoDB connections
│
└─ tdos_memory (PyPI package)
   ├─ MemoryService (high-level API)
   ├─ MemoryStore / MongoMemoryStore (low-level storage)
   ├─ MemoryEnvelope (typed memory object)
   └─ Decay / Extraction / Metrics (utilities)
```

## Installation

TDOS Memory is automatically installed when you run:

```bash
pip install -r requirements.txt
```

To verify installation:

```bash
python -c "from tdos_memory import get_memory_envelope; print('✓ TDOS Memory installed')"
```

## Using TDOS Memory in Code

### 1. Initialize Memory Service (in a Cog)

```python
from tdos_memory import create_memory_service
from tdos_memory.storage import MongoMemoryStore
from abby_core.database.mongodb import connect_to_mongodb
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Connect to MongoDB
        mongo_client = connect_to_mongodb()

        # Create MongoDB-backed memory store
        self.memory_store = MongoMemoryStore(
            storage_client=mongo_client,
            profile_collection="discord_profiles",
            session_collection="chat_sessions",
            narrative_collection="shared_narratives"
        )

        # Create high-level memory service
        self.memory_service = create_memory_service(
            store=self.memory_store,
            source_id="discord",  # Identify this adapter
            logger=logger
        )
```

### 2. Get Memory for a User

```python
from tdos_memory import get_memory_envelope

async def my_command(self, ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Get memory envelope for this user in this guild
    envelope = get_memory_envelope(
        user_id=user_id,
        guild_id=guild_id,
        source_id="discord"
    )

    print(f"User has {len(envelope.facts)} stored facts")
    print(f"Confidence score: {envelope.confidence}")
```

### 3. Add a Memorable Fact

```python
from tdos_memory import add_memorable_fact

async def my_command(self, ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Remember something about this user
    await add_memorable_fact(
        user_id=user_id,
        guild_id=guild_id,
        fact="User prefers short responses",
        confidence=0.9,
        source="user_preference"
    )
```

### 4. Format Memory for LLM Prompts

```python
from tdos_memory import format_envelope_for_llm, get_memory_envelope

async def generate_response(self, ctx, user_input):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Get memory
    envelope = get_memory_envelope(
        user_id=user_id,
        guild_id=guild_id,
        source_id="discord"
    )

    # Format for LLM - returns clean text injection
    memory_context = format_envelope_for_llm(envelope)

    # Use in your prompt
    llm_prompt = f"""
    Previous context about user:
    {memory_context}

    User's current message: {user_input}
    """
```

### 5. Extract Facts from Conversation

```python
from tdos_memory import extract_facts_from_summary

async def end_conversation(self, user_id, guild_id, conversation_summary):
    # Automatically extract structured facts from conversation
    facts = extract_facts_from_summary(
        summary=conversation_summary,
        user_id=user_id,
        guild_id=guild_id
    )

    # facts is a list of (fact_text, confidence) tuples
    for fact, confidence in facts:
        await add_memorable_fact(
            user_id=user_id,
            guild_id=guild_id,
            fact=fact,
            confidence=confidence,
            source="conversation_extraction"
        )
```

### 6. Apply Decay to Memories

```python
from tdos_memory import apply_decay

async def periodic_maintenance(self):
    """Run this periodically (e.g., hourly)"""

    # Apply decay to all memories
    # Older facts lose confidence gradually
    decayed_count = await apply_decay(
        days_old_threshold=30,
        decay_factor=0.95  # Each day: conf *= 0.95
    )

    print(f"Applied decay to {decayed_count} memory envelopes")
```

### 7. Analyze Conversation Patterns

```python
from tdos_memory import analyze_conversation_patterns

async def analyze_user(self, user_id, guild_id):
    patterns = analyze_conversation_patterns(
        user_id=user_id,
        guild_id=guild_id
    )

    print(f"Common topics: {patterns.get('topics', [])}")
    print(f"Conversation frequency: {patterns.get('frequency', {})}")
    print(f"Average response length: {patterns.get('avg_length', 0)}")
```

### 8. Manage Shared Narratives

```python
from tdos_memory import add_shared_narrative, get_shared_narratives

# Add a shared context (e.g., "User and bot have shared story")
await add_shared_narrative(
    user_id=user_id,
    guild_id=guild_id,
    narrative="We discussed their game development project",
    participants=[user_id]  # Other user IDs can be included
)

# Retrieve shared narratives
shared = get_shared_narratives(
    user_id=user_id,
    guild_id=guild_id
)
```

## Configuration

### Environment Variables

No special configuration needed! TDOS Memory uses:

- `MONGODB_URI` for database connection (shared with Abby)
- `LOG_LEVEL` for logging (shared with Abby)

### Memory Store Options

TDOS Memory supports multiple backends:

```python
# MongoDB (recommended for Discord)
from tdos_memory.storage import MongoMemoryStore
store = MongoMemoryStore(storage_client=mongo_client)

# PostgreSQL
from tdos_memory.backends.postgres import PostgresMemoryStore
store = PostgresMemoryStore(connection_string="...")

# SQLite (for testing)
from tdos_memory.backends.sqlite import SqliteMemoryStore
store = SqliteMemoryStore(db_path="memory.db")

# In-memory (for testing)
from tdos_memory.backends.inmemory import InMemoryStore
store = InMemoryStore()
```

## Common Patterns

### Pattern 1: Conversation Context Injection

```python
async def handle_conversation(self, ctx, user_input):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Get user's memory
    envelope = get_memory_envelope(user_id, guild_id, "discord")
    memory_context = format_envelope_for_llm(envelope)

    # Build LLM prompt with memory
    prompt = f"""
{memory_context}

Current user message: {user_input}
"""

    # Call LLM
    response = await self.llm_client.generate(prompt)

    # Store in session
    await append_session_message(user_id, guild_id, "user", user_input)
    await append_session_message(user_id, guild_id, "assistant", response)
```

### Pattern 2: End-of-Conversation Learning

```python
async def end_conversation(self, user_id, guild_id, chat_history):
    # Generate summary of conversation
    summary = await self.summarizer.summarize(chat_history)

    # Extract facts
    facts = extract_facts_from_summary(summary, user_id, guild_id)

    # Store facts
    for fact, confidence in facts:
        await add_memorable_fact(
            user_id, guild_id, fact, confidence, "conversation"
        )

    # Apply decay to old facts
    await apply_decay()
```

### Pattern 3: Guild-Scoped Memory

```python
async def per_guild_response(self, ctx):
    # Memory is automatically guild-scoped
    envelope = get_memory_envelope(
        user_id=str(ctx.author.id),
        guild_id=str(ctx.guild.id),  # Different per guild
        source_id="discord"
    )

    # User has separate memory in each guild
    # This prevents information leakage between communities
```

## Troubleshooting

### Memory Envelope Empty

**Problem:** `envelope.facts` is always empty after initialization

**Solution:**

```python
# Facts are loaded from MongoDB on demand
envelope = get_memory_envelope(user_id, guild_id, "discord")

# Wait for facts to load (they're fetched asynchronously)
await envelope.load_facts()  # May need this

# Or use with memory service
facts = await self.memory_service.get_user_facts(user_id, guild_id)
```

### Cache Not Invalidating

**Problem:** Memory changes aren't reflected in subsequent calls

**Solution:**

```python
from tdos_memory import invalidate_cache

# After updating memory
await add_memorable_fact(...)

# Invalidate cache for user
await invalidate_cache(user_id=user_id, guild_id=guild_id)

# Next call will fetch fresh data
envelope = get_memory_envelope(...)  # Fresh data
```

### MongoDB Connection Issues

**Problem:** Memory store can't connect to MongoDB

**Solution:**

```python
# Ensure MongoDB is running and accessible
from abby_core.database.mongodb import connect_to_mongodb

mongo_client = connect_to_mongodb()

# Try to access a collection
try:
    mongo_client.admin.command('ping')
    print("MongoDB is connected")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
```

### Performance Issues with Large Memories

**Problem:** Memory retrieval is slow with thousands of facts

**Solution:**

```python
# Use memory service's indexing
self.memory_service.create_indexes()

# Use pagination
facts = self.memory_service.get_user_facts(
    user_id, guild_id,
    skip=0,
    limit=100  # Only load 100 at a time
)

# Or use sampling
recent_facts = self.memory_service.get_recent_facts(
    user_id, guild_id,
    days=30  # Only facts from last 30 days
)
```

## Updating TDOS Memory

When you need to update TDOS Memory:

1. **Modify** the library code
2. **Update version** in `setup.py` and `pyproject.toml`
3. **Commit and tag:**
   ```bash
   git tag tdos-memory-v1.0.1
   git push origin tdos-memory-v1.0.1
   ```
4. **GitHub Actions** automatically publishes to PyPI
5. **Update Abby's** `requirements.txt`:
   ```diff
   - tdos-memory>=1.0.0,<2.0.0
   + tdos-memory>=1.0.1,<2.0.0
   ```
6. **Test** locally:
   ```bash
   pip install --upgrade tdos-memory
   python launch.py
   ```

## API Reference

See [TDOS Memory API Reference](../../tdos_memory/docs/API_REFERENCE.md) for complete function documentation.

## Resources

- [TDOS Memory on PyPI](https://pypi.org/project/tdos-memory/)
- [TDOS Memory GitHub](https://github.com/townesdev/tdos-memory)
- [TDOS Memory Docs](../../tdos_memory/docs/README.md)

---

**Questions?** Check [Troubleshooting Guide](../../tdos_memory/docs/TROUBLESHOOTING.md) or open an issue on GitHub.
