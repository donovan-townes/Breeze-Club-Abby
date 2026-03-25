# Heartbeat Architecture

## Overview

The **UnifiedHeartbeatService** consolidates all platform heartbeat emissions into a single, observable service. This eliminates fragmented heartbeat logic across multiple files and independent legacy timers.

## Problem Statement (Before Consolidation)

### Fragmented Heartbeat Sources

Prior to consolidation, heartbeat emissions were scattered across:

1. **`main.py`** - Legacy heartbeat loop (removed)
   - Emitted TDOS platform metrics every 60 seconds
   - Had its own timing loop (violated platform-agnostic architecture)
   - Duplicated emission logic

1. **`scheduler_bridge.py`** - HeartbeatJobHandler
   - Emitted SAME metrics via platform scheduler
   - Created duplicate emissions (both main.py AND scheduler firing)

1. **`scheduler_heartbeat.py`** - SchedulerHeartbeatService
   - Tracked announcement-specific metrics separately
   - Not integrated with platform heartbeat

### Architectural Problems

- ❌ **Duplicate Emissions**: Both main.py loop and scheduler job emitting every minute
- ❌ **Fragmented Logic**: Heartbeat code scattered across 3+ files
- ❌ **No Central Orchestrator**: No single source of truth
- ❌ **Observability Gap**: Hard to track which heartbeats are emitting and when
- ❌ **Platform Violation**: Legacy main.py loop violated platform-agnostic design

## Solution: Unified Heartbeat Service

### Architecture

````python
┌─────────────────────────────────────────────────────────┐
│  Platform Scheduler (60s tick)                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  HeartbeatJobHandler                            │    │
│  │  - Collects metrics from platform services      │    │
│  │  - Calls UnifiedHeartbeatService methods       │    │
│  └────────────────┬───────────────────────────────┘    │
└───────────────────┼────────────────────────────────────┘
                    │
                    ▼
      ┌─────────────────────────────────┐
      │  UnifiedHeartbeatService        │
      │  ┌──────────────────────────┐   │
      │  │ Platform Heartbeat       │   │ → TDOS Telemetry
      │  │ - Uptime, sessions       │   │
      │  │ - Submissions, latency   │   │
      │  └──────────────────────────┘   │
      │  ┌──────────────────────────┐   │
      │  │ Scheduler Heartbeat      │   │ → TDOS Telemetry
      │  │ - Announcement health    │   │
      │  │ - Success/failure rates  │   │
      │  └──────────────────────────┘   │
      │  ┌──────────────────────────┐   │
      │  │ Discord Heartbeat        │   │ → TDOS Telemetry
      │  │ - Guild/member counts    │   │
      │  │ - Voice connections      │   │
      │  └──────────────────────────┘   │
      └─────────────────────────────────┘
```python

### Key Components

#### 1. **UnifiedHeartbeatService** (`abby_core/services/heartbeat_service.py`)

### Responsibilities:

- Central orchestrator for ALL heartbeat types
- Manages emission intervals and configurations
- Tracks emission counts and last emission times
- Provides metric collection hooks

### Heartbeat Types:

| Type | Interval | Metrics |
| ------------- | -------- | ------------------------------------------------------------------------- |
| **Platform** | 60s | Uptime, active sessions, pending submissions, MongoDB health, LLM latency |
| **Scheduler** | 60s | Announcement success/failure rates, active guilds, recovery attempts |
| **Discord** | 60s | Guild count, member count, voice connections, command usage |
| **LLM** | 300s | Provider health, model latency, token usage |

### Key Methods:

```python
## Emit specific heartbeat types
await service.emit_platform_heartbeat(uptime, sessions, submissions, latency)
await service.emit_scheduler_heartbeat(health, guilds, sent, failed)
await service.emit_discord_heartbeat(guilds, members, voice)

## Emit all due heartbeats (called by scheduler tick)
await service.emit_all_due()

## Register custom metric collectors
service.register_collector(HeartbeatType.PLATFORM, lambda: {"custom_metric": 42})

## Configure intervals
service.configure(HeartbeatType.LLM, interval_seconds=600)  # Change to 10 min
```python

#### 2. **HeartbeatJobHandler** (`abby_core/discord/adapters/scheduler_bridge.py`)

### Responsibilities:

- Platform scheduler integration point
- Collects metrics from Discord bot and platform services
- Calls UnifiedHeartbeatService emission methods
- Runs every 60 seconds via platform scheduler (NOT independent loop)

### Metrics Collected:

```python
## Platform metrics

- uptime_seconds: Time since bot startup
- active_sessions: Active conversation states
- pending_submissions: Queued/retry announcements
- ollama_latency_ms: Ollama API health check

## Discord metrics

- guild_count: Number of guilds bot is in
- total_members: Total member count across guilds
- voice_connections: Active voice/streaming connections

## Scheduler metrics

- health_status: healthy/degraded/unhealthy
- active_guilds: Guilds with active announcement configs
- announcements_sent_hour: Successful announcements (last 60 min)
- announcements_failed_hour: Failed announcements (last 60 min)
```python

#### 3. **SchedulerHeartbeatService** (`abby_core/services/scheduler_heartbeat.py`)

### Responsibilities:

- Tracks announcement-specific health metrics
- Records success/failure events
- Calculates scheduler health status
- Provides heartbeat snapshot data to UnifiedHeartbeatService

**Note**: This service is now a **data provider** for UnifiedHeartbeatService, not an independent emitter.

## Benefits

### 1. **Single Source of Truth**

- All heartbeats run via platform scheduler
- No duplicate emissions
- Easy to audit when heartbeats fire

### 2. **Improved Observability**

- Centralized emission tracking
- Emission counts and timing statistics
- Easy to debug heartbeat issues

### 3. **Platform-Agnostic Architecture**

- No legacy heartbeat loops in main.py
- SchedulerService drives all time-based operations
- Consistent with scheduler consolidation pattern

### 4. **Flexible Configuration**

- Per-heartbeat interval configuration
- Enable/disable specific heartbeat types
- Custom metric collectors via registration

### 5. **Better Testing**

- Single service to mock for tests
- No background loops to manage
- Clear emission contract

## Migration Guide

### Removed Code

#### `main.py` - Removed Legacy Heartbeat Loop

**Why**: This loop duplicated the HeartbeatJobHandler running via SchedulerService. Both were emitting every 60 seconds, causing duplicate telemetry.

**Kept**: The initial heartbeat emission during bot startup remains:

```python
## ✅ KEPT: Initial startup heartbeat
emit_heartbeat(
    uptime_seconds=0,
    active_sessions=0,
    pending_submissions=0,
)
```python

#### `scheduler_bridge.py` - Updated to Use UnifiedHeartbeatService

### Before:

```python
## ❌ OLD: Direct emit_heartbeat() calls
emit_heartbeat(
    uptime_seconds=uptime,
    active_sessions=active_sessions,
    pending_submissions=pending_submissions,
    ollama_latency_ms=ollama_latency_ms,
)
```python

### After:

```python
## ✅ NEW: Via UnifiedHeartbeatService
await self.unified_heartbeat.emit_platform_heartbeat(
    uptime_seconds=uptime,
    active_sessions=active_sessions,
    pending_submissions=pending_submissions,
    ollama_latency_ms=ollama_latency_ms,
)
```python

### Adding New Heartbeat Types

To add a new heartbeat type (e.g., database health):

1. **Add enum to `heartbeat_service.py`**:

```python
class HeartbeatType(Enum):
    PLATFORM = "platform"
    SCHEDULER = "scheduler"
    DISCORD = "discord"
    LLM = "llm"
    DATABASE = "database"  # New type
```python

1. **Add config in `__init__`**:

```python
self.configs: Dict[HeartbeatType, HeartbeatConfig] = {
    # ... existing configs ...
    HeartbeatType.DATABASE: HeartbeatConfig(interval_seconds=120),  # 2 min
}
```python

1. **Add emission method**:

```python
async def emit_database_heartbeat(
    self,
    connection_pool_size: int,
    query_latency_ms: int,
    active_transactions: int,
) -> Dict[str, Any]:
    """Emit database health heartbeat."""
    if not self.should_emit(HeartbeatType.DATABASE):
        return {}

    payload = {
        "heartbeat_type": "database",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connection_pool_size": connection_pool_size,
        "query_latency_ms": query_latency_ms,
        "active_transactions": active_transactions,
    }

    # Emit via telemetry
    from abby_core.observability.telemetry import emit_event
    emit_event("DATABASE_HEARTBEAT", payload)

    # Update config
    config = self.configs[HeartbeatType.DATABASE]
    config.last_emission = datetime.now(timezone.utc)
    config.emission_count += 1

    return payload
```python

1. **Call from HeartbeatJobHandler**:

```python
async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]):
    # ... existing emissions ...

    # Emit database heartbeat
    if self.should_emit(HeartbeatType.DATABASE):
        # Collect database metrics
        pool_size = await get_db_pool_size()
        latency = await measure_db_latency()
        transactions = await get_active_transactions()

        await self.unified_heartbeat.emit_database_heartbeat(
            connection_pool_size=pool_size,
            query_latency_ms=latency,
            active_transactions=transactions,
        )
```python

### Testing

```python
import pytest
from abby_core.services.heartbeat_service import (
    get_heartbeat_service,
    reset_heartbeat_service,
    HeartbeatType,
)

@pytest.fixture
def heartbeat_service():
    """Provide clean heartbeat service instance."""
    reset_heartbeat_service()
    return get_heartbeat_service()

async def test_platform_heartbeat_emission(heartbeat_service):
    """Test platform heartbeat emission."""
    payload = await heartbeat_service.emit_platform_heartbeat(
        uptime_seconds=3600,
        active_sessions=5,
        pending_submissions=2,
        ollama_latency_ms=150,
    )

    assert payload["heartbeat_type"] == "platform"
    assert payload["uptime_seconds"] == 3600
    assert payload["active_sessions"] == 5

async def test_heartbeat_interval_gating(heartbeat_service):
    """Test that heartbeats respect intervals."""
    # Configure 5 second interval
    heartbeat_service.configure(HeartbeatType.PLATFORM, interval_seconds=5)

    # First emission should succeed
    await heartbeat_service.emit_platform_heartbeat(uptime_seconds=0)

    # Second emission immediately should be gated
    assert not heartbeat_service.should_emit(HeartbeatType.PLATFORM)

    # After interval, should emit
    await asyncio.sleep(5)
    assert heartbeat_service.should_emit(HeartbeatType.PLATFORM)
```python

## Monitoring & Debugging

### Check Emission Statistics

```python
from abby_core.services.heartbeat_service import get_heartbeat_service

service = get_heartbeat_service()
stats = service.get_statistics()

print(stats)
## {
##   "platform": {
##     "enabled": true,
##     "interval_seconds": 60,
##     "emission_count": 245,
##     "last_emission": "2024-12-20T12:34:56.789Z"
##   },
##   "scheduler": { ... },
##   "discord": { ... }
## }
```python

### Logs to Watch

```python
[❤️ Unified Heartbeat] Emitted all heartbeats
  extra: {
    "uptime_seconds": 3600,
    "active_sessions": 12,
    "scheduler_health": "healthy"
  }
```python

### Common Issues

#### Issue: Heartbeats not firing

### Diagnosis:

```python
## Check if scheduler is running
from abby_core.services.scheduler import get_scheduler_service
scheduler = get_scheduler_service()
print(f"Scheduler running: {scheduler._running}")

## Check if HeartbeatJobHandler is registered
from abby_core.discord.adapters.scheduler_bridge import JOB_HANDLERS
print("heartbeat" in JOB_HANDLERS)  # Should be True
```python

**Solution**: Ensure SchedulerService is started and HeartbeatJobHandler is registered in scheduler bridge.

#### Issue: Duplicate heartbeat emissions

**Diagnosis**:

```bash
## Search for legacy heartbeat timers
grep -r "heartbeat" abby_core/ | grep -i "loop"

## Should return NO results after consolidation
```python

**Solution**: Remove any remaining legacy heartbeat timers. All heartbeats should run via HeartbeatJobHandler.

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Overall platform architecture
- [../runtime/SCHEDULER_ARCHITECTURE.md](../runtime/SCHEDULER_ARCHITECTURE.md) - Unified scheduler pattern (same consolidation approach)
- [../runtime/GENERATION_PIPELINE.md](../runtime/GENERATION_PIPELINE.md) - Content lifecycle with delivery states

## Future Improvements

### 1. **Adaptive Intervals**

- Adjust heartbeat frequency based on system load
- More frequent during high activity, less during idle

### 2. **Health Score Aggregation**

- Combine platform, scheduler, and Discord health into unified score
- Alert on degraded health across multiple dimensions

### 3. **Metric Collectors**

- Standardized collector interface for custom metrics
- Plugin system for third-party integrations

### 4. **Historical Tracking**

- Store heartbeat snapshots for trend analysis
- Anomaly detection on metric drift

## Changelog

### 2024-12-20 - Initial Consolidation

### Removed:

- `main.py` legacy heartbeat loop (removed)
- `main.py` before_heartbeat_task hook
- Duplicate emit_heartbeat() calls in scheduler_bridge

### Added:

- `abby_core/services/heartbeat_service.py` - UnifiedHeartbeatService
- HeartbeatType enum (platform, scheduler, discord, llm)
- HeartbeatConfig dataclass for per-type configuration
- Metric collector registration system

### Updated:

- `scheduler_bridge.py` HeartbeatJobHandler to use UnifiedHeartbeatService
- Consolidated all three heartbeat types (platform, scheduler, discord) into single handler

### Benefits:

- ✅ Eliminated duplicate heartbeat emissions
- ✅ Single source of truth via platform scheduler
- ✅ Improved observability and debugging
- ✅ Consistent with scheduler consolidation pattern
````
