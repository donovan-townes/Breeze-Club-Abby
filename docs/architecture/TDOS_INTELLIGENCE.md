# TDOS Intelligence Layer - Standalone Reference

**Purpose:** Production-ready, reusable AI/intent infrastructure for multi-domain applications.

**Last Updated:** January 31, 2026  
**Status:** Core functionality stable; packaging for external use in progress  
**Scope:** Platform-agnostic intent classification, orchestration, RAG, and memory  
**Users:** Abby (reference implementation), future projects (small business tools, content management, etc.)

---

## Philosophy

TDOS Intelligence is **intentionally domain-agnostic**. It provides:

1. **Intent Classification** — Determine what a user actually wants (chat, knowledge query, memory recall, action)
2. **Orchestration** — Route requests to appropriate processors (LLM, RAG, memory, tools)
3. **RAG Pipeline** — Retrieve relevant documents for knowledge queries
4. **LLM Abstraction** — Multi-provider support (OpenAI, Ollama, future providers)
5. **Memory System** — Extract and store facts, patterns, user profiles (via tdos_memory_package)
6. **Observability** — Unified telemetry across all processing

**Core Design Decision:** TDOS has NO knowledge of:

- Discord guilds or channels
- Abby personas or responses
- Application-specific workflows
- UI/platform details

These belong in adapters, not TDOS.

---

## Architecture

````python
tdos_intelligence/
├── intent/
│   ├── classifier.py       # Intent classification (LLM-based + heuristics)
│   └── __init__.py
├── orchestrator.py         # Main routing engine
├── llm/
│   ├── client.py          # Provider-agnostic LLM client
│   ├── providers/         # Provider implementations (OpenAI, Ollama, etc.)
│   └── __init__.py
├── rag/
│   ├── handler.py         # RAG query processor
│   └── __init__.py
├── memory/
│   ├── extractor.py       # Extract facts from conversations
│   └── __init__.py
├── observability/
│   ├── telemetry.py       # Unified event emission
│   └── __init__.py
├── tdos_memory_package/   # External memory package (PyPI)
└── __init__.py
```python

---

## Core Components

### 1. Intent Classification

**Entry Point:** `from tdos_intelligence import classify_intent`

**Responsibility:** Determine what type of processing a message needs.

### Intent Types:

- `GENERAL_CHAT` — Casual conversation (no special processing)
- `KNOWLEDGE_QUERY` — Question about rules/docs (trigger RAG)
- `MEMORY_RECALL` — Reference to past events (trigger memory system)
- `PERSONA_ACTION` — Direct command (play sound, toggle feature, etc.)
- `META_CONTROL` — System command (admin, config, etc.)

### Interface:

```python
async def classify_intent(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> IntentResult:
    """
    Classify user intent.

    Args:
        message: User message text
        context: Optional context dict (domain-agnostic)
        user_id: Optional user identifier

    Returns:
        IntentResult with intent, confidence, tokens_used, reasoning

    Example:
        result = await classify_intent("What are the rules?")
        if result.intent == "KNOWLEDGE_QUERY":
            docs = await rag_handler.query(message)
    """
    pass
```python

### Capabilities Map:
Each intent comes with a `capabilities` dict indicating what processing is needed:

```python
{
    "intent": "KNOWLEDGE_QUERY",
    "confidence": "high",
    "capabilities": {
        "needs_rag": True,
        "needs_memory_read": False,
        "needs_memory_write": False,
        "needs_tools": False,
        "priority": "interactive"
    }
}
```python

**Implementation:** Rule-based heuristics + optional LLM fallback. Uses lightweight local model to stay under 100ms budget.

---

### 2. Orchestrator

**Entry Point:** `from tdos_intelligence import Orchestrator`

**Responsibility:** Route messages through the full intelligence pipeline.

### Workflow:

```python
Message → Intent Classification → (
    if KNOWLEDGE_QUERY → RAG retrieval
    if MEMORY_RECALL → Memory system lookup
    if GENERAL_CHAT → LLM conversation
) → Response
```python

### Interface:

```python
class Orchestrator:
    async def process_message(
        self,
        message: str,
        user_id: str,
        guild_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorResponse:
        """
        Process a user message end-to-end.

        Args:
            message: User message text
            user_id: User identifier (domain-agnostic)
            guild_id: Optional workspace/group identifier
            context: Optional processing context

        Returns:
            OrchestratorResponse with intent, response, processing details
        """
        pass
```python

### Processing Budgets:

- Intent classification: 100ms max, 100 tokens
- RAG retrieval: 500ms max, 500 tokens
- LLM response: 5000ms max, 1500 tokens
- Memory extraction: async, 1000 tokens

### FSM Tracking (Optional):
The orchestrator can optionally integrate with Abby's conversation FSM if available:

```python
## If abby_core is installed, FSM tracking is enabled
_fsm_available = True
try:
    from abby_core.llm.conversation_turn import ConversationTurn
except ImportError:
    _fsm_available = False

## Adapters can check: if orchestrator.turn is not None: track FSM
```python

---

### 3. RAG Handler

**Entry Point:** `from tdos_intelligence import get_rag_handler`

**Responsibility:** Retrieve relevant documents for knowledge queries.

### Interface:

```python
class RAGHandler:
    async def query(
        self,
        text: str,
        tenant_id: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Document]:
        """
        Query RAG corpus.

        Args:
            text: Query text
            tenant_id: Tenant/domain scope (e.g., guild_id)
            top_k: Number of results

        Returns:
            List of relevant documents
        """
        pass
```python

### Adapters Can Extend:

- Document ingestion (adapters choose what to index)
- Chunking strategy
- Embedding model
- Vector store backend (Chroma, Qdrant, etc.)

---

### 4. LLM Client

**Entry Point:** `from tdos_intelligence import LLMClient`

**Responsibility:** Provider-agnostic LLM inference.

### Supported Providers:

- OpenAI (GPT-3.5, GPT-4)
- Ollama (local models: Llama, Mistral, etc.)
- Future: Claude, Gemini, etc.

### Interface:

```python
class LLMClient:
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: Message history
            model: Model override (uses default if None)
            temperature: Creativity level
            max_tokens: Response length limit

        Returns:
            Response text
        """
        pass
```python

### Multi-Provider Design:
Provider selection happens at runtime based on environment:

```python
## If OPENAI_API_KEY is set: use OpenAI
## Else if OLLAMA_HOST is reachable: use Ollama
## Else fallback to degraded mode
```python

---

### 5. Memory System

**Entry Point:** `from tdos_intelligence import extract_memory`

**Responsibility:** Extract facts and patterns from conversations for persistent storage.

### Interface:

```python
async def extract_memory(
    conversation: List[Dict[str, str]],
    user_id: str,
    tenant_id: Optional[str] = None,
) -> MemoryExtraction:
    """
    Extract facts and patterns from conversation.

    Returns:

        - facts: Explicit information ("user likes coffee")
        - patterns: Inferred patterns ("user is anxious about deadlines")
        - profiles: User profile updates
    """
    pass
```python

**Persistence:** Via external tdos_memory_package (PyPI). TDOS provides extraction; adapters provide storage.

---

### 6. Observability

**Entry Point:** `from tdos_intelligence import emit_event`

**Responsibility:** Unified telemetry across all processing.

### Event Types:

- `intent_classified` — Intent classification completed
- `rag_queried` — RAG retrieval performed
- `llm_invoked` — LLM call made
- `memory_extracted` — Facts extracted from conversation
- `error` — Processing error occurred

### Interface:

```python
def emit_event(
    event_type: str,
    data: Dict[str, Any],
    severity: str = "info",
) -> None:
    """Emit structured telemetry event."""
    pass
```python

---

## Adapter Extension Points

Adapters (Abby, Web, CLI, etc.) extend TDOS at these points:

### 1. Context Enrichment

Add domain-specific context to processing:

```python
context = {
    "user_id": "discord:123456",
    "tenant_id": "guild:789",
    "timezone": "America/New_York",
    "user_profile": {...},  # Optional profile data
    "system_rules": {...},   # Domain-specific rules
}

result = await orchestrator.process_message(message, context=context)
```python

### 2. RAG Corpus

Choose what documents to index:

- Abby: Server rules, canon documents, FAQs
- Web App: Product docs, knowledge base
- Business Tool: Internal policies, procedures

### 3. Post-Processing

Apply domain-specific logic after TDOS processing:

```python
## TDOS returns: message, intent, rag_docs, memory_extracted

## Abby adapter:

- Apply persona overlay
- Format for Discord
- Emit to channels

## Web adapter:

- Format for web UI
- Apply styling
- Store in session
```python

### 4. Tool Execution

If intent is `PERSONA_ACTION`, adapters provide tool implementations:

```python
## TDOS: "Intent is PERSONA_ACTION with tool=play_sound"
## Adapter: Execute play_sound(sound_id, channel_id)
```python

---

## External Dependencies

TDOS core has **minimal external dependencies**:

- `aiohttp` — HTTP client for LLM APIs
- `pydantic` — Schema validation
- `python-dotenv` — Configuration loading

### Optional dependencies:

- `ollama-python` — For local LLM inference
- `openai` — For OpenAI provider
- `chromadb` or `qdrant-client` — For RAG (adapters choose)

### Zero dependencies on:

- Discord.py
- Abby core
- Application frameworks
- Async job queues

---

## Deployment & Packaging

### Development

TDOS is developed as part of Abby but is **packaging-ready**:

```bash
## TDOS can be used standalone:
from tdos_intelligence import Orchestrator, classify_intent

## Or vendored in another project:
cp -r tdos_intelligence/ my_project/
```python

### Production

TDOS is packaged as a PyPI module (future):

```bash
pip install tdos-intelligence

from tdos_intelligence import Orchestrator
```python

### Versioning

- Semantic versioning (MAJOR.MINOR.PATCH)
- TDOS and Abby have independent version numbers
- Compatibility matrix documented

---

## Testing & Quality

**Coverage:** 85%+ (critical paths 95%+)
### Test Markers:

- `@pytest.mark.tdos_unit` — TDOS unit tests (run fast)
- `@pytest.mark.tdos_integration` — TDOS + adapter integration (slower)

### Backward Compatibility:

- TDOS API is stable; breaking changes trigger MAJOR version bump
- Adapters pin to TDOS version in requirements

---

## What TDOS Is NOT

### TDOS does not:

- Implement Discord-specific logic (voice, reactions, etc.)
- Define persona/tone (adapters do this)
- Manage guild configuration (adapters do this)
- Store conversation history (adapters do this)
- Implement game logic (adapters do this)
- Define safety rails (adapters extend TDOS safety with domain logic)

### These belong in adapters, not TDOS core.

---

## Migration Path to External Package

**Phase 1 (Now):** Formalize TDOS as standalone component

- Document public API
- Remove any implicit Abby dependencies ✅
- Add deprecation warnings to shared code

**Phase 2 (Q2 2026):** Extract to separate repository

- `tdos-intelligence` repo on GitHub
- CI/CD for independent testing
- PyPI publishing

**Phase 3 (Q3 2026):** Use external package in Abby

- `pip install tdos-intelligence`
- Abby depends on external TDOS

---

## Further Reading

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Abby integration
- [../runtime/GENERATION_PIPELINE.md](../runtime/GENERATION_PIPELINE.md) — How Abby uses TDOS
- [ADAPTER_CONTRACTS.md](ADAPTER_CONTRACTS.md) — Building adapters
````
