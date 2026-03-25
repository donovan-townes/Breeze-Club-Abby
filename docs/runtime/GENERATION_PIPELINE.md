# Generation Pipeline (How Abby Thinks)

Purpose: show the orchestration from trigger to final message. This is conceptual; implementation lives in code.

## Stages

1. **Trigger & intent**
   - Source: user message, slash command, scheduled job, operator action.
   - Intent classification and routing handled by orchestrator/intent layer (see `tdos_intelligence/orchestrator.py` and `abby_core/intent` modules).
1. **Conversation FSM / policy check**
   - Determine whether to engage, refuse, or nudge based on mode, safety, and summon/dismiss triggers.
   - Consult configuration state (summon mode, channels) and platform state (modes/events).
1. **Context assembly**
   - Persona base: loaded via [abby_core/personality/manager.py](abby_core/personality/manager.py).
   - Overlays: derived from platform state (`get_persona_overlays`) and applied in persona manager.
   - Guild/user context: memory snippets, channel metadata, and prior messages (via `build_conversation_context`).
   - **Memory/RAG Injection (Safety-Gated - Task 24):** Custom guild memory is only injected for knowledge-seeking intents:
     - **Inject When:** Message contains "?" OR keywords (help, know, tell, show, what, how, where, when, why, rule, information, detail, explain, describe, find, look, search)
     - **Block When:** Casual small-talk, greetings, off-topic chat
     - **Sanitization (Task 25):** All custom_memory fields sanitized against injection attacks before LLM injection
     - **Audit Trail:** All memory injection decisions logged with operator_id and intent
     - **Owner:** [abby_core/adapters/orchestrator_adapter.py](abby_core/adapters/orchestrator_adapter.py) process_message()
   - Knowledge: optional RAG memory or devlog injection chosen by context factory (see [abby_core/llm/context_factory.py](abby_core/llm/context_factory.py)).
   - System scaffolding: safety rails, length budgets, formatting constraints.
1. **LLM invocation**
   - Call `respond` (async) with assembled context and prompt; respects max retries and throttling.
   - Generation state is ephemeral per request (no persistence of prompt or outputs beyond logging/telemetry).
   - Cost tracking and audit are defined in [../lifecycle/GENERATION_STATE.md](../lifecycle/GENERATION_STATE.md).
1. **Post-generation checks**
   - Effects and state validation are part of platform safety gates.
   - See [../lifecycle/PLATFORM_STATE.md](../lifecycle/PLATFORM_STATE.md) and [../lifecycle/GENERATION_STATE.md](../lifecycle/GENERATION_STATE.md).

1. **Delivery & error recovery**
   - Adapter sends to channel / user / webhook; failures are logged and surfaced to operators.
   - Delivery retries and DLQ behavior are defined in [../lifecycle/LIFECYCLE_STATE.md](../lifecycle/LIFECYCLE_STATE.md).

## Key properties

- **Ephemeral by design:** No generated prompt/content is persisted unless part of an explicit lifecycle (e.g., announcements).
- **State-aware:** Persona overlays and mode/season effects are injected at context-build time, not baked into static prompts.
- **Config-scoped:** Guild/user preferences adjust context (channels, toggles) but do not override platform state.
- **Observable:** Logging around prompt assembly, retries, and post-processing for debugging; [MetricsService](../abby_core/services/metrics_service.py) tracks timing, errors, and cost per transition. Structured traces available via operator panel (Metrics Dashboard).
- **Resilient:** DLQService gracefully handles retryable vs non-retryable errors; missing announcements don't spam logs.

## Inputs and outputs

- Inputs: trigger metadata (intent), platform state (season/event/mode), configuration state (guild/user), memory/RAG slices, persona base + overlays.
- Output: sanitized text (or embed/payload) ready for adapter delivery.

## Hard rules

- Do not persist generation state.
- Apply overlays only through platform state effects.
- Keep safety and refusal rules in system scaffolding, not scattered prompts.

Use this doc when evolving prompts or adding new adapters; align changes with STATE_MAP to avoid leaking new persistent state.
