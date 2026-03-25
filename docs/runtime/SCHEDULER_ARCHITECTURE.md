# Scheduler Architecture

**Owner:** Platform Team  
**Status:** ✅ Canonical (February 2, 2026)  
**Last Updated:** February 2, 2026

---

## Executive Summary

**SchedulerService is the canonical single scheduler for all background jobs across all platforms.**

The scheduler is platform-agnostic, runs on pure asyncio, and dispatches jobs to platform-specific handlers (Discord, web, CLI). This architecture ensures:

- **Single source of truth** for job scheduling
- **Platform independence** - works in Discord bots, web servers, CLI tools
- **Idempotent execution** - atomic job claiming prevents duplicate execution
- **Observable** - comprehensive logging and metrics
- **Resilient** - automatic retries with DLQ for failed jobs

---

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│              SchedulerService                           │
│  (abby_core/services/scheduler.py)                     │
│                                                          │
│  ┌────────────────────────────────────────────┐        │
│  │  Tick Loop (60s interval)                  │        │
│  │  ├── Phase 1: MongoDB system jobs          │        │
│  │  ├── Phase 2: Guild config jobs            │        │
│  │  └── Phase 3: Summary & metrics            │        │
│  └────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                        │
                        ├── Reads Jobs From
                        ▼
┌────────────────────────────────────┐  ┌──────────────────────┐
│  MongoDB: scheduler_jobs           │  │  Guild Configs       │
│  - System-level jobs               │  │  - Guild-specific    │
│  - Heartbeat, Bank Interest, etc.  │  │  - Daily posts, etc. │
└────────────────────────────────────┘  └──────────────────────┘
                        │
                        ├── Dispatches to Handlers
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Job Handlers                               │
│  (registered via scheduler.register_handler())          │
│                                                          │
│  ├── HeartbeatJobHandler                                │
│  ├── BankInterestJobHandler                             │
│  ├── GuildJobsTickHandler                               │
│  ├── AnnouncementGenerationHandler                      │
│  └── [Custom handlers...]                               │
└─────────────────────────────────────────────────────────┘
                        │
                        ├── Executes Platform Operations
                        ▼
┌─────────────────────────────────────────────────────────┐
│        Platform Adapters (I/O Layer)                    │
│                                                          │
│  ├── Discord Channels (message sending)                 │
│  ├── Web Webhooks (HTTP notifications)                  │
│  ├── CLI Output (stdout)                                │
│  └── Database Operations (data updates)                 │
└─────────────────────────────────────────────────────────┘
```

---

## How It Works

### 1. Tick-Based Execution Model

The scheduler runs a continuous loop with a configurable tick interval (default: 60 seconds):

```python
# From abby_core/services/scheduler.py

class SchedulerService:
    def __init__(self, tick_interval_seconds: int = 60):
        self.tick_interval = tick_interval_seconds

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            await self._tick()  # Process one tick
            await asyncio.sleep(self.tick_interval)
```

### 2. Two-Phase Job Processing

Each tick processes jobs from two sources:

#### Phase 1: MongoDB System Jobs

System-wide jobs stored in `scheduler_jobs` collection:

```python
# Example MongoDB job document
{
    "_id": ObjectId("..."),
    "job_type": "bank_interest",
    "enabled": true,
    "schedule": {
        "type": "interval",
        "every_minutes": 10
    },
    "last_run_at": ISODate("2026-02-02T10:00:00Z"),
    "next_run_at": ISODate("2026-02-02T10:10:00Z")
}
```

The scheduler:

1. Queries for jobs where `next_run_at <= now` and `enabled = true`
2. Attempts atomic claim (prevents duplicate execution)
3. Executes registered handler for `job_type`
4. Updates `last_run_at` and calculates new `next_run_at`

#### Phase 2: Guild Configuration Jobs

Guild-specific jobs from guild configuration documents:

```python
# Example guild config scheduling section
{
    "guild_id": "123456789",
    "scheduling": {
        "timezone": "America/Los_Angeles",
        "jobs": {
            "daily_announcement": {
                "enabled": true,
                "time": "09:00",
                "handler": "guild_daily_post"
            },
            "random_message": {
                "enabled": true,
                "schedule": "*/30 * * * *",  # Every 30 minutes
                "handler": "guild_random_post"
            }
        }
    }
}
```

The scheduler:

1. Fetches all guild configurations
2. Evaluates each guild's jobs in the guild's timezone
3. Executes jobs that are due
4. Tracks `last_run_at` per guild per job type

### 3. Job Handler Registration

Handlers are registered during bot startup:

```python
# From abby_core/discord/adapters/scheduler_bridge.py

def register_scheduler_jobs(bot):
    """Register all job handlers with SchedulerService."""
    scheduler = get_scheduler_service()

    # Register system handlers
    scheduler.register_handler("heartbeat", HeartbeatJobHandler(bot))
    scheduler.register_handler("bank_interest", BankInterestJobHandler(bot))
    scheduler.register_handler("guild_jobs_tick", GuildJobsTickHandler(bot))

    # Create default MongoDB jobs if they don't exist
    _ensure_job("heartbeat", every_minutes=1)
    _ensure_job("bank_interest", every_minutes=10)
    _ensure_job("guild_jobs_tick", every_minutes=1)
```

### 4. Atomic Job Claiming

To prevent duplicate execution in multi-instance deployments:

```python
async def _try_claim_job(self, job: Dict[str, Any]) -> bool:
    """Atomically claim a job for execution.

    Uses MongoDB compare-and-set to ensure only one instance claims the job.
    """
    db = get_database()
    result = db.scheduler_jobs.update_one(
        {
            "_id": job["_id"],
            "status": {"$ne": "CLAIMED"}  # Only claim if not already claimed
        },
        {
            "$set": {
                "status": "CLAIMED",
                "claimed_at": datetime.now(timezone.utc),
                "claimed_by": self._instance_id
            }
        }
    )
    return result.modified_count > 0
```

### 5. Schedule Types

The scheduler supports three schedule types:

#### Interval Schedules

Run every N minutes:

```python
{
    "schedule": {
        "type": "interval",
        "every_minutes": 10,
        "jitter_minutes": 2  # Optional random offset
    }
}
```

#### Daily Schedules

Run at a specific time each day:

```python
{
    "schedule": {
        "type": "daily",
        "time": "09:00",  # HH:MM in guild timezone
        "timezone": "America/Los_Angeles"
    }
}
```

#### Date-Based Schedules

Run once at a specific date/time:

```python
{
    "schedule": {
        "type": "date_based",
        "scheduled_date": "2026-12-25",
        "scheduled_time": "08:00",
        "timezone": "America/New_York"
    }
}
```

---

## Job Handler Interface

All handlers implement the `JobHandler` abstract base class:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class JobHandler(ABC):
    """Abstract base class for job handlers."""

    @abstractmethod
    async def execute(
        self,
        job_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the job.

        Args:
            job_config: Job configuration from MongoDB
            context: Execution context (guild_id, bot, etc.)

        Returns:
            Result dict with status and any output
        """
        pass
```

Example handler implementation:

```python
class BankInterestJobHandler(JobHandler):
    """Processes bank interest for all users."""

    def __init__(self, bot):
        self.bot = bot

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply interest to all bank accounts."""
        from abby_core.economy.banking import process_interest_cycle

        result = await process_interest_cycle()

        return {
            "status": "success",
            "accounts_processed": result["count"],
            "total_interest": result["total_interest"]
        }
```

---

## Observability

### Logging

The scheduler emits structured logs at multiple levels:

```python
# Tick-level logging (DEBUG)
logger.debug("[⏰] Scheduler tick at 2026-02-02 10:00:00 UTC")

# Job execution (INFO)
logger.info("[⏰] Executing job bank_interest", extra={
    "job_id": "...",
    "job_type": "bank_interest",
    "next_run_at": "2026-02-02T10:10:00Z"
})

# Summary logging (INFO - every 60 minutes)
logger.info("[⏰] Scheduler summary", extra={
    "ticks_processed": 60,
    "jobs_executed": 120,
    "errors": 0,
    "duration_minutes": 60
})

# Error logging (ERROR)
logger.error("[⏰] Job execution failed", extra={
    "job_id": "...",
    "job_type": "...",
    "error": "...",
    "retry_count": 1
}, exc_info=True)
```

### Metrics

The scheduler exposes metrics via `MetricsService`:

```python
from abby_core.services.metrics import get_metrics_service

metrics = get_metrics_service()

# Query scheduler metrics
scheduler_stats = await metrics.get_scheduler_stats()
# {
#     "jobs_pending": 5,
#     "jobs_running": 2,
#     "jobs_completed_last_hour": 120,
#     "jobs_failed_last_hour": 0,
#     "average_execution_time_ms": 45
# }
```

### Health Checks

Operator panel health check:

```python
from abby_core.services.scheduler import get_scheduler_service

scheduler = get_scheduler_service()
is_healthy = scheduler.is_running()
pending_jobs = await scheduler.get_pending_jobs()
```

---

## Failure Handling

### Dead Letter Queue (DLQ)

Failed jobs are automatically stored in the DLQ for investigation:

```python
# From abby_core/services/scheduler.py

async def _process_job(self, job: Dict[str, Any], utc_now: datetime):
    """Process a single job with DLQ fallback."""
    try:
        # Attempt execution
        result = await handler.execute(job, context)

        # On success, update next_run_at
        await self._update_next_run_at(job, utc_now)

    except Exception as e:
        # On failure, store in DLQ
        from abby_core.services.dlq import get_dlq_service
        dlq = get_dlq_service()

        await dlq.enqueue_item({
            "source": "scheduler",
            "job_id": job["_id"],
            "job_type": job["job_type"],
            "error": str(e),
            "retry_count": job.get("retry_count", 0) + 1
        })

        logger.error(f"[⏰] Job failed, stored in DLQ: {job['job_type']}")
```

### Automatic Retries

The scheduler implements exponential backoff for retries:

```python
retry_count = job.get("retry_count", 0)
if retry_count < 3:  # Max 3 retries
    delay_minutes = 2 ** retry_count  # 2, 4, 8 minutes
    next_run_at = utc_now + timedelta(minutes=delay_minutes)
else:
    # Disable job after 3 failures
    await db.scheduler_jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"enabled": False, "failure_reason": "max_retries_exceeded"}}
    )
```

---

## Usage Examples

### Creating a New System Job

```python
from abby_core.database.mongodb import get_database

db = get_database()
db.scheduler_jobs.insert_one({
    "job_type": "cleanup_expired_sessions",
    "enabled": True,
    "schedule": {
        "type": "interval",
        "every_minutes": 30
    },
    "last_run_at": None,
    "next_run_at": datetime.now(timezone.utc),
    "created_at": datetime.now(timezone.utc)
})
```

### Registering a Handler

```python
from abby_core.services.scheduler import get_scheduler_service, JobHandler

class CleanupHandler(JobHandler):
    async def execute(self, job_config, context):
        # Cleanup logic here
        return {"status": "success", "items_cleaned": 42}

scheduler = get_scheduler_service()
scheduler.register_handler("cleanup_expired_sessions", CleanupHandler())
```

### Adding a Guild Job

```python
from abby_core.database.collections.guild_configuration import update_guild_config

update_guild_config(guild_id, {
    "scheduling.jobs.daily_greeting": {
        "enabled": True,
        "time": "09:00",
        "handler": "guild_daily_post",
        "channel_id": "123456789"
    }
})
```

---

## Migration Notes

### ⚠️ Deprecated: Discord Scheduler Cog

The legacy Discord scheduler cog (`abby_core/discord/cogs/system/scheduler.py`) has been deprecated and is no longer loaded by the bot.

**Old Pattern (DEPRECATED):**

```python
# Discord.py @tasks.loop pattern - DO NOT USE
from discord.ext import tasks

@tasks.loop(minutes=10)
async def bank_update():
    await process_interest_cycle()

@bank_update.before_loop
async def wait_ready():
    await bot.wait_until_ready()
```

**New Pattern (CANONICAL):**

```python
# SchedulerService pattern - USE THIS
from abby_core.services.scheduler import get_scheduler_service, JobHandler

class BankInterestJobHandler(JobHandler):
    async def execute(self, job_config, context):
        return await process_interest_cycle()

scheduler = get_scheduler_service()
scheduler.register_handler("bank_interest", BankInterestJobHandler(bot))
```

### Benefits of SchedulerService

1. **Platform-agnostic** - Works outside Discord (web, CLI)
2. **Persistent state** - Jobs survive restarts
3. **Atomic execution** - No duplicate runs in multi-instance setups
4. **Unified observability** - All jobs logged in one place
5. **Flexible scheduling** - Interval, daily, date-based, cron-like
6. **Automatic retries** - DLQ integration for failed jobs

---

## Testing

### Unit Tests

```python
# tests/test_scheduler_service.py
import pytest
from abby_core.services.scheduler import SchedulerService, JobHandler

class TestJobHandler(JobHandler):
    async def execute(self, job_config, context):
        return {"status": "success"}

@pytest.mark.asyncio
async def test_job_execution():
    scheduler = SchedulerService(tick_interval_seconds=1)
    scheduler.register_handler("test_job", TestJobHandler())

    # Create test job
    db = get_database()
    db.scheduler_jobs.insert_one({
        "job_type": "test_job",
        "enabled": True,
        "schedule": {"type": "interval", "every_minutes": 1},
        "next_run_at": datetime.now(timezone.utc)
    })

    # Run one tick
    await scheduler._tick()

    # Verify job executed
    # ... assertions ...
```

### Integration Tests

See [tests/test_scheduler_idempotency.py](../../tests/test_scheduler_idempotency.py) for comprehensive integration tests including:

- Atomic job claiming across multiple instances
- Duplicate execution prevention
- Failure recovery and DLQ integration

---

## Performance Considerations

### Tick Interval

The default 60-second tick interval balances responsiveness with system load:

```python
# Default configuration
scheduler = SchedulerService(tick_interval_seconds=60)

# For high-frequency jobs, reduce tick interval
scheduler = SchedulerService(tick_interval_seconds=30)  # 30-second ticks
```

**Recommendation:** Keep tick interval ≥ 30 seconds unless you have sub-minute job requirements.

### Job Execution Time

Jobs should complete within the tick interval to prevent backup:

- **Target:** Jobs complete in < 30 seconds
- **Warning threshold:** 30 seconds (logged automatically)
- **Critical threshold:** 60 seconds (consider breaking into smaller jobs)

Long-running jobs should:

1. Use background tasks (asyncio.create_task)
2. Update progress markers in MongoDB
3. Support cancellation/resume

### MongoDB Queries

The scheduler optimizes MongoDB queries:

```python
# Efficient query with index on next_run_at
jobs = db.scheduler_jobs.find({
    "enabled": True,
    "next_run_at": {"$lte": utc_now}
}).hint("next_run_at_1")  # Use index
```

Recommended indexes:

```python
db.scheduler_jobs.create_index("next_run_at")
db.scheduler_jobs.create_index([("enabled", 1), ("next_run_at", 1)])
```

---

## Configuration

### Environment Variables

```bash
# Scheduler configuration
ABBY_SCHEDULER_TICK_INTERVAL=60          # Tick interval in seconds
ABBY_SCHEDULER_VERBOSE=false             # Enable verbose logging
ABBY_SCHEDULER_SUMMARY_INTERVAL_MINUTES=60  # Summary log interval
```

### MongoDB Collections

The scheduler uses these collections:

1. **scheduler_jobs** - System-level job definitions
2. **guild_configurations** - Guild-specific job schedules
3. **dlq_items** - Failed jobs for retry/investigation

---

## Troubleshooting

### Scheduler Not Running

Check if scheduler is started:

```python
from abby_core.services.scheduler import get_scheduler_service

scheduler = get_scheduler_service()
if not scheduler.is_running():
    await scheduler.start()
```

### Jobs Not Executing

1. **Check job is enabled:**

   ```python
   db.scheduler_jobs.find_one({"job_type": "my_job", "enabled": True})
   ```

2. **Check next_run_at:**

   ```python
   job = db.scheduler_jobs.find_one({"job_type": "my_job"})
   print(f"Next run: {job['next_run_at']}")
   ```

3. **Check handler is registered:**
   ```python
   scheduler = get_scheduler_service()
   print(f"Registered handlers: {list(scheduler.handlers.keys())}")
   ```

### High Execution Time

Check scheduler metrics for slow jobs:

```python
from abby_core.services.metrics import get_metrics_service

metrics = get_metrics_service()
slow_jobs = await metrics.get_slow_jobs(threshold_seconds=30)
```

Consider splitting slow jobs into smaller chunks or background tasks.

---

## References

- **Implementation:** [abby_core/services/scheduler.py](../../abby_core/services/scheduler.py)
- **Job Handlers:** [abby_core/discord/adapters/scheduler_bridge.py](../../abby_core/discord/adapters/scheduler_bridge.py)
- **Job Catalog:** [SCHEDULER_JOBS_CATALOG.md](SCHEDULER_JOBS_CATALOG.md)
- **Tests:** [tests/test_scheduler_idempotency.py](../../tests/test_scheduler_idempotency.py)
- **DLQ Integration:** [../operations/OBSERVABILITY_RUNBOOK.md](../operations/OBSERVABILITY_RUNBOOK.md)

---

## Change Log

- **2026-02-02:** ✅ Declared SchedulerService as canonical, deprecated Discord scheduler cog
- **2026-01-31:** Added guild configuration job processing
- **2026-01-30:** Implemented atomic job claiming and DLQ integration
- **2026-01-28:** Initial scheduler service implementation
