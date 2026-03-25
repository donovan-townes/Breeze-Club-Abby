# Abby Platform — Canonical Overview

**Version:** 1.0  
**Date:** February 3, 2026  
**Maintenance Horizon:** 50 years  
**Read This First:** Before touching any other document

---

## What Abby Is

Abby is a **state-driven conversational platform** designed to host long-lived creative communities across multiple platforms (Discord, web, CLI). It combines **canonical platform state** (seasons, events, modes) with **per-guild preferences** and **ephemeral LLM context** to maintain coherence over decades while remaining adaptive in the moment.

Abby is not a chatbot. It is a **platform for building conversational experiences** with serious architectural discipline.

---

## Problem Space

Creative communities face three fundamental challenges:

1. **Temporal coherence** — Communities need consistent identity across months and years, not just individual conversations
2. **Context-aware engagement** — Responses must incorporate community history, guild preferences, and platform-wide events
3. **Operational reliability** — Long-lived systems require observability, safety rails, and graceful degradation

Abby solves these by making **state explicit, queryable, and auditable** rather than implicit in prompts or code.

---

## Core Architectural Pillars

### 1. State-First Design

All behavior keys off **canonical state axes** (platform, lifecycle, gameplay, configuration, generation). State is not scattered across flags or ad-hoc variables—it has explicit ownership, mutation rules, and persistence contracts.

- **Platform state** (seasons, events, modes) drives XP resets, persona overlays, and feature toggles
- **Lifecycle state** (announcements, scheduled content) moves through explicit stages with audit trails
- **Configuration state** (guild/user preferences) shapes execution but never overrides platform state

**Why this matters:** State changes are versioned, auditable, and testable. No "hidden flags" or "magic configuration."

### 2. Platform-Agnostic Core

Core services (scheduler, announcements, persona, DLQ, metrics) are **adapter-agnostic**. Platform-specific I/O (Discord, web, CLI) lives in **adapters** that implement core interfaces.

This enables:

- Adding new platforms without rewriting business logic
- Testing core logic without mocking Discord API
- Long-term evolution as platforms change

**Why this matters:** Abby can outlive any single platform. Discord today, web tomorrow, spatial computing in 2030.

### 3. Lifecycle Clarity

Content (announcements, scheduled posts) moves through **explicit stages**:

```
pending → ready → delivered → archived
```

Failed items route to **Dead-Letter Queue (DLQ)** with:

- Categorized errors (state_transition, validation, transient, unknown)
- Retry policies (exponential backoff, max 3 attempts)
- Diagnostic tooling (root cause, remediation suggestions)

**Why this matters:** No silent failures. Every content item has a complete audit trail.

### 4. Composable Generation

LLM responses are assembled from **layers** (persona base + overlays + guild context + memory + devlogs) rather than monolithic prompts.

```
Persona Base (who Abby is)
  + State Overlays (seasonal tone shifts)
  + Guild Context (channel, preferences)
  + Memory (RAG, custom guild knowledge)
  + Devlogs (self-referential updates)
  = Final Prompt
```

This enables:

- Persona evolution without rewriting prompts
- Context injection policies (memory gating for knowledge-seeking queries only)
- Testing individual layers in isolation

**Why this matters:** Prompts are not magic incantations. They're composable, testable contracts.

### 5. Operator Maturity

Operators have **first-class tooling** for:

- State activation (seasons, events, modes)
- Announcement queueing (system, world, scheduled)
- Incident response (DLQ inspection, metrics dashboard)
- Audit review (all critical operations logged with operator ID, timestamp, reason)

**Why this matters:** Operations are not an afterthought. They're designed for 50-year maintainability.

---

## Operational Model

### Execution Model

Abby uses a **canonical scheduler** (SchedulerService) with tick-based execution (60-second intervals):

**System Jobs:**

- Heartbeat (health monitoring)
- Bank interest (economy)
- Maintenance (cleanup)

**Guild Jobs:**

- Daily announcements
- Random messages
- Event-bound games

**Guarantees:**

- Atomic job claiming prevents duplicate execution in multi-instance deployments
- Long-running job detection (warns if job exceeds 30 seconds)
- Idempotent execution (safe to retry)

### Data Model

**MongoDB** as primary source of truth with minimal in-memory caching:

| Collection               | Purpose                       | Owner                  |
| ------------------------ | ----------------------------- | ---------------------- |
| `system_state`           | Platform state definitions    | StateActivationService |
| `system_state_instances` | Active state instances        | StateActivationService |
| `content_delivery_items` | Lifecycle (announcements)     | AnnouncementDispatcher |
| `content_delivery_dlq`   | Failed deliveries             | DLQService             |
| `users`                  | Multi-platform user profiles  | UserRepository         |
| `sessions`               | Conversation sessions         | ConversationService    |
| `guild_configuration`    | Guild preferences             | GuildConfigService     |
| `generation_audit`       | LLM call logs (costs, tokens) | Generation pipeline    |

### Observability Model

**Structured JSON logging** (JSONL format):

```json
{
  "timestamp": "2026-02-03T14:23:45.123Z",
  "level": "INFO",
  "service": "scheduler",
  "event": "job_executed",
  "job_type": "heartbeat",
  "duration_ms": 342,
  "status": "success"
}
```

**Metrics collection:**

- All LLM calls logged to `generation_audit` for 50-year cost projections
- DLQ diagnostics for root cause analysis (error category, retry count, remediation)
- Operator panels for metrics dashboard (24-hour performance, 7-day trends, cost analysis)

---

## State Model (High Level)

| Domain            | Source of Truth                 | Mutation Owner          | Consumers                   |
| ----------------- | ------------------------------- | ----------------------- | --------------------------- |
| **Platform**      | `system_state`                  | StateActivationService  | Economy, Persona, Scheduler |
| **Lifecycle**     | `content_delivery_items`        | AnnouncementDispatcher  | Scheduler, Discord cogs     |
| **Session**       | `sessions`                      | ConversationService     | Turn management, Analytics  |
| **Configuration** | `guild_configuration`, env vars | Guild config, Operators | All services (read-only)    |
| **Generation**    | In-memory request context       | ContextFactory          | LLM invocation              |

### Key Invariants

1. **Platform state transitions are atomic** — MongoDB transactions ensure consistency
2. **Gameplay features are event-bound** — No direct persona mutation
3. **Configuration never overrides platform state** — Guild preferences shape execution, not identity
4. **Generation state is ephemeral** — No prompt persistence outside lifecycle

### State Guarantees

- **Deterministic effects merging** — States sorted by priority DESC, start_at DESC
- **Snapshot isolation** — Concurrent reads see consistent state during transitions
- **Audit trails** — All state changes record operator_id, timestamp, reason
- **Validation gates** — Pre-activation checks prevent invalid state (e.g., non-existent persona overlays)

---

## Long-Term Intent

Abby is designed for **20–50 year evolution** without major rewrites:

### Architectural Stability Principles

1. **State models are stable** — New features add state types, not refactor existing ones
2. **Adapters are swappable** — Platform changes (Discord → Web → future) require only adapter updates
3. **Documentation is canonical** — Architecture docs are versioned, audited, and treated as contracts
4. **Telemetry is permanent** — All LLM costs, error rates, and performance metrics archived for future analysis

### Evolution Strategy

**What changes:**

- Adapters (platforms evolve)
- Schemas (data models extend)
- Operations (deployment tooling improves)

**What stays stable:**

- State ownership boundaries
- Service contracts
- Lifecycle stages
- Generation pipeline structure

### Future-Proofing Mechanisms

- **Feature flags** — Gradual rollout without code changes
- **API versioning** — Backward compatibility for clients
- **Schema migrations** — Backfill procedures with validation
- **Audit trails** — Permanent record for future debugging

---

## Success Criteria

Abby succeeds when:

1. **A new engineer can understand the system in 2 weeks** (not 6 months)
2. **Adding a new platform takes days** (not months)
3. **State changes are auditable 10 years later** (who, when, why)
4. **Incidents are triaged in minutes** (not hours)
5. **The system outlives its original authors** (20+ year lifespan)

---

## Anti-Patterns (What Abby Is Not)

❌ **Not a monolithic bot** — Core is platform-agnostic, adapters are swappable  
❌ **Not prompt-driven** — State is explicit, not hidden in prompts  
❌ **Not configuration-by-flags** — State has ownership, not scattered boolean flags  
❌ **Not fire-and-forget** — Every operation has audit trails and error handling  
❌ **Not a hobby project** — Designed for decades-long maintenance

---

## Navigation

### Start Here (First Week)

1. [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md) — Product and platform intent
2. [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md) — Subsystem topology
3. [STATE_MAP.md](../lifecycle/STATE_MAP.md) — State ownership registry
4. [OPERATOR_GUIDE.md](../operations/OPERATOR_GUIDE.md) — Day-to-day operations

### Deep Dives (By Domain)

- **Architecture:** [architecture/](../architecture/) — Service boundaries, contracts, invariants
- **Lifecycle:** [lifecycle/](../lifecycle/) — State machines, transitions, ownership
- **Data:** [data/](../data/) — Persistence layer, schemas, collections
- **Runtime:** [runtime/](../runtime/) — Execution model, scheduling, generation
- **Operations:** [operations/](../operations/) — Configuration, security, incidents

### Full Index

[INDEX.md](../INDEX.md) — Complete documentation navigation

---

## Maintenance Notes

**Review Schedule:**

- **Annual:** Verify state model still matches reality
- **5-year:** Assess architectural debt, plan major refactors
- **10-year:** Evaluate if core pillars still hold, update or deprecate

**Update Triggers:**

- New state domain added
- Platform adapter added (web, CLI, etc.)
- Major architectural change (e.g., new persistence layer)
- Operator feedback on clarity

**Ownership:** Platform Architecture Team  
**Last Reviewed:** February 3, 2026  
**Next Review:** February 2027

---

**This is the document you read before touching any other document.**

If this overview doesn't match reality, reality is wrong—update the code, not this doc.
