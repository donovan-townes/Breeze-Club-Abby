# API Reference

Complete API documentation for Abby's core modules and services.

## 📚 Contents

### Core Services

#### [Storage API](STORAGE_API_REFERENCE.md)

File management, quotas, and user storage operations.

**Classes:**

- `StorageManager` — Main storage orchestrator
- `QuotaManager` — Quota tracking and enforcement

**Methods:**

```python
save_generation(user_id, image_bytes, metadata) -> dict
get_quota_status(user_id, guild_id, user_roles, user_level) -> dict
list_user_files(user_id, guild_id) -> list
delete_file(file_path) -> bool
cleanup_old_files() -> dict
```

---

#### [LLM Client API](LLM_CONFIGURATION.md)

Language model abstraction and conversation management.

**Classes:**

- `LLMClient` — Provider-agnostic LLM client
- `ConversationManager` — Multi-user conversation tracking

**Methods:**

```python
generate(prompt, temperature, max_tokens, system_prompt) -> str
stream_generate(prompt, **kwargs) -> AsyncIterator[str]
get_conversation(user_id, max_history) -> list
append_message(user_id, role, content) -> None
```

---

#### [RAG API](rag-api.md)

Retrieval-Augmented Generation for document search.

**Functions:**

```python
ingest(source, title, text, user_id, guild_id, tags) -> dict
query(text, user_id, guild_id, top_k, min_score) -> list
delete_document(doc_id) -> bool
list_documents(user_id, guild_id) -> list
```

---

#### [Economy API](economy-api.md)

XP, leveling, and banking operations.

**XP System:**

```python
get_xp(user_id, guild_id) -> dict
add_xp(user_id, amount, guild_id, reason) -> dict
get_level(user_id, guild_id) -> int
get_leaderboard(guild_id, limit) -> list
```

**Banking:**

```python
get_balance(user_id, guild_id) -> int
transfer(from_user, to_user, amount, guild_id) -> bool
add_currency(user_id, amount, reason, guild_id) -> dict
```

---

#### [Database API](database-api.md)

MongoDB operations and schema utilities.

**Connection:**

```python
connect_to_mongodb() -> MongoClient
get_collection(collection_name) -> Collection
```

**User Operations:**

```python
upsert_user(user_id, username, discriminator, guild_id) -> None
get_user_profile(user_id, guild_id) -> dict
update_user_profile(user_id, updates, guild_id) -> bool
```

**Session Management:**

```python
create_session(user_id, channel_id, guild_id) -> str
append_session_message(session_id, role, content) -> None
close_session(session_id, summary) -> dict
```

---

#### [Image Generation API](image-generation-api.md)

Stability AI integration for image creation.

**Class:**

- `ImageGenerator` — Image generation client

**Methods:**

```python
text_to_image(prompt, style_preset, **kwargs) -> tuple[bool, bytes, str]
image_to_image(prompt, init_image, strength, **kwargs) -> tuple[bool, bytes, str]
upscale_image(image_bytes, scale) -> tuple[bool, bytes, str]
```

---

### Personality System

#### [Persona API](persona-api.md)

Bot personality configuration and response patterns.

**Functions:**

```python
get_personality_config(persona_name) -> PersonalityConfig
get_random_greeting(user_name, emoji, include_action) -> str
get_random_dismissal(emoji) -> str
get_emoji(emoji_key, default) -> str
```

---

### Security & Encryption

#### [Security API](security-api.md)

Encryption, decryption, and credential management.

**Functions:**

```python
encrypt_data(data, key) -> bytes
decrypt_data(encrypted_data, key) -> str
hash_password(password) -> str
verify_password(password, hashed) -> bool
```

---

### Observability

#### [Logging API](logging-api.md)

Structured logging and event tracking.

**Setup:**

```python
setup_logging(level, log_dir) -> None
logger = logging.getLogger(__name__)
```

**TDOS Telemetry:**

```python
emit_heartbeat(uptime_seconds, active_sessions, pending_submissions) -> None
emit_error(error_type, message, recovery_action) -> None
emit_governance_event(event_type, payload) -> None
```

---

## 🎯 Quick Reference by Use Case

### Adding a New Command

1. Import from `abby_adapters.discord.config`
2. Use Discord.py command decorators
3. Call core services (e.g., `StorageManager`, `LLMClient`)
4. Handle Discord interactions (embeds, buttons)

**Example:**

```python
from discord import app_commands
from abby_core.storage import StorageManager
from abby_core.generation import ImageGenerator

@app_commands.command(name="imagine")
async def imagine(interaction, prompt: str):
    await interaction.response.defer()

    # Use core services
    success, image_bytes, msg = await generator.text_to_image(prompt)

    if success:
        result = storage.save_generation(
            user_id=str(interaction.user.id),
            image_bytes=image_bytes,
            metadata={"prompt": prompt}
        )
        # Send Discord response
        await interaction.followup.send(file=discord.File(...))
```

---

### Querying the Database

```python
from abby_core.database.mongodb import get_collection

# Get user data
users = get_collection("discord_profiles")
profile = users.find_one({"user_id": "123456789"})

# Update XP
xp_collection = get_collection("user_xp")
xp_collection.update_one(
    {"user_id": "123456789"},
    {"$inc": {"points": 50}},
    upsert=True
)
```

---

### Using RAG for Context

```python
from abby_core.rag import query as rag_query

# Query knowledge base
results = rag_query(
    text="How do I mix vocals?",
    guild_id=str(interaction.guild_id),
    top_k=3,
    min_score=0.7
)

# Format context for LLM
context = "\n\n".join([r["text"] for r in results])
prompt = f"Context:\n{context}\n\nQuestion: {user_question}"
```

---

## 📖 Related Documentation

- **[Architecture](../architecture/)** — System design principles
- **[Features](../features/)** — Feature implementations
- **[Getting Started](../getting-started/)** — Setup guides
- **[Contributing](../contributing/)** — Development workflow

---

## 🔧 Code Examples

Full working examples available in:

- `abby_adapters/discord/cogs/` — Command implementations
- `tests/` — Unit and integration tests
- `docs/examples/` — Standalone examples

---

## 📝 Conventions

### Type Hints

All API functions use Python type hints:

```python
def add_xp(user_id: str, amount: int, guild_id: Optional[str] = None) -> dict:
    ...
```

### Return Values

- **Success/failure operations**: Return `tuple[bool, ...]` or `dict` with `"success"` key
- **Data retrieval**: Return data directly or `None` if not found
- **Async operations**: Use `async def` and `await` consistently

### Error Handling

- Raise exceptions for programmer errors (invalid types, missing deps)
- Return error indicators for expected failures (quota exceeded, not found)
- Log all errors using `logging.error()`

---

**Last Updated**: January 2026  
**API Version**: 2.0.0-beta
