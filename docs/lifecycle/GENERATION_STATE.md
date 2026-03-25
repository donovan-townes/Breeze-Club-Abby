# Generation State

Ephemeral, per-request context used to call the LLM. Never persisted unless tied to a lifecycle artifact (e.g., announcements).

## Components

- Persona base (from JSON) + in-memory cache
- Dynamic overlays (season/event/mode effects)
- Guild/user context (memory snippets, channel metadata, recent messages)
- Optional RAG/devlog injections
- System scaffolding (safety rails, formatting constraints)
- **System prompt assembly** (WHO vs HOW separation)
- **Cost tracking** (via GenerationAuditService)

## System Prompt Assembly (Phase 2: Architectural Separation)

### Prompt building is now separated from persona definition for better modularity:

- **WHO (Persona Definition):** `abby_core/personality/` defines Abby's character, voice, and identity
- **HOW (Prompt Assembly):** `abby_core/llm/prompt_builder.py` composes the system prompt from persona + overlays + context

### PromptBuilder responsibilities:

- Load persona base from JSON
- Apply dynamic overlays from platform state (season/event effects)
- Inject guild context (guild name, channel purpose, member count)
- Build system scaffolding (safety rails, formatting constraints)
- Manage token budget for memory injection

**Owner:** [abby_core/llm/prompt_builder.py](../../abby_core/llm/prompt_builder.py)  
**Invoked From:** Context factory during request processing  
**Impact:** Decouples persona from prompt strategy; enables independent evolution without persona drift

## Cost Tracking & Observability (Phase 2: Audit Trail)

### All LLM generations are logged with complete metadata for cost analysis and capacity planning:

- **Captured Metadata:** input_tokens, output_tokens, total_cost_usd, latency_ms, provider, model, session_id, user_id, guild_id, intent, turn_number
- **Persistence:** Mongo `generation_audit` collection (permanent audit trail)
- **Cost Calculation:** Built-in rates for OpenAI ($0.03/$0.06 GPT-4), Anthropic ($0.008/$0.024 Claude), Ollama ($0 local)
- **Query Support:** Time-windowed cost summaries per provider, user, or guild
- **Use Cases:**
  - Monthly cost reporting per provider/model
  - Per-user generation quotas and usage tracking
  - 50-year cost projections for capacity planning
  - Multi-tenant billing for future hosted deployments

**Owner:** [abby_core/services/generation_audit_service.py](../../abby_core/services/generation_audit_service.py)  
**Key Functions:** `log_generation()` (record call with costs), `get_cost_summary()` (per-date-range), `get_provider_breakdown()` (per-provider)  
**Invoked From:** [abby_core/llm/conversation.py](../../abby_core/llm/conversation.py) respond() and summarize() functions  
### MongoDB Queries:

```js
// Cost summary by provider
db.generation_audit.aggregate([
  { $group: { _id: "$provider", cost: { $sum: "$total_cost_usd" } } },
]);

// Per-user cost (date range)
db.generation_audit.aggregate([
  { $match: { timestamp: { $gte: ISODate("2026-01-01") } } },
  { $group: { _id: "$user_id", cost: { $sum: "$total_cost_usd" } } },
]);
```python

## Source of truth

- Persona files under `abby_core/personality/data`
- Platform state overlays via `system_state`
- Context assembly in `abby_core/llm/context_factory.py` and consumers

## Ownership and mutation

- Built per request by the context factory and calling handler.
- Mutated only in-memory during a turn; not stored.

## Invariants

- Do not persist prompts or outputs outside lifecycle flows.
- Apply overlays through platform state, not ad-hoc flags.
- Enforce safety/policy before invocation.

## Key functions

- Persona load/overlay: `abby_core/personality/manager.py`
- Context build: `abby_core/llm/context_factory.py`, `build_conversation_context`
- LLM call: `respond`

## Observability

- Log assembly steps and retry metadata; consider structured traces for adapters.

See also: [STATE_MAP.md](STATE_MAP.md) and [../runtime/GENERATION_PIPELINE.md](../runtime/GENERATION_PIPELINE.md).
