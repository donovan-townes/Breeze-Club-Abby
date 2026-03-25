# Startup Logging Architecture

> **Design Goal**: Clean, actionable startup logs that make sense for operators maintaining this system over 10-20 years.

## Philosophy

### Logging Levels (Operator Perspective)

- **INFO** - What happened (phase completions, counts, health checks)
- **DEBUG** - How it happened (component initialization, registration)
- **TRACE** (env var) - Everything (individual file loads, internal state dumps)
- **WARNING** - Expected issues (optional components missing, fallbacks engaged)
- **ERROR** - Unexpected failures requiring attention

### Third-Party Library Suppression

Even in DEBUG mode, these libraries are suppressed to WARNING:

- `pymongo.*` - Connection pooling noise
- `urllib3.*` - HTTP connection chatter
- `discord.*` - Gateway frame spam
- `asyncio` - Event loop internals

**Rationale**: Operators debug _our_ code, not dependencies. Library issues surface as errors.

## Startup Phases

```
1. Core Services (0.0s)    → Storage, Image Gen initialization
2. MongoDB (1.1s)           → 37 collections initialized
3. Scheduler (0.0s)         → Platform scheduler operational
4. Cogs (4.2s)              → 33 cogs loaded across 7 categories
5. Connection (3.0s)        → Discord Gateway connected
6. Complete (9.0s)          → Final health summary
```

### Phase Logging Pattern

**INFO Level** (always visible):

```json
{"level": "INFO", "phase": "Core Services", "message": "[🐰] Initializing core services..."}
{"level": "INFO", "phase": "Cogs", "message": "[🐰] Loaded 33 cogs across 7 categories"}
{"level": "INFO", "phase": "Complete", "message": "[✓] System operational - 33 cogs, 27 commands"}
```

**DEBUG Level** (--dev mode):

```json
{"level": "DEBUG", "message": "[💾] Storage manager initialized (root: shared, cleanup: 7d)"}
{"level": "DEBUG", "message": "  • admin: 10 cog(s)"}
{"level": "DEBUG", "message": "[🤖] Guild Assistant loaded"}
```

**TRACE Level** (TRACE=1 env var):

```json
{"level": "DEBUG", "message": "[🐰] Loading admin/canon..."}
{"level": "DEBUG", "message": "[🐰] Loading admin/guild_assistant..."}
```

## Component Startup Contracts

### Cogs

- **Load-time**: Silent or single DEBUG log in `__init__`
- **Setup-time**: Single DEBUG log in `setup()` function
- **NO**: Individual file load announcements (use TRACE)
- **NO**: Configuration dumps in DEBUG (only counts/summaries)

### Services

- **Initialization**: Single DEBUG with key config summary
- **Registration**: Single INFO for phase completion
- **NO**: Per-item registration (consolidate to summary)

### Databases/Collections

- **Connection**: Single INFO with success/failure
- **Collections**: Single INFO with total count
- **NO**: Per-collection initialization logs
- **NO**: Repeated database name checks (log once)

## Debugging Modes

### Standard Startup (INFO)

```bash
python launch.py
```

Shows: Phases, counts, health checks, errors only

### Debug Mode (DEBUG)

```bash
python launch.py --dev
```

Shows: All of INFO + component initializations, summaries

### Trace Mode (DEBUG + individual loads)

```bash
TRACE=1 python launch.py --dev
```

Shows: All of DEBUG + individual file loads, full state dumps

## Anti-Patterns (What NOT to do)

### ❌ Logging Every File Load

```python
# BAD - floods DEBUG logs
logger.debug(f"Loading {filename}...")
```

```python
# GOOD - summary only
logger.info(f"Loaded {count} files")
```

### ❌ Dumping Full Configuration

```python
# BAD - walls of text
logger.debug(f"Config: {full_config_dict}")
```

```python
# GOOD - key metrics only
logger.debug(f"Config loaded: {len(items)} items, mode={mode}")
```

### ❌ Repeated Status Checks

```python
# BAD - spams runtime logs
def get_db():
    logger.debug("Using database: X")  # Every call!
```

```python
# GOOD - log once at startup
_logged = False
def get_db():
    global _logged
    if not _logged:
        logger.debug("Using database: X")
        _logged = True
```

### ❌ Third-Party Library Noise

```python
# BAD - lets urllib3/pymongo flood logs
logging.basicConfig(level=logging.DEBUG)
```

```python
# GOOD - suppress in setup_logging()
logging.getLogger('pymongo').setLevel(logging.WARNING)
```

## Operator Scenarios

### "Why is startup slow?"

```bash
python launch.py --dev
```

Look at phase timings in final summary:

```
[⏱️] Timing: Core=0.00s | DB=1.13s | Scheduler=0.00s | Cogs=4.21s | Connect=3.01s
```

### "Which cog is failing to load?"

```bash
python launch.py --dev
```

Check the loader summary table - failed items show ❌ with error message.

### "Why isn't my command registering?"

```bash
python launch.py --dev
```

Final summary shows:

```
[startup] Slash commands (global=27): analyze, announce, bank, ...
```

Compare against expected count.

### "What's happening during cog load?"

```bash
TRACE=1 python launch.py --dev
```

Shows individual `[🐰] Loading admin/canon...` messages.

## Maintenance Guidelines

### Adding New Components

1. **Choose appropriate level**:
   - Phase completion: INFO
   - Component init: DEBUG
   - Per-item processing: Suppress or TRACE-only

2. **Use emoji prefixes** for visual scanning:
   - 🐰 Core/Loader
   - 💾 Storage
   - 🎨 Image Gen
   - 📗 Database
   - ⏰ Scheduler
   - 🔌 Adapters

3. **Include metrics** in summaries:

   ```python
   logger.info(f"[🐰] Loaded {count} cogs across {categories} categories")
   ```

4. **Suppress third-party noise** in `setup_logging()`:
   ```python
   logging.getLogger('new_library').setLevel(logging.WARNING)
   ```

### Reviewing Startup Logs

**Good startup log characteristics**:

- ✅ Clear phase progression
- ✅ Counts and metrics visible
- ✅ Failures immediately obvious
- ✅ No walls of repeated text
- ✅ No third-party library spam

**Red flags**:

- ❌ Same message repeated 100+ times
- ❌ Full config dumps in DEBUG
- ❌ Third-party stack traces
- ❌ No phase structure

## Future Improvements

### Structured Logging (JSONL)

Already implemented - all logs go to `logs/abby.jsonl` for:

- Machine parsing
- Telemetry ingestion
- Historical analysis

### Startup Performance Metrics

Consider adding to metrics collection:

- Per-cog load time
- Database connection latency
- Slow initialization warnings (>1s)

### Health Check Endpoint

Expose startup state via HTTP:

```json
{
  "status": "healthy",
  "startup_duration_ms": 8960,
  "cog_count": 33,
  "command_count": 27,
  "phases": {
    "core_services": "complete",
    "mongodb": "complete",
    "scheduler": "complete",
    "cogs": "complete",
    "connection": "complete"
  }
}
```

---

**Last Updated**: 2026-02-02  
**Maintainer**: Architecture Team  
**Review Cycle**: Annual or on major refactors
