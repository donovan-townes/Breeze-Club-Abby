# Service Contracts

## Purpose

This document defines the **contract boundaries** between ABBY core services. It is the canonical reference for what each service **accepts**, **returns**, **owns**, and **guarantees**. It is designed to remain stable for 20–50 years even as implementations evolve.

## Contract Principles

- **Explicit ownership:** Every responsibility maps to a single service.
- **Idempotent operations:** Retried requests must not double‑apply effects.
- **Side‑effect transparency:** Write operations must declare all collections mutated.
- **Async‑first:** Long‑running work must be scheduled, not executed inline.
- **Traceable:** All service calls must emit trace identifiers and result status.

## Shared Contract Fields

Every service request should include:

- `request_id` (string) — unique per operation
- `actor_id` (string) — user or system actor
- `guild_id` (string, optional) — scope for guild operations
- `correlation_id` (string) — cross‑service trace
- `timestamp` (UTC ISO‑8601)

Every service response should include:

- `status` (`success|retryable_error|fatal_error`)
- `errors[]` (optional) — structured error list
- `warnings[]` (optional)
- `duration_ms`

## Service Contract Registry

### SchedulerService

**Purpose:** Canonical scheduler for all background jobs.

**Consumes:**

- `scheduler_jobs` collection

**Produces / Mutates:**

- Updates `scheduler_jobs.next_run_at`, `last_run_at`, `last_error`
- Emits scheduler metrics via MetricsService

**Guarantees:**

- At‑most‑once execution per job tick
- Atomic job claiming
- Idempotent handler invocation

**Failure Policy:**

- Retry with backoff on retryable errors
- Never crash loop due to a single job

---

### AnnouncementDispatcher

**Purpose:** Orchestrates content delivery lifecycle.

**Consumes:**

- `content_delivery_items` (status transitions)

**Produces / Mutates:**

- `content_delivery_items.generation_status`
- `deliveries[]` (delivery audit)

**Guarantees:**

- Never deliver content before status is `ready`
- Exactly‑once delivery per delivery record

**Failure Policy:**

- Delivery failures route to DLQService
- Retries controlled by lifecycle status

---

### StateActivationService

**Purpose:** Activates platform state transitions.

**Consumes:**

- `system_state`, `system_state_instances`

**Produces / Mutates:**

- Activates or deactivates state instances
- Writes audit trail

**Guarantees:**

- Atomic transitions (MongoDB transactions)
- Conflicting states are deactivated before activation

---

### StateValidationService

**Purpose:** Validates invariants before activation.

**Consumes:**

- Proposed state payload
- Current platform state

**Produces:**

- Validation report (pass/fail + reasons)

**Guarantees:**

- Does not mutate state
- Deterministic validation outcome

---

### MetricsService

**Purpose:** Centralized metrics aggregation.

**Consumes:**

- Events, counters, timers from all services

**Produces:**

- Aggregated metrics and health indicators

**Guarantees:**

- Non‑blocking writes
- Best‑effort delivery

---

### DLQService

**Purpose:** Handles failed jobs and delivery events.

**Consumes:**

- Failed events from SchedulerService or delivery pipeline

**Produces / Mutates:**

- DLQ entries (retryable vs fatal)

**Guarantees:**

- No drop of fatal failures
- Retryable failures are scheduled for reprocessing

---

### PersonalityManager

**Purpose:** Applies persona base + overlays.

**Consumes:**

- Persona base config
- State‑derived overlays

**Produces:**

- Final persona context

**Guarantees:**

- Overlay application is deterministic
- No side effects beyond returned context

---

### Intent Orchestrator

**Purpose:** Routes inbound messages to intent + handlers.

**Consumes:**

- Message payload
- Context factory output

**Produces:**

- Intent classification result
- Action plan

**Guarantees:**

- Safe refusal for disallowed intents
- Memory injection gating enforced

## Cross‑Service Constraints

- **No direct adapter coupling:** Services must not call Discord/Web adapters directly.
- **State access rules:** Only StateActivationService mutates platform state.
- **Scheduler exclusivity:** Background work must be scheduled, not inlined.
- **DLQ routing:** All retryable failures must be routed to DLQService.

## Reference

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [runtime/SCHEDULER_ARCHITECTURE.md](../runtime/SCHEDULER_ARCHITECTURE.md)
- [lifecycle/STATE_INVARIANTS.md](../lifecycle/STATE_INVARIANTS.md)
