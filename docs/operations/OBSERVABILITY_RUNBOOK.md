# Observability, Metrics & Alerting Runbook

Comprehensive guide to Abby's observability stack: structured logging, metrics collection, alerting rules, and incident triage.

**Last Updated:** January 31, 2026  
**Environment:** All (dev/staging/production)  
**Tools:** JSONL logging, MetricsService, Grafana, DLQService

---

## Executive Summary

Abby implements **three-layer observability** for 50-year operational safety:

1. **Structured Logging** — Every event logged to `logs/abby.jsonl` with full context
2. **Metrics Collection** — Transition times, generation costs, error rates in MetricsService
3. **Alerting & Triage** — Grafana dashboards, automated alerts, DLQ diagnostics

---

## Layer 1: Structured Logging

### Log Output

All logs are written to **`logs/abby.jsonl`** in structured JSON format:

```jsonl
{"timestamp": "2026-01-31T14:23:45.123Z", "level": "INFO", "logger": "abby_core.discord.bot", "message": "Bot started successfully", "process_id": 12345}
{"timestamp": "2026-01-31T14:23:46.045Z", "level": "INFO", "logger": "abby_core.services.scheduler", "message": "Scheduler tick started", "metrics": {"jobs_pending": 3, "jobs_running": 1}, "tick_id": "abc123"}
{"timestamp": "2026-01-31T14:24:02.567Z", "level": "WARNING", "logger": "abby_core.services.metrics_service", "message": "Generation took longer than baseline", "metrics": {"generation_time_ms": 4521, "baseline_p95_ms": 3000}, "user_id": "123456789", "guild_id": "987654321"}
{"timestamp": "2026-01-31T14:25:10.890Z", "level": "ERROR", "logger": "abby_core.services.dlq_service", "message": "State transition failed", "error_category": "state_transition", "reason": "ValidateEffects failed", "exception": "EffectValidationError: ...", "retry_count": 0, "next_retry_at": "2026-01-31T14:26:10.890Z"}
```python

### Log Levels

| Level | Use Case | Example |
| ------- | ---------- | --------- |
| `DEBUG` | Development only | `_resolve_intent_candidate called with embeddings=[...]` |
| `INFO` | Important state changes | `Bot connected`, `Scheduler tick started`, `XP update committed` |
| `WARNING` | Degraded behavior (but recoverable) | `Generation time exceeded baseline`, `Low XP in season` |
| `ERROR` | Failure (retry or DLQ) | `State transition failed`, `MongoDB connection lost` |
| `CRITICAL` | System down | `Out of memory`, `Database unreachable after 30s` |

### Log Handler

The structured logging handler:

```python
from abby_core.observability.logging import StructuredJSONLHandler

handler = StructuredJSONLHandler(
    filename="logs/abby.jsonl",
    encoding="utf-8",
    mode="a"  # append-only for 50-year durability
)

## All logs include context
logger.info("Message", extra={
    "user_id": "123",
    "guild_id": "456",
    "metrics": {
        "generation_time_ms": 1234,
        "token_count": 450
    }
})
```python

### Startup Phases

At bot startup, Abby logs initialization milestones:

```python
## docs/guides/STARTUP_OPERATIONS_GUIDE.md defines these phases
STARTUP_PHASES = {
    "initialization": "Loading configuration",
    "database_connection": "Connecting to MongoDB",
    "cogs_loading": "Loading Discord cogs",
    "adapter_registration": "Registering platform adapters",
    "scheduler_setup": "Initializing scheduler",
    "ready": "Bot fully operational"
}
```python

### Startup Log Example:
```jsonl
{"timestamp": "2026-01-31T14:23:40.000Z", "level": "INFO", "startup_phase": "initialization", "elapsed_ms": 0}
{"timestamp": "2026-01-31T14:23:41.234Z", "level": "INFO", "startup_phase": "database_connection", "elapsed_ms": 1234}
{"timestamp": "2026-01-31T14:23:42.567Z", "level": "INFO", "startup_phase": "cogs_loading", "elapsed_ms": 1333}
{"timestamp": "2026-01-31T14:23:44.890Z", "level": "INFO", "startup_phase": "ready", "elapsed_ms": 4890}
```python

---

## Layer 2: Metrics Collection

### Metrics Service Overview

MetricsService tracks all operational metrics in MongoDB:

```python
from abby_core.services.metrics_service import MetricsService

metrics = MetricsService()

## Record a state transition
metrics.record_transition(
    user_id="123",
    guild_id="456",
    from_state="WAITING_FOR_INPUT",
    to_state="GENERATING_RESPONSE",
    duration_ms=1234
)

## Record generation timing
metrics.record_timing(
    operation="generation",
    duration_ms=2567,
    tokens_generated=350,
    metadata={"model": "gpt-4", "temperature": 0.7}
)

## Record error
metrics.record_error(
    user_id="123",
    error_type="ValidationError",
    error_message="Invalid state transition",
    category="state_transition"
)

## Query metrics
stats = metrics.get_performance_stats(
    operation="generation",
    last_n_days=7
)
## Returns: {"p50": 1200, "p95": 2500, "p99": 4000, "error_rate": 0.02}
```python

### Baseline Metrics (50-Year Model)

Abby startup should complete within these ranges:

| Metric | Target | Warning | Critical |
| -------- | -------- | --------- | ---------- |
| **Total startup time** | < 10s | > 15s | > 20s |
| **MongoDB connection** | < 0.1s | > 0.3s | > 0.5s |
| **Cogs loading** | 1.5–2s | > 2.5s | > 3s |
| **Adapter registration** | < 0.5s | > 1s | > 2s |
| **Scheduler setup** | < 0.5s | > 1s | > 2s |
| **Connection to Discord** | 2–4s | > 5s | > 10s |

### Usage Metrics (per guild):

| Metric | Target | Warning | Critical |
| -------- | -------- | --------- | ---------- |
| **Generation p50 latency** | 800–1200ms | > 1500ms | > 3000ms |
| **Generation p95 latency** | 1500–2000ms | > 2500ms | > 4000ms |
| **Delivery time** | 100–300ms | > 500ms | > 1000ms |
| **Error rate (generation)** | < 0.5% | > 1% | > 5% |
| **Error rate (state transition)** | < 0.1% | > 0.5% | > 2% |

### Accessing Metrics

### In Python:
```python
from abby_core.services.metrics_service import MetricsService

metrics = MetricsService()

## Get generation stats (last 7 days)
gen_stats = metrics.get_performance_stats(
    operation="generation",
    last_n_days=7
)
print(f"Generation p50: {gen_stats['p50']}ms")

## Get error trend
error_trend = metrics.get_error_trend(
    last_n_days=7
)
print(f"Error rate: {error_trend['error_rate']:.2%}")
```python

### In Grafana Dashboard:
```sql
-- Query: Generation latency over time
db.metrics.find({
    operation: "generation",
    timestamp: {$gte: ISODate("2026-01-24")}
}).sort({timestamp: 1})

-- Query: Error rate by category
db.metrics.aggregate([
    {$match: {error_category: {$exists: true}}},
    {$group: {
        _id: "$error_category",
        count: {$sum: 1}
    }}
])
```python

---

## Layer 3: Alerting & Triage

### Alerting Rules

Configure alerts in Grafana for threshold breaches:

### CRITICAL (Page on-call immediately):

- MongoDB unavailable for > 30s
- Generation error rate > 5%
- State transition failures > 10/min
- Scheduler not ticking for > 5 min
- Out of memory (< 100MB free)
- Storage quota exceeded

### WARNING (Notify ops channel, no page):

- Generation p95 > 2500ms
- XP season completion time > 60s
- Scheduler job failure rate > 1%
- DLQ backlog > 100 messages
- MongoDB slow queries > 1s

### INFO (Log only, visible in dashboard):

- New guild joined
- Guild removed
- Feature flag toggled
- Configuration reloaded
- User hit daily quota

### DLQ (Dead Letter Queue) Diagnostics

Failed operations are stored in the DLQ with full diagnostics:

```python
from abby_core.services.dlq_service import DLQService

dlq = DLQService()

## Get failure diagnostics
failures = dlq.get_failure_diagnostics(
    error_category="state_transition",
    last_n_hours=24
)

## Output
for failure in failures:
    print(f"""
    User: {failure['user_id']}
    Guild: {failure['guild_id']}
    Error: {failure['error_message']}
    Category: {failure['error_category']}
    Last retry: {failure['last_retry_at']}
    Retry count: {failure['retry_count']}
    """)
```python

### DLQ Record Schema:
```json
{
    "dlq_id": "uuid",
    "user_id": "123",
    "guild_id": "456",
    "operation_type": "state_transition",
    "error_category": "validation",
    "error_message": "EffectValidationError: XP gain invalid",
    "context": {
        "from_state": "WAITING_FOR_INPUT",
        "to_state": "GENERATING_RESPONSE",
        "user_level": 5,
        "xp_delta": -100
    },
    "retry_history": [
        {"timestamp": "2026-01-31T14:25:10.890Z", "attempt": 1, "error": "..."},
        {"timestamp": "2026-01-31T14:26:10.890Z", "attempt": 2, "error": "..."}
    ],
    "next_retry_at": "2026-01-31T14:30:00.000Z",
    "created_at": "2026-01-31T14:25:10.890Z"
}
```python

### Triage Procedure

When alert fires, follow this decision tree:

```python
Alert: Generation error rate > 5%
│
├─ Step 1: Check platform health
│   └─ Is MongoDB healthy?
│      ├─ NO → Page MongoDB admin, check connections
│      └─ YES → Continue
│
├─ Step 2: Check recent errors
│   └─ Query error logs
│      ├─ Common error? (e.g., API key expired)
│      │  └─ Fix: Rotate key, redeploy
│      ├─ Intermittent? (< 100 errors)
│      │  └─ Monitor: Likely transient, wait 5 min
│      └─ Persistent? (> 1000 errors)
│         └─ Escalate: Page on-call engineer
│
├─ Step 3: Check DLQ
│   └─ Any common patterns?
│      ├─ User_id pattern?
│      │  └─ Guild isolation breach? Investigate guild config
│      ├─ State transition pattern?
│      │  └─ Intent model regression? Check LLM performance
│      └─ Validation pattern?
│         └─ Effects invalid? Check state mutations
│
└─ Step 4: Monitor
    └─ Watch error rate for 15 min
       ├─ Declining? → Resolved, document
       └─ Rising? → Escalate to tier 2
```python

### Common Issues & Recovery

| Issue | Symptoms | Recovery |
| ------- | ---------- | ---------- |
| **MongoDB slow queries** | Generation p95 > 3000ms, long startup | Scale read replicas, add indexes, optimize queries |
| **OOM (out of memory)** | CRITICAL alert, bot crash | Increase container memory limit, profile memory usage |
| **Scheduler not ticking** | No jobs running for > 5 min | Restart scheduler service, check MongoDB |
| **State transition stuck** | DLQ backlog grows, users report no progress | Manual intervention: mark operation as failed, move to next state |
| **Generation quality degraded** | Error rate stable but user complaints | Check LLM model version, verify RAG documents fresh |
| **Guild data corrupt** | Inconsistent state for single guild | Restore from snapshot, skip corrupted operations |

---

## Key Logs to Watch

### Startup

```bash
## Watch bot startup (should complete in < 20s)
tail -f logs/abby.jsonl | grep startup_phase

## Output should be:
## initialization → database_connection → cogs_loading → ready
```python

### Scheduler Heartbeat

```bash
## Watch scheduler ticking every 60s
tail -f logs/abby.jsonl | grep "Scheduler tick"

## Should see new tick every 60s
## If gap > 90s, scheduler may be stuck
```python

### State Transitions

```bash
## Watch user conversations progressing
tail -f logs/abby.jsonl | grep "record_transition"

## Should see progression: WAITING → GENERATING → RESPONDING → READY
## If stuck on one state > 30s, investigate
```python

### Errors

```bash
## Watch error logs
tail -f logs/abby.jsonl | grep '"level": "ERROR"'

## Separate by category
tail -f logs/abby.jsonl | jq 'select(.error_category)'
```python

---

## 50-Year Observability Strategy

### Annual Audits

- [ ] Review baseline metrics (has workload changed?)
- [ ] Audit log retention (should retain full 7 years for compliance)
- [ ] Verify alerting rules still relevant
- [ ] Check metrics schema for deprecated fields

### 5-Year Reviews

- [ ] Migrate logging infrastructure (JSON → newer format?)
- [ ] Evaluate observability vendor changes (Grafana alternatives?)
- [ ] Design new dashboards for emerging concerns
- [ ] Plan metrics schema evolution

### 10-Year Reviews

- [ ] Full observability redesign
- [ ] Consolidate metrics with external platforms (Datadog, New Relic?)
- [ ] Implement distributed tracing for end-to-end visibility
- [ ] Plan observability for multi-region deployment

---

## Related Documents

- [STARTUP_OPERATIONS_GUIDE.md](STARTUP_OPERATIONS_GUIDE.md) — Startup metrics baseline
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Incident triage procedures
- [SCHEDULER_JOBS_CATALOG.md](SCHEDULER_JOBS_CATALOG.md) — Scheduler monitoring
