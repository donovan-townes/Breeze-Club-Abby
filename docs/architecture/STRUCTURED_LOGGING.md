# Structured Logging Architecture

## Overview

Abby now uses **dual-output structured logging** for long-term observability and telemetry:

- **Console/Text Log**: Human-readable with colors and emojis (`logs/abby.log`)
- **JSONL Log**: Machine-parseable structured data (`logs/abby.jsonl`)

This aligns with TDOS event emission patterns for consistent observability across systems.

## Architecture

### Dual Output System

```
Logger Call
    ├─> Console Handler (human, colored)
    ├─> Text File Handler (human, utf-8)
    └─> JSONL Handler (machine, structured)
```

### JSONL Schema

Each log entry in `abby.jsonl` follows this structure:

```json
{
  "timestamp": "2026-01-01T23:18:43.433000+00:00",
  "level": "INFO",
  "logger": "Main",
  "message": "Core services initialized",
  "module": "main",
  "function": "__init__",
  "line": 45,
  "phase": "CORE_SERVICES",
  "metrics": {
    "cog_count": 28,
    "command_count": 89,
    "startup_duration_seconds": 0.5
  }
}
```

### Startup Phases

Startup is organized into **6 distinct phases** for clear tracking:

1. **INIT** - Bot initialization
2. **CORE_SERVICES** - Storage, image generation, LLM client
3. **COG_LOADING** - Dynamic cog discovery and loading
4. **CONNECTION** - Discord gateway connection
5. **BACKGROUND_TASKS** - Scheduled tasks (MOTD, XP, etc.)
6. **COMPLETE** - Final summary with metrics

## Usage

### Basic Logging

Use standard Python logging as before:

```python
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

logger.info("Normal log message")
logger.debug("Debug information")
logger.error("Error occurred")
```

### Phase-Based Logging

For startup events, use phase markers:

```python
from abby_core.observability.logging import log_startup_phase, STARTUP_PHASES

log_startup_phase(
    logger,
    STARTUP_PHASES["CORE_SERVICES"],
    "[🐰] Storage initialized"
)
```

### Logging with Metrics

Add structured metrics to log entries:

```python
log_startup_phase(
    logger,
    STARTUP_PHASES["COMPLETE"],
    "[🐰] Startup complete",
    metrics={
        "cog_count": 28,
        "command_count": 89,
        "startup_duration_seconds": 0.5
    }
)
```

## Frontend Integration

### Parsing JSONL Logs

```python
import json

def parse_abby_logs(log_file_path):
    """Parse Abby JSONL logs for telemetry."""
    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            yield entry

# Get all startup events
startup_events = [
    e for e in parse_abby_logs('logs/abby.jsonl')
    if e.get('phase') == 'COMPLETE'
]
```

### Querying Startup Metrics

```python
# Get latest startup duration
latest_startup = startup_events[-1]
duration = latest_startup['metrics']['startup_duration_seconds']
print(f"Last startup: {duration}s")

# Get average startup time
durations = [e['metrics']['startup_duration_seconds'] for e in startup_events]
avg_duration = sum(durations) / len(durations)
print(f"Average startup: {avg_duration:.2f}s")
```

### Dashboard Metrics

Key metrics available in JSONL logs:

- `startup_duration_seconds` - Total init to ready time
- `cog_count` - Number of loaded cogs
- `command_count` - Number of registered commands
- `guild_count` - Number of connected guilds

## Benefits

### For Developers

- Human-readable console output during development
- Structured data for debugging and analysis
- Phase markers show exactly where slowdowns occur

### For Operations

- Machine-parseable JSONL for log aggregation (ELK, Splunk, etc.)
- Consistent schema across all Abby logs
- Aligns with TDOS event standards

### For Analytics

- Track startup performance over time
- Identify slow initialization phases
- Monitor cog loading issues
- Measure resource usage trends

## Log Rotation

**Recommended**: Use log rotation to manage file sizes:

```bash
# Linux logrotate config
/opt/tdos/apps/abby/logs/abby.jsonl {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

## Migration Notes

### Before (Verbose)

```
[INFO] - Quota manager initialized
[INFO] -     Global limit: 5000MB
[INFO] -     Per-user limit: 500MB
[INFO] - Storage manager initialized
[INFO] -     Root: C:\path\to\storage
[INFO] - StorageManager initialized successfully
```

### After (Consolidated)

```
Console:
[INFO] - [🐰] Core services initialized (storage: C:\path\to\storage, ...)

JSONL:
{"timestamp": "...", "phase": "CORE_SERVICES", "message": "Core services initialized", ...}
```

## Future Enhancements

- [ ] Add log levels to JSONL (DEBUG, INFO, WARNING, ERROR)
- [ ] Emit startup phases as TDOS events for cross-system monitoring
- [ ] Add memory usage metrics to startup complete
- [ ] Create real-time log streaming endpoint
- [ ] Build Grafana dashboard for startup metrics
