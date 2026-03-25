# Conversation FSM

Purpose: describe the state machine that governs a single conversational turn/request. Applies to all adapters (Discord today, web/CLI later).

## States (conceptual)

- **Idle**: No active turn; waiting for trigger.
- **Ingress**: Message/command received. Capture trigger metadata (channel, guild, user, mode, platform state snapshot).
- **Gate**: Summon/dismiss and routing checks; may short-circuit to `Ignore` or `Refuse`.
- **Intent Classified**: Intent layer selects handler (chat, command, operator, system event, safety).
- **Policy Check**: Safety and mode constraints evaluated (NSFW/safety rails, operator lockdown, maintenance).
- **Context Assembled**: Persona + overlays + guild/user context + memory + optional RAG/devlog injected; prompt built.
- **LLM Call**: `respond` invoked with assembled context; retries and timeouts enforced.
- **Post-Process**: Length/tone filters, markdown stripping (if needed), channel capability adjustments.
- **Deliver**: Adapter sends response; errors can transition to `Recover`.
- **Recover**: Fallback messaging on generation/delivery failure.
- **Complete**: Turn finalized; telemetry/logs emitted.

## Transitions (happy path)

Idle → Ingress → Gate → Intent Classified → Policy Check → Context Assembled → LLM Call → Post-Process → Deliver → Complete

## Early exits / branches

- Gate → Ignore (not summoned / blocked channel)
- Gate → Refuse (dismissed / user muted / platform mode blocks)
- Policy Check → Refuse (safety violation, operator lockdown)
- LLM Call → Recover (errors, empty output) → Complete
- Deliver → Recover (permission errors, channel missing) → Complete

## Inputs at each stage

- **Ingress:** raw message, guild/user ids, channel, platform state snapshot (season/event/mode), guild config (channels/toggles).
- **Gate:** summon/dismiss words, allowed channels/modes, operator overrides.
- **Intent Classified:** intent models/routers in `tdos_intelligence/intent` and orchestrator.
- **Policy Check:** safety rails, rate limits, maintenance/degraded mode flags.
- **Context Assembled:** persona base (`personality/manager`), overlays from platform state, memory/RAG, devlog snippets, conversation history, system scaffolding.
- **LLM Call:** provider selection, max tokens, temperature, retries.
- **Post-Process:** formatting guards, truncation, emoji/punctuation normalization.
- **Deliver:** adapter send, audit metadata.

## Owner and source of truth

### Session Management (Consolidated - Task 9):

- **Primary Service:** [abby_core/services/conversation_service.py](../../abby_core/services/conversation_service.py)
- **Session Storage:** MongoDB `sessions` collection (direct operations, no intermediate layers)
- **Session Lifecycle:** `create_session()`, `close_session()`, `record_exchange()` - all atomic operations
- **Turn Limits:** Enforced at session level (default: 10 turns per session)
- **Cooldown:** Applied after reaching turn limit, expires automatically

### State Resolution:

- FSM logic lives across the orchestrator/intent layer and adapter cogs
- Canonical state axes defined in [STATE_MAP.md](STATE_MAP.md)
- Persona and overlays: `abby_core/personality/manager.py`
- Platform state snapshot: `system_state` collection (seasons/events/modes)
- Guild config: `guild_configuration` collection

### Legacy Code (Removed):

- `_legacy_create_session()`, `_legacy_close_session()` - Consolidated into ConversationService
- `session_repository.py` - Removed (redundant abstraction layer)

## Invariants

- Generation state is ephemeral; do not persist assembled prompts or outputs unless tied to a lifecycle artifact (e.g., announcements).
- Platform state and safety checks must occur before LLM invocation.
- Delivery must not mutate platform or configuration state.

## Hooks for new adapters

- Implement Ingress/Gate/Deliver in the adapter; reuse shared intent and context assembly.
- Surface adapter-specific delivery constraints in Post-Process (e.g., markdown, length limits).
- Emit telemetry per state transition for observability.
