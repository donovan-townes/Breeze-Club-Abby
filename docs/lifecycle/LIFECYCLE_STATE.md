# Lifecycle State

Objects that move through stages (created → generated → delivered → archived). Today: announcements and scheduled content.

## Source of truth

- Mongo `content_delivery_items` (unified collection for all announcements, system events, world announcements, scheduled content)
  - **PRIMARY ENTRY POINT:** [abby_core/services/announcement_dispatcher.py](../../abby_core/services/announcement_dispatcher.py) - Creates announcements with operator audit trail
  - Internal helper: [abby_core/services/content_delivery.py](../../abby_core/services/content_delivery.py) `_create_content_item()` (do not call directly)
  - Event routing: [abby_core/services/events_lifecycle.py](../../abby_core/services/events_lifecycle.py) routes system events through dispatcher

## Stages (State Machine)

**Lifecycle States:** `draft` → `generated` → `queued` → `delivered` → `archived`

- `lifecycle_state`: Primary state machine (above)
- `generation_status`: `pending` | `ready` | `error` (subprocess during generation phase)
- `delivery_status`: `pending` | `delivered` | `failed` (subprocess during delivery phase)
- `scheduled_at`: UTC datetime for scheduled delivery (items only delivered when `scheduled_at <= now`)

### State Transitions:

- **draft → generated:** Announcement dispatcher marks content generated (with operator_id audit)
- **generated → queued:** Dispatcher queues for delivery (with channel/role info)
- **queued → delivered:** Unified content dispatcher delivers to Discord (stores message_id)
- **delivered → archived:** Cleanup job removes old items (7-day retention)

## Delivery Retry & Error Handling (Dead-Letter Queue)

### When a delivery fails, items are routed to the DLQ for retry or manual review:

- **Dead-Letter Queue (DLQ):** `content_delivery_dlq` collection
- **Error Categories:**
  - `state_transition`: State activation failed (e.g., invalid state ID)
  - `validation`: Invalid data (e.g., missing required fields)
  - `transient`: Network/timeout errors (auto-retry eligible)
  - `unknown`: Uncategorized errors (requires investigation)
- **Retry Policy:**
  - Max retries: 3 attempts
  - Backoff: 5 min, 15 min, 30 min
  - After max retries: `status=abandoned` (requires operator intervention)
- **Diagnostics:** `DLQService.get_failure_diagnostics(dlq_item_id)` provides:
  - Root cause category
  - Retry history (last 3 attempts)
  - Remediation suggestions (specific to error type)
  - Related announcement details (title, state, operator)

**Owner:** [abby_core/services/dlq_service.py](../../abby_core/services/dlq_service.py)  
### Invoked From:

- Announcement dispatcher (generation failures, state errors)
- Unified content dispatcher (delivery failures)
- Scheduler jobs (timeout errors)

**Persistence:** Mongo `content_delivery_dlq` (permanent audit trail)  
**Impact:** Ensures no silent failures; all errors categorized and retryable

## Ownership and mutation

- **Operators create announcements:** Via `/announce` command or direct API calls to `create_announcement_for_delivery()`
- **System creates announcements:** Season transitions, scheduled events via `events_lifecycle.py` routing through unified content pipeline
- **Unified content dispatcher:** Single scheduler job handles generation → delivery → cleanup (replaces 3 legacy handlers)
- **Atomic transitions:** Each state change is atomic with audit trail (operator_id, timestamps, error context)
- **Idempotency:** Prevents duplicate announcements via unique constraints and state validation

**IMPORTANT:** Always use `create_announcement_for_delivery()` from `abby_core.services.content_delivery` for operator audit trail. Do NOT call `_create_content_item()` directly. The old `AnnouncementDispatcher.create_announcement()` is DEPRECATED (removal Q2 2026).

## Invariants

- Generation happens before delivery; delivery only for `ready` items with `scheduled_at <= now` (UTC)
- Idempotency keys prevent duplicate events
- Generated content is persisted with full audit trail (operator_id, timestamps, error context)
- Timezone-aware scheduling: User input converted to UTC for storage, prevents premature delivery
- State transitions are atomic: uses MongoDB transactions for consistency guarantees

## Key functions

### Primary Services:

- `create_announcement_for_delivery()` in [abby_core/services/content_delivery.py](../../abby_core/services/content_delivery.py) - PUBLIC API for creating announcements with operator audit
- `AnnouncementDispatcher.generate_content()` - Mark generated with operator_id
- `AnnouncementDispatcher.queue_for_delivery()` - Transition to queued state
- `AnnouncementDispatcher.deliver()` - Mark delivered with message_id
- `AnnouncementDispatcher.generation_failed()` - Route to DLQ on error

### Unified Job Handler:

- `execute_unified_content_dispatcher()` in [abby_core/discord/cogs/system/jobs/unified_content_dispatcher.py](../../abby_core/discord/cogs/system/jobs/unified_content_dispatcher.py)
  - Phase 1: Generate pending content (draft → generated)
  - Phase 2: Deliver generated content (generated → delivered, respects scheduled_at)
  - Phase 3: Archive old content (delivered → archived, 7-day TTL)

### Internal Helpers:

- `_create_content_item()` in [abby_core/services/content_delivery.py](../../abby_core/services/content_delivery.py) (internal only, do not call directly)
- `record_season_transition_event()` in [abby_core/services/events_lifecycle.py](../../abby_core/services/events_lifecycle.py) (routes through dispatcher)

## Observability

### Audit Trail:

- All announcements track: `operator_id`, `created_at`, `updated_at`, `scheduled_at`
- State transitions logged with timestamps and operator context
- Full lifecycle visibility: who created, when generated, when delivered, which message_id

### Metrics & Monitoring:

- `MetricsService.record_transition()` tracks state changes in `content_delivery_metrics` (90-day TTL)
- `MetricsService.get_unified_announcement_metrics()` aggregates delivery + generation metrics in single query
- Generation audit: All LLM calls logged with tokens, cost, latency in `generation_audit` (permanent)
- Long-running job detection: Scheduler warns about jobs exceeding 30 seconds

### DLQ Diagnostics:

- `DLQService.get_failure_diagnostics()` provides failure analysis with remediation suggestions
- Error categorization (state_transition, validation, transient, unknown)
- Retry history tracking (last 3 attempts with timestamps)

### Logs to Watch:

- `[📝 announcement] CREATED` - Announcement created with operator_id
- `[✅ announcement] GENERATED` - Content generated successfully
- `[📤 announcement] QUEUED` - Queued for delivery
- `[✉️ announcement] DELIVERED` - Delivered to Discord with message_id
- `[🚫 dlq] ROUTED` - Failed item routed to DLQ
- `[⚠️ long_job]` - Job execution exceeded 30 seconds

See also: [STARTUP_LOGGING.md](../reference/STARTUP_LOGGING.md) for complete log examples and testing guidance.
