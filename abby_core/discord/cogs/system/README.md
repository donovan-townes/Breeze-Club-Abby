# Guild Job Scheduling (SchedulerService)

**Status:** ✅ Canonical (February 2, 2026)  
**Primary Documentation:** [docs/SCHEDULER_ARCHITECTURE.md](../../../docs/SCHEDULER_ARCHITECTURE.md)

## Overview

SchedulerService is the **canonical platform-wide scheduler** for all time-based jobs (system-level and guild-scoped). It replaces legacy Discord-specific @tasks.loop patterns and provides a unified, deterministic execution model.

## Architecture

````python
Discord Bot
└── SchedulerService (services/scheduler.py)
  ├── Wakes every minute
  ├── Runs GuildJobsTickHandler (scheduler_bridge.py)
  ├── Iterates all guild configs
  ├── Evaluates jobs (enabled, time match, not already run)
  ├── Dispatches to registered handlers
  └── Tracks last_run_at (idempotent)
```python

## Key Components

### 1. SchedulerService (`services/scheduler.py`)

- **Single responsibility**: Time-based job evaluation and dispatch via GuildJobsTickHandler
- **Guild-scoped**: Each guild has independent job registry
- **Deterministic**: No race conditions, no duplicate runs
- **Lightweight**: No game logic, no Discord UI

### 2. Job Registry (`scheduling.jobs.*` in guild config)

```json
{
  "scheduling": {
    "timezone": "US/Eastern",
    "jobs": {
      "games": {
        "emoji": {
          "enabled": true,
          "time": "20:00",
          "duration_minutes": 5,
          "last_run_at": "2026-01-20"
        }
      },
      "motd": {
        "enabled": true,
        "time": "08:00",
        "last_run_at": "2026-01-20"
      }
    }
  }
}
```python

### 3. Job Handlers (`job_handlers.py`)

- **Explicit registration**: Via `@register_job_handler(job_type)` decorator
- **Clear contract**: `async def handler(bot, guild_id, job_config)`
- **Responsible for**: Job execution + updating `last_run_at`
- **Error handling**: Handlers catch their own errors (don't propagate to scheduler)

## Job Contract

Every job must satisfy:

```python
{
  "enabled": bool,        # Feature enabled
  "time": "HH:MM",        # Scheduled time (guild timezone)
  "last_run_at": "YYYY-MM-DD",  # Last execution date (idempotency)
  # ... job-specific fields
}
```python

## Job Evaluation Logic

```python
def should_run_job(job, now, timezone_str):
    if not job.enabled:
        return False

    if job.time != now.strftime("%H:%M"):
        return False

    if job.last_run_at == today(now):
        return False

    return True
```python

## Adding a New Scheduled Job

1. **Add job config** to guild config schema:

   ```python
   scheduling.jobs.{category}.{job_type}
````

1. **Register handler** in `job_handlers.py`:

   ```python
   @register_job_handler("my_job")
   async def handle_my_job(bot, guild_id, job_config):
       # Execute job
       # Update last_run_at
       pass
   ```

1. **Add UI** in guild_config panels to configure the job

1. **Done** - scheduler automatically picks it up

## Migration Path

### Current State

- ✅ Emoji game: Uses new jobs structure (`scheduling.jobs.games.emoji`)
- ⚠️ MOTD: Still uses legacy structure (`scheduling.motd`)
- ⚠️ Old scheduler: `auto_game_task` in games.py still runs (deprecated)

### Migration Steps

1. **Coexistence**: New scheduler + old loops both check `features.*` flags
2. **Per-guild migration**: Gradually move guilds to new structure
3. **Legacy fallback**: Code reads from `jobs.*` first, falls back to legacy
4. **Final cleanup**: Remove any remaining legacy loop code once all guilds migrated

## Benefits

### For Development

- **Single source of truth** for time-based execution
- **Easy to add jobs**: Register handler + add config
- **No duplicate logic**: Idempotency, timezone handling, time matching centralized
- **Clear boundaries**: Scheduler evaluates time, handlers execute jobs

### For Operations

- **Idempotent**: Can't accidentally run same job twice
- **Observable**: Single place to log/debug scheduled execution
- **Guild-scoped**: Each guild independent, no cross-contamination
- **Deterministic**: No race conditions between multiple schedulers

### For Architecture

- **Kernel behavior**: Scheduling is infrastructure, not feature logic
- **Declarative jobs**: Config declares what/when, handlers do how
- **Extensible**: Add new job types without touching scheduler core
- **TDOS-aligned**: Guild-local execution plans, idempotent records

## Files

- `scheduler.py` - Core scheduler cog
- `job_handlers.py` - Handler registration and implementations
- `__init__.py` - Package init

## Usage Example

````python
## In guild_config.py - UI to enable job
set_guild_config(
    guild_id,
    {"scheduling": {"jobs": {"games": {"emoji": {"enabled": True}}}}}
)

## In job_handlers.py - Handler registration
@register_job_handler("emoji")
async def handle_emoji_game(bot, guild_id, job_config):
    # Get channel, start game, update last_run_at
    pass

## Scheduler automatically:
## 1. Reads scheduling.jobs.games.emoji from config
## 2. Evaluates if job should run (time match, not run today)
## 3. Dispatches to handle_emoji_game()
## 4. Handler updates last_run_at
```python

## Future Work

- [ ] Migrate MOTD to jobs structure (`scheduling.jobs.motd`)
- [ ] Remove deprecated `auto_game_task` loop
- [ ] Add backoff/retry semantics for failed jobs
- [ ] Add job execution history/audit trail
- [ ] Support interval-based jobs (not just daily time-based)
- [ ] Add job execution metrics to observability

## Testing

To test the scheduler:

1. Set a job time to current time + 1 minute
2. Watch logs for scheduler tick
3. Verify job dispatched at correct time
4. Verify `last_run_at` updated
5. Verify job doesn't run again until next day

## Logs

```python
[⏰] Centralized scheduler initialized
[⏰] Scheduler ready - beginning tick cycle
[⏰] Scheduler tick at 2026-01-20 14:30:00 UTC
[⏰] Dispatching job 'emoji' for guild 12345 at 20:00 US/Eastern
[🎮] Starting scheduled emoji game in guild 12345, duration 5m
```python

## Notes

- Scheduler runs every 1 minute (adjust SchedulerService tick if needed)
- Jobs evaluate in guild timezone (from `scheduling.timezone`)
- `last_run_at` prevents duplicate execution within same day
- Handlers are responsible for updating `last_run_at`
- Failed handlers don't crash scheduler (errors logged)
````
