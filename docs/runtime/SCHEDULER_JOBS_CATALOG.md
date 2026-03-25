# Scheduler Jobs Catalog

Complete inventory of all scheduled background jobs in Abby: system jobs, guild jobs, ownership, schedules, and idempotency guarantees.

**Last Updated:** February 2, 2026  
**Maintenance:** Platform-independent (usable in web, CLI, Discord)  
**Schedule Engine:** ✅ **SchedulerService is the canonical single scheduler** (AsyncIO-based, 60-second tick interval)  
**Primary Documentation:** [SCHEDULER_ARCHITECTURE.md](SCHEDULER_ARCHITECTURE.md) — Complete architecture and usage guide

---

## Executive Summary

The Scheduler subsystem runs **6 core system jobs** plus **guild-scoped jobs** from configuration. All jobs are:

- **Atomic** — claim/execute/rollback pattern prevents duplicate execution
- **Resilient** — failed jobs stored in DLQ, retried automatically
- **Observable** — all execution logged with timing and outcomes

---

## System Architecture

### Scheduler Service

````python
from abby_core.services.scheduler import SchedulerService

scheduler = SchedulerService(
    tick_interval=60  # seconds
)

## Scheduler ticks every 60 seconds
## On each tick:
## 1. Query for jobs due to run (next_run_at <= now)
## 2. Attempt atomic claim (set status=CLAIMED, return if fails)
## 3. Execute job handler
## 4. On success: update next_run_at for next iteration
## 5. On failure: store in DLQ, increment retry_count
```python

### Schedule Types

```python
from abby_core.services.scheduler import ScheduleConfig

## Interval: Run every N seconds
ScheduleConfig(
    type="interval",
    interval_seconds=60
)

## Daily: Run at specific time
ScheduleConfig(
    type="daily",
    time_utc="14:00"  # 2 PM UTC
)

## Date-based: Run on specific date/time
ScheduleConfig(
    type="date_based",
    run_at="2026-02-01T14:00:00Z"
)
```python

---

## System Jobs (6 Core)

### 1. Heartbeat (1 min interval)

**Purpose:** Emit health signal to monitoring systems
**Owner:** `abby_core/services/scheduler.py`
**Schedule:** Every 60 seconds
**Duration:** < 100ms

```python
async def heartbeat_handler(scheduler: SchedulerService):
    """Emit scheduler heartbeat."""
    logger.info("Scheduler heartbeat", extra={
        "jobs_pending": len(await scheduler.get_pending_jobs()),
        "jobs_running": len(await scheduler.get_running_jobs()),
        "tick_id": scheduler.current_tick_id
    })
    # Used by monitoring to verify scheduler isn't stuck
```python

**Idempotency:** Safe to run multiple times (read-only operation)
**Failure Mode:** If heartbeat missing for > 2 ticks, escalate to CRITICAL

### 2. XP Streaming (Configurable, default 5 min)

**Purpose:** Process accumulated XP gains and stream to database
**Owner:** `abby_core/services/xp_service.py`
**Schedule:** Interval (default 300 seconds)
**Duration:** 100–500ms (depends on guild population)

```python
async def xp_streaming_handler(job_context: JobContext):
    """Flush accumulated XP to database."""
    # Pseudocode
    pending_xp = get_pending_xp_updates()

    for user_id, guild_id, xp_delta in pending_xp:
        await update_user_xp(user_id, guild_id, xp_delta)

    logger.info("XP streaming complete", extra={
        "updates_processed": len(pending_xp),
        "duration_ms": elapsed
    })
```python

**Idempotency:** Guaranteed. Each XP update is keyed by `(user_id, guild_id, timestamp)`. Re-running marks as processed again but doesn't double-apply XP.
**Failure Mode:** DLQ stores failed updates; retried on next job tick

### Configuration:
```python
## abby_core/config/base.py
xp_streaming_interval_seconds = 300  # Configurable
xp_batch_size = 100  # Updates per batch
```python

### 3. Giveaway Check (1 min interval)

**Purpose:** Check for expired giveaways and announce winners
**Owner:** `abby_core/discord/adapters/scheduler_bridge.py`
**Schedule:** Every 60 seconds
**Duration:** 50–200ms

```python
async def giveaway_check_handler(job_context: JobContext):
    """Check for giveaways past end_time."""
    active_giveaways = await db.giveaways.find({
        "end_time": {$lte: now()},
        "status": "ACTIVE"
    }).to_list(None)

    for giveaway in active_giveaways:
        winner_id = select_random_participant(giveaway)
        await announce_winner(giveaway, winner_id)
        await db.giveaways.update_one(
            {_id: giveaway._id},
            {$set: {status: "COMPLETED", winner_id}}
        )
```python

**Idempotency:** Job checks if giveaway already marked COMPLETED; skips if so.
**Failure Mode:** Giveaway stays ACTIVE, retried on next tick (max 3 retries)

### 4. Nudge Check (Configurable, default 10 min)

**Purpose:** Check if users haven't spoken in X hours, send nudge
**Owner:** `abby_core/discord/adapters/scheduler_bridge.py`
**Schedule:** Interval (default 600 seconds)
**Duration:** 200–1000ms (depends on idle users)

```python
async def nudge_check_handler(job_context: JobContext):
    """Send nudges to idle users."""
    idle_threshold_hours = get_config().nudge_idle_hours  # e.g., 24

    idle_users = await db.users.find({
        "last_message_at": {$lt: now() - timedelta(hours=idle_threshold_hours)},
        "nudge_sent_at": {$lt: now() - timedelta(days=7)}
    }).to_list(None)

    for user in idle_users:
        await send_nudge_message(user)
        await db.users.update_one(
            {_id: user._id},
            {$set: {nudge_sent_at: now()}}
        )
```python

**Idempotency:** Tracks `nudge_sent_at` per user; won't re-nudge for 7 days.
**Failure Mode:** If send fails, retried next tick

### Configuration:
```python
nudge_idle_hours = 24  # Send nudge if no activity
nudge_cooldown_days = 7  # Don't re-nudge for 7 days
nudge_enabled = True  # Feature flag
```python

### 5. Unified Content Dispatcher (1 min interval)

**Purpose:** Process content queue and deliver announcements
**Owner:** `abby_core/services/content_delivery_service.py`
**Schedule:** Every 60 seconds
**Duration:** 100–1000ms (depends on queue depth)

```python
async def unified_content_dispatcher_handler(job_context: JobContext):
    """Deliver queued content to users/channels."""
    pending_content = await db.content_queue.find({
        "status": "QUEUED",
        "scheduled_for": {$lte: now()}
    }).to_list(None)

    for content in pending_content:
        await deliver_to_channel(content)
        await db.content_queue.update_one(
            {_id: content._id},
            {$set: {status: "DELIVERED", delivered_at: now()}}
        )
```python

**Idempotency:** Status field prevents duplicate delivery. Re-running job skips already-DELIVERED content.
**Failure Mode:** Content stays QUEUED, retried on next tick

### Performance Baseline:

- Small batch (< 10 messages): < 200ms
- Large batch (100+ messages): < 1000ms
- Stuck > 2000ms: escalate to WARNING

### 6. DLQ Retry (Varies, typically 5 min)

**Purpose:** Retry failed operations from Dead Letter Queue
**Owner:** `abby_core/services/dlq_service.py`
**Schedule:** Interval (5 minutes)
**Duration:** 100–2000ms (depends on DLQ backlog)

```python
async def dlq_retry_handler(job_context: JobContext):
    """Retry failed operations from DLQ."""
    failed_ops = await db.dlq.find({
        "status": "PENDING",
        "next_retry_at": {$lte: now()},
        "retry_count": {$lt: 3}  # Max 3 retries
    }).to_list(None)

    for op in failed_ops:
        try:
            result = await retry_operation(op)
            await db.dlq.update_one(
                {_id: op._id},
                {$set: {status: "RESOLVED"}}
            )
        except Exception as e:
            await db.dlq.update_one(
                {_id: op._id},
                {
                    $set: {next_retry_at: now() + timedelta(minutes=5)},
                    $inc: {retry_count: 1}
                }
            )
```python

**Idempotency:** Retry operations are idempotent by design (state_transition retries check current state first).
**Failure Mode:** Moves to next retry window (exponential backoff)

### Retry Strategy:

- Attempt 1: Immediately (on first failure)
- Attempt 2: After 5 minutes
- Attempt 3: After 15 minutes
- After 3 failures: Move to archive

---

## Guild-Scoped Jobs

Guild-specific jobs are registered from configuration:

```python
## abby_core/config/base.py
GUILD_JOBS = {
    "guild_123456": [
        {
            "name": "weekly_summary",
            "handler": "generate_weekly_summary",
            "schedule": {"type": "weekly", "day": "monday", "time_utc": "09:00"}
        },
        {
            "name": "season_reset",
            "handler": "reset_xp_season",
            "schedule": {"type": "monthly", "day": 1, "time_utc": "00:00"}
        }
    ]
}
```python

### Guild Job Lifecycle:
```python

1. Configuration loaded at startup
2. Jobs registered in scheduler_jobs collection
3. On each tick, scheduler checks for guild jobs due
4. Same claim/execute/rollback pattern as system jobs
5. Failed guild jobs go to DLQ (shared with system jobs)
```python

---

## Scheduler Job Registry (MongoDB)

All jobs tracked in `scheduler_jobs` collection:

```json
{
    "_id": "ObjectId",
    "job_id": "heartbeat",
    "guild_id": null,
    "job_type": "SYSTEM",
    "schedule_type": "interval",
    "schedule_config": {
        "interval_seconds": 60
    },
    "status": "READY",
    "last_run_at": "2026-01-31T14:25:00Z",
    "last_error": null,
    "next_run_at": "2026-01-31T14:26:00Z",
    "error_count": 0,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-31T14:25:00Z"
}
```python

### Collection Indexes:
```python
db.scheduler_jobs.create_index("job_id", unique=True)
db.scheduler_jobs.create_index("status")
db.scheduler_jobs.create_index("next_run_at")
db.scheduler_jobs.create_index([("guild_id", 1), ("status", 1)])
```python

---

## Idempotency Guarantees

All jobs use atomic claiming to prevent duplicate execution:

```python
## Atomic claim operation (MongoDB)
result = await db.scheduler_jobs.find_one_and_update(
    {
        "job_id": "xp_streaming",
        "status": "READY",
        "next_run_at": {$lte: now()}
    },
    {
        $set: {status: "CLAIMED", last_run_at: now()}
    },
    return_document=ReturnDocument.AFTER
)

if result is None:
    # Another process claimed this job, skip
    return

try:
    # Execute job
    await xp_streaming_handler()

    # Mark success
    await db.scheduler_jobs.update_one(
        {job_id: "xp_streaming"},
        {$set: {
            status: "READY",
            next_run_at: calculate_next_run_at(),
            error_count: 0
        }}
    )
except Exception as e:
    # Mark failure (DLQ service will retry)
    await db.scheduler_jobs.update_one(
        {job_id: "xp_streaming"},
        {$set: {
            status: "FAILED",
            last_error: str(e)
        }, $inc: {error_count: 1}}
    )
    await dlq_service.enqueue_failed_job(...)
```python

---

## Error Handling & Retries

```python
Job Execution Flow:
│
├─ Tick #1 (60s): Attempt 1
│  └─ FAIL → Move to DLQ
│
├─ DLQ Service (async):
│  └─ Set next_retry_at = now + 5min
│
├─ Tick #N (65s+): Attempt 2 from DLQ
│  └─ FAIL → Set next_retry_at = now + 15min
│
└─ Tick #M (80s+): Attempt 3
   ├─ SUCCESS → Resolve
   └─ FAIL → Archive (no more retries)
```python

---

## Monitoring Scheduled Jobs

### Check Job Status

```python
from abby_core.database.client import MongoDB

db = MongoDB()

## Get all pending jobs
pending = await db.scheduler_jobs.find({
    "status": {"$in": ["READY", "CLAIMED"]}
}).to_list(None)

print(f"Pending jobs: {len(pending)}")

## Get overdue jobs (should have run but didn't)
overdue = await db.scheduler_jobs.find({
    "next_run_at": {$lt: now() - timedelta(minutes=5)},
    "status": "READY"
}).to_list(None)

if overdue:
    logger.warning(f"OVERDUE jobs detected: {len(overdue)}")
```python

### Watch Scheduler in Action

```bash
## Tail scheduler logs
tail -f logs/abby.jsonl | jq 'select(.logger | contains("scheduler"))'

## Expected output every 60s:
## Scheduler tick #1234 started
## Scheduler tick #1234 completed (3 jobs run, 0 failed)

## If tick stops appearing, scheduler is stuck
```python

---

## 50-Year Job Maintenance

### Annual Audits

- [ ] Review all job durations (baseline still valid?)
- [ ] Audit retry policies (max 3 retries still appropriate?)
- [ ] Check for stuck jobs in DLQ (manual intervention needed?)
- [ ] Verify guild jobs still registered correctly

### 5-Year Reviews

- [ ] Evaluate new job types based on feature development
- [ ] Consider distributed scheduler for multi-region deployments
- [ ] Migrate to managed job service (AWS SQS, Google Cloud Tasks)?
- [ ] Plan job schema evolution

### 10-Year Reviews

- [ ] Full scheduler redesign for new workloads
- [ ] Evaluate real-time event systems (Kafka, RabbitMQ) as alternative
- [ ] Plan global job distribution across data centers

---

## Related Documents

- [scheduler_bridge.py](../../abby_core/discord/adapters/scheduler_bridge.py) — How Discord adapters register jobs
- [../operations/OBSERVABILITY_RUNBOOK.md](../operations/OBSERVABILITY_RUNBOOK.md) — Monitor scheduler heartbeat and job timing
- [../operations/INCIDENT_RESPONSE.md](../operations/INCIDENT_RESPONSE.md) — Troubleshoot stuck scheduler
````
