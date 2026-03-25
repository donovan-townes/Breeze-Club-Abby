# System Architecture (10,000-foot view)

This document is box-and-arrow orientation for engineers and future-you.

## Major subsystems

- **Platform State:** Canonical seasons, events, eras, modes. Stored in Mongo `system_state` and `system_state_instances`. Governs platform-wide effects (XP reset, persona overlays). **Atomic activation** via [StateActivationService](../abby_core/services/state_activation_service.py) with MongoDB transactions ensures consistent state transitions, automatic deactivation of conflicting states, and full operator audit trail. State validation enforced pre-activation via [StateValidationService](../abby_core/system/state_validation_service.py) including persona overlay validation against PersonalityManager.

- **Lifecycle / Events:** Announcement lifecycle and scheduled content. Canonical details live in [lifecycle/LIFECYCLE_STATE.md](../lifecycle/LIFECYCLE_STATE.md). This page only summarizes that lifecycle is unified through `content_delivery_items` and routed via AnnouncementDispatcher with DLQ handling.

- **Session Management:** Conversation session lifecycle consolidated into [ConversationService](../abby_core/services/conversation_service.py) with **direct MongoDB operations** (no intermediate abstraction layers). Sessions track: create → active → cooldown → closed/expired states. Turn limits enforced atomically with fairness guarantees. Legacy session*repository and \_legacy*\* functions removed for clarity.

- **Observability:** Comprehensive audit trails across all services. **ConversationAnalyticsService** (Task 20) provides session metrics aggregation (count by state, intent distribution, health scoring). **MetricsService** enhanced with `get_unified_announcement_metrics()` (Task 12) for cross-service metrics queries. **Scheduler long-running job detection** (Task 22) warns about jobs exceeding 30 seconds. All generation costs tracked in permanent `generation_audit` collection for 50-year cost projections.

- **Generation Pipeline:** Intent → context assembly → LLM invocation → post-processing. Canonical flow lives in [runtime/GENERATION_PIPELINE.md](../runtime/GENERATION_PIPELINE.md) and state semantics in [lifecycle/GENERATION_STATE.md](../lifecycle/GENERATION_STATE.md).

- **Scheduling:** **SchedulerService is the canonical single scheduler** for all background jobs (Discord, web, CLI). Platform-agnostic tick-based execution model dispatches jobs to registered handlers. Atomic job claiming prevents double-execution in multi-instance deployments. All scheduling goes through SchedulerService—no Discord @tasks.loop patterns. Full details: [runtime/SCHEDULER_ARCHITECTURE.md](../runtime/SCHEDULER_ARCHITECTURE.md).

- **Turn Management:** User conversation turn limits enforced atomically via [TurnManager](../abby_core/discord/adapters/turn_manager.py). Atomic MongoDB operations prevent race conditions under concurrent load.

- **Prompt Assembly:** System prompt building delegated to [PromptBuilder](../abby_core/llm/prompt_builder.py) (extracted from personality/manager.py) to cleanly separate persona definition (WHO) from prompt assembly (HOW).

- **Economy & Gameplay:** XP, leveling, and event-bound gameplay toggles; game stats stored in Mongo collections; effects gated by platform state.

- **Persistence:** MongoDB as primary source of truth; minimal in-memory caches (persona, scheduler handlers) for performance. All state reads use snapshot isolation during concurrent transitions.

- **Adapters:** Discord cog layer bridges platform services (scheduler, announcements, games) to guild channels and commands.

## Interaction map (narrative)

1. **State drives behavior:** Active season/event from platform state enables or disables effects (XP reset, persona overlay, gameplay toggles).
2. **Scheduling runs work:** Scheduler polls Mongo job configs → invokes handlers (announcement generation, daily announcements, random messages, maintenance, games) → handlers read guild config and platform state.
3. **Lifecycle executes:** Announcement events are recorded → generation job renders content → delivery job ships to channels → archives outcomes in `deliveries`.
4. **Generation responds:** A user action or scheduled prompt triggers intent → context factory builds conversation envelope (persona + overlays + guild context + optional RAG) → LLM respond → post-processing trims/normalizes.
5. **Operators govern:** Admin actions mutate platform state, queue announcements, or change guild configuration; all critical changes persist in Mongo with audit-friendly fields.

## Boundaries and contracts

- **Platform state vs gameplay:** Gameplay flags live on event effects; they must not alter persona directly—overlays only apply via state-derived rules.
- **Lifecycle vs generation:** Lifecycle stores content readiness; generation is stateless per call. Delivery only sends "ready" items. Automatic retries with exponential backoff prevent permanent delivery failures.
- **Configuration vs platform state:** Guild/user preferences never override canonical platform state; they shape local execution (channels, toggles).
- **Adapters vs services:** Core services (scheduler, announcements, persona, DLQ, metrics) are platform-agnostic; adapters perform I/O and channel selection. DLQService and MetricsService are protocol-agnostic and can be reused across platforms (Discord, web, etc.).
- **Generation auditing:** All LLM calls (chat + summary + analysis) logged to `generation_audit` collection with full metadata: tokens, costs, latency, intent, session context. Enables 50-year cost projections and capacity planning.
- **Turn limit atomicity:** Conversation turn limits enforce fairness via MongoDB atomic operations. Turn increment happens **before** LLM invocation using `findOneAndUpdate` with conditional filter (`turn_count < max_turns`). Prevents race conditions from parallel requests bypassing limits. Implementation: [TurnManager.increment_and_check_turn()](../abby_core/discord/adapters/turn_manager.py) delegates to [usage_gate_service.py](../abby_core/services/usage_gate_service.py) `increment_and_check_turn_limit()`.
- **State determinism:** Concurrent state reads use MongoDB snapshot isolation (`ReadConcern(level="snapshot")`) to guarantee all effects merges see the same active states. Effects merge precedence: priority DESC → start_at DESC. Results are deterministic and reproducible across 50 years of operation.
- **Prompt assembly separation:** System prompt building (HOW to talk to LLM) is now separate from persona definition (WHO Abby is). [PromptBuilder](../abby_core/llm/prompt_builder.py) lives in llm/ module; personality/ only defines persona. Enables independent evolution of prompt strategies without persona drift.

## Minimal data flow sketches

- **Announcements:** state change → `record_event` (in `content_delivery_items`) → `generation_status=pending` → background generation job → `generation_status=ready` + `generated_message` → delivery job → channel send → `deliveries[]` updated.
- **Season rollover:** scheduler job → platform state activate next season → effects applied (XP reset eligibility, persona overlay inputs) → economy/gameplay read new state on next operation.
- **Generation request:** trigger → intent layer → context factory (persona base + overlays + guild memory + optional RAG/devlog) → LLM → sanitize/length trim → send.

Keep this page high-level; implementation lives in code. For state ownership and allowed mutations, see STATE_MAP.
