# Abby Bot Startup Operations Guide

**Maintenance Horizon:** 50+ Years | **Last Updated:** 2026-01-29 | **Version:** 2.0.0

## Table of Contents

1. [Scope](#scope)
2. [Startup Sequence](#startup-sequence)
3. [Health Status Interpretation](#health-status-interpretation)
4. [Performance Baselines](#performance-baselines)
5. [Troubleshooting](#troubleshooting)
6. [Monitoring Strategy](#monitoring-strategy)
7. [Maintenance Tasks](#maintenance-tasks)

---

## Scope

This is the startup runbook. For architecture and operator policy, see:

- [../architecture/SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)

Startup uses a strict order to avoid dependency failures. The next section is the authoritative sequence and health interpretation.

## Startup Sequence

### Example Output (Annotated)

````python
[2026-01-29 22:13:13] [INFO] - [Main]: ======================================================================
Abby Bot v2.0.0 | Build: 2026-01-29 | Startup ID: 1e748a7f
Python 3.13.1 | Windows 11 | Mode: DEV
======================================================================

[🐰] Initializing core services (mode=dev)...
     └─ Creates StorageManager (disk quotas, user limits)
     └─ Creates ImageGenerator (validates Stability API connection)
     └─ Configuration validation (warnings logged if features disabled)

[📗] MongoDB connected and operational
     └─ Performs health check ping, validates collections exist
     └─ Database is ready for queries, job registration

[⏰] Platform scheduler operational (tick interval: 60s)
     └─ Starts background job loop (runs jobs every 60s)
     └─ Loads job registry from MongoDB
     └─ Registers handlers for all job types

[❤️ Heartbeat] Unified heartbeat service initialized (platform=60s, scheduler=60s, discord=60s, llm=300s)
     └─ Creates telemetry emitter
     └─ Registers collectors for: platform stats, scheduler health, Discord metrics, LLM latency

[🔌] Discord adapters initialized (tools, formatters, scheduler)
     └─ Registers: server_info, user_xp, bot_status tools
     └─ Registers: Discord embed formatter, announcement delivery
     └─ Registers: Scheduler job handlers for Discord operations

[🐰] Loaded 33 cogs across 8 categories
     └─ Admin: 4 cogs (config, reload, shutdown, slash_sync)
     └─ Community: 5 cogs (welcome, nudge, etc.)
     └─ Creative: 4 cogs (chatbot, image, etc.)
     └─ Economy: 6 cogs (bank, experience, etc.)
     └─ Entertainment: 5 cogs (games, giveaways, etc.)
     └─ Other: 5 cogs (support, utilities, etc.)

[🔗] Connecting to Discord Gateway...
     └─ Sends authentication token to Discord
     └─ Opens WebSocket connection
     └─ Waits for READY packet

[🌐] Connected to Discord Gateway (1 guild)
     └─ on_ready() event fires
     └─ Guild configuration initialized (1/1)
     └─ Initial heartbeat emitted to telemetry

======================================================================
[✓] System operational - 33 cogs, 8 commands (5.5s)
[💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK | Scheduler: OK
[⏱️] Timing: Core=0.00s | DB=0.04s | Scheduler=0.00s | Cogs=2.17s | Connect=2.75s
[🔗] Ready to serve 1 guild(s) | Startup ID: 1e748a7f
======================================================================
```python

### Phase Descriptions

| Phase | Duration | What It Does | Failure Mode |
| ----------------- | -------- | ----------------------------------------------------- | ------------------------------------------------------------------ |
| **Core Services** | 0-1s | Creates storage/image gen instances, validates config | Missing API keys, insufficient disk space |
| **MongoDB** | 0-2s | Connects to database, runs health check | Database offline, auth failed, network timeout |
| **Scheduler** | 0-0.5s | Starts job loop, loads job registry from DB | Scheduler already running (crashed previous instance) |
| **Adapters** | 0-0.5s | Registers tools, formatters, job handlers | Factory singletons corrupted |
| **Cogs** | 1-5s | Loads all 33 command modules | Missing imports, circular dependencies, exceptions in cog **init** |
| **Connection** | 1-10s | Authenticates token, opens Discord WebSocket | Invalid token, Discord API down, rate limited |
| **on_ready** | 1-3s | Initializes guild configs, emits heartbeat | Guild config DB errors, heartbeat telemetry down |

---

## Health Status Interpretation

### Status Dashboard

```python
[💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK | Scheduler: OK
```python

Each component shows `OK` or `DEGRADED`:

| Component | OK Means | DEGRADED Means | Impact |
| ------------- | ----------------------------------------- | ----------------------------------------- | -------------------------------------------------- |
| **MongoDB** | Database responding, schema valid | Connection failed, timeout, auth error | Core features unavailable (no XP, no economy) |
| **Storage** | StorageManager initialized, disk writable | Initialization failed, insufficient space | Image generation disabled, file operations fail |
| **Image Gen** | Stability API key valid, connection works | Missing API key, API down, auth failed | Image commands fail (not critical) |
| **Scheduler** | Job engine running, job registry loaded | Failed to start, job registry corrupted | Scheduled tasks don't run (announcements, cleanup) |

### Interpreting Mixed Health States

### Example: "MongoDB: DEGRADED | Storage: OK | Image Gen: OK | Scheduler: OK"

- ✅ Bot can still function (serve commands, respond to users)
- ⚠️ XP/economy features don't work (database unavailable)
- ⚠️ Scheduled jobs won't execute (scheduler needs MongoDB)
- **Action:** Check MongoDB logs, restart database service

### Example: "MongoDB: OK | Storage: DISABLED | Image Gen: DISABLED | Scheduler: OK"

- ✅ Bot operational, all core features work
- ⚠️ Image generation disabled (missing API key, not critical)
- **Action:** No emergency response needed, normal degraded mode

---

## Performance Baselines

### Expected Timing Ranges

| Phase | Expected | Warning | Critical |
| -------------- | --------- | ------- | -------------------------------- |
| **Core** | <0.5s | >1s | >2s |
| **MongoDB** | 0.02-0.1s | >0.5s | >2s (DB down) |
| **Scheduler** | <0.1s | >0.5s | Infinite (hung/already running) |
| **Cogs** | 1.5-3s | >5s | >10s (circular dependency) |
| **Connection** | 2-5s | >10s | >30s (Discord down/rate limited) |
| **Total** | 4-8s | >10s | >15s |

### Timing Anomaly Detection

### If total startup time is 15+ seconds:

1. Check which phase is slow (look at individual timings)
2. Common causes:
   - **Cogs slow:** Missing dependency, expensive initialization code
   - **Connection slow:** Discord API degraded, rate limiting, network issue
   - **DB slow:** MongoDB under load, network latency, query performance

### Use Startup ID to find root cause:

```bash
## Find all logs for this startup
grep "Startup ID: 1e748a7f" logs/abby.jsonl

## Look for errors during this startup
grep -E "ERROR | EXCEPTION" logs/abby.jsonl | grep "1e748a7f"

## Check timing breakdown
grep "Timing:" logs/abby.jsonl | grep "1e748a7f"
```python

---

## Troubleshooting

### "Heartbeat already running" Warning

**Root Cause:** Previous bot instance crashed, singleton service retained `running=True` state

### Solution:

1. Automatic: `reset_heartbeat_service()` called at startup (already implemented)
2. Manual: Restart Python process (kills singleton)
3. Prevention: Ensure graceful `close()` handler runs on shutdown

**Code Location:** `abby_core/services/heartbeat_service.py` - `reset_heartbeat_service()`

---

### "Scheduler already running" Warning

**Root Cause:** Previous scheduler instance crashed, `_scheduler_service` singleton not reset

### Solution:

1. Automatic: `reset_scheduler_service()` called at startup (already implemented)
2. Manual: Restart Python process
3. Prevention: Graceful shutdown handler stops scheduler before closing

**Code Location:** `abby_core/services/scheduler.py` - `reset_scheduler_service()`

---

### "Session is closed" RuntimeError

**Root Cause:** Discord WebSocket session from previous connection attempt not properly closed

### Symptoms:

```python
RuntimeError: Session is closed
  File ".../discord/client.py", line 839, in static_login
    data = await self.request(Route('GET', '/users/@me'))
```python

### Solution:

1. Automatic: `close()` handler stops scheduler, closes connection gracefully
2. Manual: Kill all Python processes, ensure no zombie connections
3. Prevention: Wait 2-3 seconds between restarts to allow socket cleanup

**Code Location:** `abby_core/discord/main.py` - `close()` method

---

### MongoDB Connection Failed

### Symptoms:

```python
[ERROR] - [abby_core.database.mongodb]: MongoDB unavailable - some features may be limited
[💚] Health: MongoDB: DEGRADED
```python

### Debugging:

1. Check MongoDB is running: `mongosh --eval "db.adminCommand('ping')"`
2. Check credentials: Validate `MONGODB_URL`, `MONGODB_DB` env vars
3. Check network: `ping localhost:27017` or appropriate MongoDB host
4. Check logs: `grep "mongodb" logs/abby.jsonl`

### Recovery:

1. Start MongoDB service: `net start MongoDB` (Windows) or `systemctl start mongod` (Linux)
2. Restart bot: `python launch.py --dev`
3. Verify: Look for `[📗] MongoDB connected and operational`

---

### Cogs Failing to Load

### Symptoms:

```python
[ERROR] - [abby_core.discord.core.loader]: Failed to load cog ...
[🐰] Loaded 20 cogs across 6 categories  (fewer than expected 33)
```python

### Debugging:

1. Check logs for import errors: `grep "ImportError\ | ModuleNotFoundError" logs/abby.jsonl`
2. Check for circular dependencies: Look for cog A imports cog B, B imports A
3. Check for exceptions in cog `__init__`: Each cog's `__init__(self, bot)` must not raise
4. Check dependencies: Missing packages, wrong Python version

### Recovery:

1. Fix the broken cog (see error message)
2. Test import: `python -c "from abby_core.discord.cogs.admin.guild_config import GuildConfig"`
3. Restart bot
4. Verify all 33 cogs loaded: `grep "Loaded.*cogs" logs/abby.jsonl`

---

### Discord Connection Timeout

### Symptoms:

```python
[🔗] Connecting to Discord Gateway...
(waits 30+ seconds)
[ERROR] - [discord.client]: Failed to connect to Discord
```python

### Causes:

1. **Invalid Token:** `ABBY_TOKEN` or `DEVELOPER_TOKEN` wrong/expired
2. **Discord API Down:** Status check at https://discordstatus.com
3. **Rate Limited:** Too many rapid restart attempts (Discord bans for 1hr)
4. **Network Issue:** Firewall blocking, VPN issues

### Recovery:

1. Verify token: Check `.env` or environment variables
2. Wait 1 hour if rate-limited (Discord temporary ban)
3. Check Discord status: https://discordstatus.com
4. Increase wait time between restarts (2-5 seconds)

---

## Monitoring Strategy

### Metrics to Track (50-Year Baseline)

```python
Startup Metrics:
├─ total_startup_time_seconds          (trending: watch for increases)
├─ phase_core_services_seconds         (baseline: 0.0-0.5s)
├─ phase_mongodb_seconds               (baseline: 0.02-0.1s)
├─ phase_scheduler_seconds             (baseline: 0.0-0.1s)
├─ phase_cogs_seconds                  (baseline: 1.5-3s)
├─ phase_connection_seconds            (baseline: 2-5s)
├─ health_mongodb_status               (OK, DEGRADED, DOWN)
├─ health_storage_status               (OK, DISABLED)
├─ health_image_gen_status             (OK, DISABLED)
├─ health_scheduler_status             (OK, DEGRADED)
├─ cog_count                           (should be 33)
├─ command_count                       (should be 8)
└─ startup_id                          (for log correlation)
```python

### Alerting Rules

### CRITICAL (Page operator immediately):

- Total startup time > 20s (indicates infrastructure degradation)
- MongoDB health = DEGRADED (core features unavailable)
- Cog count < 25 (missing critical commands)

### WARNING (Investigate within 1 hour):

- Connection time > 10s (Discord slowness or rate limiting)
- MongoDB time > 0.5s (network latency or DB load)
- Total startup time > 15s (trending toward critical)

### INFO (Log for trending):

- Any startup completes (store all metrics)
- Health status changes (monitor degraded modes)
- Cog load times (detect slow cogs over time)

### Grafana Dashboard Setup

Store these metrics in structured JSON format (already implemented):

```json
{
  "timestamp": "2026-01-29T22:13:19Z",
  "level": "INFO",
  "startup_id": "1e748a7f",
  "phase": "Startup Complete",
  "metrics": {
    "startup_duration_seconds": 5.5,
    "cog_count": 33,
    "command_count": 8,
    "guild_count": 1,
    "health_status": [
      "MongoDB: OK",
      "Storage: OK",
      "Image Gen: OK",
      "Scheduler: OK"
    ]
  },
  "phase_timings": {
    "core_services": 0.0,
    "mongodb": 0.04,
    "scheduler": 0.0,
    "cogs": 2.17,
    "connection": 2.75
  }
}
```python

Import into Prometheus/Grafana for historical trending.

---

## Maintenance Tasks

### Daily (Automated)

- ✅ Monitor startup duration (alerting on >20s)
- ✅ Track health status changes
- ✅ Archive JSONL logs (rotate if >100MB)

### Weekly

- Review startup anomalies: Are any phases trending slower?
- Check cog load times: Any individual cog slow?
- Validate all 33 cogs loaded successfully

### Monthly

- Performance baseline review: Are timings stable?
- Dependency audit: Any packages need updates?
- Log storage analysis: Growth rate sustainable?

### Quarterly

- Full load test: Restart bot 10 times, verify consistency
- Failover test: Kill MongoDB, restart bot, verify degraded mode handling
- Token rotation: Verify bot token still valid, no expiration

### Annually

- Architecture review: Any changes needed for next 12 months?
- Documentation update: Reflect any changes in this guide
- Disaster recovery test: Can we recover from corrupted singletons?

---

## Critical Files Reference

| File | Purpose | Maintenance |
| ----------------------------------------- | --------------------------------------- | --------------------------------------------- |
| `abby_core/discord/main.py` | Bot lifecycle, startup sequence | Update when phases change |
| `abby_core/observability/logging.py` | Logging setup, startup phases | Update `STARTUP_PHASES` dict if adding phases |
| `abby_core/services/scheduler.py` | Job engine, `reset_scheduler_service()` | Verify reset logic on changes |
| `abby_core/services/heartbeat_service.py` | Telemetry, `reset_heartbeat_service()` | Verify reset logic on changes |
| `docs/STARTUP_OPERATIONS_GUIDE.md` | This file | **Update whenever startup changes** |

---

## Version History

| Version | Date | Changes |
| ------- | ---------- | ---------------------------------------------------------------------------------- |
| 2.0.0 | 2026-01-29 | Professional startup logging, health status, accurate timing, 50-year architecture |
| 1.0.0 | 2025-XX-XX | Initial startup (pre-professional) |

---

## Contact & Escalation

### For Startup Issues:

1. Check logs: `grep Startup ID logs/abby.jsonl`
2. Check this guide's troubleshooting section
3. Verify environment: Python version, MongoDB running, Discord status
4. Check recent changes: Did code/config change recently?

### For Performance Degradation:

1. Identify which phase is slow (see timing breakdown)
2. Check that component's logs
3. Verify external dependencies (MongoDB, Discord API)
4. Review this guide's performance baselines

### For 50-Year Maintenance:

- Keep this document synchronized with code changes
- Update timing baselines when infrastructure changes
- Track architectural decisions in git commit messages
- Annual review of this guide (see Maintenance section)

---

**Document Status:** ✅ Production-Ready | **Maintenance Horizon:** 50+ Years | **Last Reviewed:** 2026-01-29
````
