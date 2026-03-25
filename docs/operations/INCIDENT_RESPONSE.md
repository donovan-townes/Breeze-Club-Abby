# Incident Response & Operational Safety

Comprehensive incident response procedures for Abby: health checks, triage workflow, multi-phase operations, rollback procedures, and 50-year operational safety.

**Last Updated:** January 31, 2026  
**Scope:** Production operations (Discord, web platforms)  
**Goal:** Zero downtime for user-facing services, 99.9% availability

---

## Executive Summary

Abby implements **three-layer incident response** for 50-year operational safety:

1. **Prevention** — Baseline monitoring, alerting rules, health checks
2. **Triage** — Systematic decision tree to identify root cause
3. **Recovery** — Atomic rollback with snapshot restoration, no data loss

---

## Platform Health Checks

### Health Check Dashboard

Every operator has access to real-time platform health:

```python
from abby_core.discord.cogs.admin.operator_panel import get_platform_health

health = await get_platform_health()

## Returns
{
    "mongodb": {
        "status": "HEALTHY",  # HEALTHY, DEGRADED, CRITICAL
        "latency_ms": 5.2,
        "connection_time": "2026-01-31T14:25:10Z",
        "last_error": None
    },
    "storage": {
        "status": "HEALTHY",
        "usage_gb": 42.5,
        "available_gb": 157.5,
        "percent_used": 21.2
    },
    "image_generation": {
        "status": "HEALTHY",
        "queue_size": 2,
        "last_success": "2026-01-31T14:24:50Z",
        "error_rate": 0.002
    },
    "scheduler": {
        "status": "HEALTHY",
        "ticks_per_minute": 60,
        "failed_jobs_in_dlq": 3,
        "last_tick": "2026-01-31T14:25:01Z"
    },
    "discord": {
        "status": "HEALTHY",
        "latency_ms": 45,
        "guild_count": 128,
        "user_count": 45632
    }
}
```python

### Status Mapping

| Status | Description | Action |
| -------- | ------------- | -------- |
| **HEALTHY** | Service operating normally | Monitor, no action |
| **DEGRADED** | Service degraded but functional | Monitor closely, prepare fallback |
| **CRITICAL** | Service down or unusable | Page on-call, execute incident response |

---

## Quick Triage Workflow

When an alert fires, follow this decision tree:

```python
ALERT FIRED (e.g., "Generation error rate > 5%")
│
├─ Step 1: Check Platform Health
│  │
│  ├─ MongoDB CRITICAL?
│  │  └─ YES → Go to: MongoDB Recovery (below)
│  │  └─ NO → Continue
│  │
│  ├─ Storage full?
│  │  └─ YES → Go to: Storage Recovery (below)
│  │  └─ NO → Continue
│  │
│  └─ Scheduler stuck?
│     └─ YES → Go to: Scheduler Recovery (below)
│     └─ NO → Continue
│
├─ Step 2: Check Recent Errors (DLQ)
│  │
│  ├─ Common pattern? (> 50% of errors same type)
│  │  ├─ API key expired? → Rotate key, redeploy
│  │  ├─ Memory exhaustion? → Scale up container, restart
│  │  ├─ State machine bug? → Investigate code, deploy fix
│  │  └─ User input validation? → Check DLQ for patterns
│  │
│  └─ Random errors? (< 20% correlation)
│     └─ Likely transient, monitor for 15 min
│
├─ Step 3: Check Affected Users
│  │
│  ├─ Single guild affected?
│  │  ├─ Data corruption? → Go to: Data Corruption Recovery
│  │  └─ User quota exceeded? → Message user, resolve manually
│  │
│  └─ Multiple guilds affected?
│     └─ System-wide issue → Go to: System Recovery
│
├─ Step 4: Escalation Decision
│  │
│  ├─ Error rate declining? → Monitor for 15 min, close ticket
│  ├─ Error rate stable? → Monitor + investigate root cause
│  └─ Error rate rising? → Page tier 2 engineer, begin recovery
│
└─ Step 5: Communicate Status
   ├─ Send status update to #operations channel
   └─ Include: Issue description, current status, ETA to resolution
```python

---

## Common Scenarios & Recovery

### Scenario 1: MongoDB Connection Lost

### Symptoms:

- `startup_time` > 20s
- All operations fail with connection timeout
- Health check shows CRITICAL for MongoDB

### Recovery Steps:

1. **Verify connectivity:**
   ```bash
   mongo $MONGODB_URI --eval "db.adminCommand('ping')"
   # Expected: { "ok" : 1 }
   ```

1. **Check MongoDB status:**
   ```bash
   # If MongoDB in cloud (Atlas, etc.)
   # Check console for alerts
   
   # If self-hosted
   systemctl status mongodb
   systemctl logs mongodb -n 100
   ```

1. **Reconnect bot:**
   ```bash
   # Force reconnection
   docker restart abby-bot
   
   # Monitor logs
   tail -f logs/abby.jsonl | grep "database_connection"
   ```

1. **If still failing, failover:**
   ```python
   # Check replica set status
   mongo $MONGODB_PRIMARY --eval "rs.status()"
   
   # If primary down, force secondary as new primary
   mongo $MONGODB_SECONDARY --eval "rs.stepDown()"
   
   # This triggers failover to secondary
   ```

### Prevention:

- [ ] Use MongoDB replicas (3+ nodes) for production
- [ ] Set connection retry policy with exponential backoff
- [ ] Monitor connection pool health

### Scenario 2: High Generation Error Rate

### Symptoms:

- Error rate > 5% for generation operations
- DLQ backlog growing
- `generation_p95_latency` > 3000ms

### Triage Steps:

1. **Check error category distribution:**
   ```python
   from abby_core.services.dlq_service import DLQService
   
   dlq = DLQService()
   errors_by_category = dlq.get_failure_diagnostics(
       error_category=None,  # All categories
       last_n_hours=1
   )
   
   # Group by type
   from collections import Counter
   categories = Counter(e["error_category"] for e in errors_by_category)
   print(f"Top errors: {categories.most_common(3)}")
   ```

1. **Check for pattern:**
   - If > 50% `API_ERROR` → API provider issue
   - If > 50% `VALIDATION_ERROR` → Model/prompt regression
   - If > 50% `STATE_TRANSITION` → State machine bug
   - If mixed → Likely transient load spike

1. **Recovery:**

   ### For API errors:
   ```bash
   # Check API status
   curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
   
   # If failed, contact provider support
   # Implement fallback LLM if available
   ```

   ### For validation errors:
   ```bash
   # Revert latest code deployment
   git revert HEAD
   git push origin main
   
   # Redeploy
   docker build -t abby:latest .
   docker push abby:latest
   docker service update --image abby:latest abby-service
   ```

   ### For state transition errors:
   ```python
   # Manually resolve stuck operations
   from abby_core.services.dlq_service import DLQService
   
   dlq = DLQService()
   
   # Move stuck operations to archive
   stuck = await dlq.get_failures_by_age(hours=2)
   
   for op in stuck:
       if op["retry_count"] >= 3:
           await dlq.archive_operation(op["operation_id"])
   ```

### Scenario 3: Scheduler Not Ticking

### Symptoms:

- No scheduler heartbeat for > 2 minutes
- Scheduled jobs not executing
- Job queue not advancing

### Recovery Steps:

1. **Check scheduler health:**
   ```python
   from abby_core.services.scheduler import SchedulerService
   
   scheduler = SchedulerService()
   
   # Check if ticking
   if scheduler.is_running():
       print("Scheduler is running")
   else:
       print("Scheduler is NOT running")
       
   # Check pending jobs
   pending = await scheduler.get_pending_jobs()
   print(f"Pending jobs: {len(pending)}")
   ```

1. **Check for stuck claim:**
   ```python
   # Scheduler claims jobs atomically
   # If bot crashes mid-execution, job stays CLAIMED forever
   
   # Find stuck jobs
   stuck = db.scheduler_jobs.find({
       "status": "CLAIMED",
       "last_run_at": {$lt: now() - timedelta(minutes=5)}
   })
   
   # Force reset
   for job in stuck:
       db.scheduler_jobs.update_one(
           {_id: job._id},
           {$set: {status: "READY"}}
       )
   ```

1. **Restart scheduler:**
   ```bash
   # In codebase, trigger scheduler restart
   docker exec abby-bot python -c "
   from abby_core.services.scheduler import SchedulerService
   scheduler = SchedulerService()
   await scheduler.restart()
   "
   ```

1. **Monitor recovery:**
   ```bash
   tail -f logs/abby.jsonl | grep "Scheduler tick"
   # Should see new tick every 60s
   ```

### Scenario 4: Guild Data Corruption

### Symptoms:

- Single guild reports incorrect state (stuck conversation, wrong XP)
- Other guilds unaffected
- Guild-specific queries hang or fail

### Recovery Steps:

1. **Identify corruption:**
   ```python
   # Check guild state consistency
   from abby_core.system.state_management import StateValidator
   
   validator = StateValidator()
   
   is_valid = await validator.validate_guild_state(guild_id="123456")
   
   if not is_valid:
       print("Guild state is corrupted")
   ```

1. **Restore from snapshot:**
   ```python
   from abby_core.system.system_operations import restore_guild_snapshot
   
   # List available snapshots
   snapshots = await get_guild_snapshots(guild_id="123456")
   
   for snap in snapshots:
       print(f"Snapshot {snap['_id']}: {snap['created_at']} - {snap['version']}")
   
   # Restore to 1 hour ago
   target_snapshot = snapshots[-1]  # Most recent
   
   await restore_guild_snapshot(
       guild_id="123456",
       snapshot_id=target_snapshot["_id"]
   )
   ```

1. **Verify guild is healthy:**
   ```bash
   # Guild health check
   python -c "
   from abby_core.discord.cogs.admin.operator_panel import get_guild_health
   health = await get_guild_health('123456')
   print(health)
   "
   ```

1. **Message users:**
   ```python
   # Notify affected users
   channel = bot.get_channel(SUPPORT_CHANNEL_ID)
   
   await channel.send('''
   We detected and resolved a data inconsistency in Guild `ABC123`.
   Your conversations have been restored to a consistent state.
   Thank you for your patience.
   ''')
   ```

---

## Multi-Phase Operations & Rollback

All critical operations follow a five-phase pattern for atomic safety:

```python
Phase A: Intent (Create operation record)
│
├─ Record: operation_id, user, timestamp, intent
├─ Status: PENDING
└─ MongoDB: system_operations collection
│
↓
Phase B: Snapshot (Capture current state)
│
├─ Copy current guild/user state
├─ Store: operation_snapshots collection
└─ Status: SNAPSHOT_CREATED
│
↓
Phase C: Mutation (Apply changes)
│
├─ Execute the operation
├─ Status: MUTATION_APPLIED
└─ On failure: Go to Rollback
│
↓
Phase D: Recompute (Update derived state)
│
├─ Update metrics, cache, etc.
├─ Status: RECOMPUTED
└─ On failure: Rollback
│
↓
Phase E: Announce (Notify users)
│
├─ Send message to user/guild
└─ Status: COMPLETED
```python

### Example: XP Season Reset

```python
from abby_core.system.season_reset_operations import (
    create_xp_season_reset,
    apply_xp_season_reset,
    rollback_xp_season_reset
)

## Phase A: Intent
op = await create_xp_season_reset(
    guild_id="123456",
    initiated_by="admin_user",
    reason="Manual season transition"
)
print(f"Operation: {op.operation_id}")

## Phase B: Snapshot (automatic)
## (Captured before Phase C)

## Phase C: Apply mutation
try:
    await apply_xp_season_reset(op.operation_id)
except Exception as e:
    print(f"Apply failed: {e}")
    
    # Phase F: Rollback
    await rollback_xp_season_reset(op.operation_id)
    print("Rolled back to snapshot")
```python

### Rollback Procedure

If any phase fails, rollback is automatic:

```python
from abby_core.system.system_operations import rollback_operation

## Manually trigger rollback
await rollback_operation(
    operation_id="op_abc123",
    reason="Manual intervention"
)

## Rollback steps:
## 1. Fetch snapshot
## 2. Restore all collections from snapshot
## 3. Invalidate guild cache (force refresh)
## 4. Mark operation as ROLLED_BACK
## 5. Notify user of rollback
```python

---

## Incident Investigation

### Gathering Context

When an incident occurs, collect:

1. **Timeline:**
   ```bash
   # Get logs around event time
   grep "2026-01-31T14:25:" logs/abby.jsonl | head -20
   ```

1. **Error details:**
   ```python
   # Query DLQ for error context
   errors = db.dlq.find({
       "created_at": {
           "$gte": incident_start_time,
           "$lte": incident_end_time
       }
   })
   
   for error in errors:
       print(f"Operation {error['operation_id']}: {error['error_message']}")
   ```

1. **State snapshot:**
   ```python
   # Capture guild state at time of incident
   guild_state = db.platform_state.find_one({"guild_id": incident_guild})
   print(json.dumps(guild_state, indent=2))
   ```

1. **Performance metrics:**
   ```python
   # Check system metrics during incident
   metrics = db.metrics.find({
       "timestamp": {
           "$gte": incident_start,
           "$lte": incident_end
       }
   })
   ```

### Post-Incident Review

After resolving, conduct review:

1. **Identify root cause:**
   - Was it predictable?
   - Should it have been caught in testing?
   - Does alerting exist for this?

1. **Document findings:**
   ```markdown
   ## Incident Report: XYZ
   
   **Time:** 2026-01-31 14:25 UTC  
   **Duration:** 15 minutes  
   **Impact:** 3 guilds, ~200 users  
   **Root Cause:** Database connection pool exhaustion  
   
   ### What Went Right:

   - Health check detected issue within 2 min
   - Automated snapshot prevented data loss
   - Rollback completed in < 1 min
   
   ### What Went Wrong:

   - No alert for connection pool > 80%
   - No runbook for this scenario
   - Manual investigation took 5 minutes
   
   ### Action Items:

   - [ ] Add connection pool alert threshold
   - [ ] Document recovery procedure
   - [ ] Load test connection pool
   ```

1. **Implement preventions:**
   - Add missing alerting rules
   - Update runbooks
   - Deploy code fixes
   - Increase monitoring

---

## Alerting Rules

Configure these rules in monitoring system:

| Rule | Threshold | Severity | Action |
| ------ | ----------- | ---------- | -------- |
| MongoDB unavailable | > 30s | CRITICAL | Page on-call |
| Generation error rate | > 5% | WARNING | Notify ops |
| Generation error rate | > 20% | CRITICAL | Page on-call |
| Scheduler stopped | > 2 ticks missed | CRITICAL | Page on-call |
| DLQ backlog | > 100 messages | WARNING | Notify ops |
| Guild data corrupt | Any | CRITICAL | Page on-call |
| Storage quota | > 90% | WARNING | Notify ops |
| Memory usage | > 85% | WARNING | Notify ops |

---

## 50-Year Operational Safety

### Annual Audits

- [ ] Review all alerting rules (still relevant?)
- [ ] Audit recovery procedures (tested recently?)
- [ ] Check incident response SLO (currently < 15 min?)
- [ ] Verify snapshots are recent and restorable

### 5-Year Reviews

- [ ] Design new resilience patterns
- [ ] Evaluate distributed architecture (multi-region failover?)
- [ ] Plan operational capability growth
- [ ] Assess new incident categories

### 10-Year Reviews

- [ ] Full operational architecture redesign
- [ ] Plan for next-generation monitoring
- [ ] Evaluate AI-assisted incident response
- [ ] Zero-downtime deployment strategies

---

## Runbook Quick Reference

### Fastest Resolutions

1. **Generation error rate high** → Check DLQ categories, restart API clients
2. **Scheduler stuck** → Reset CLAIMED jobs, restart scheduler service
3. **Single guild corrupted** → Restore from snapshot (< 1 min)
4. **MongoDB slow** → Scale replicas, optimize queries
5. **Storage full** → Archive old data, delete cleanup

---

## Related Documents

- [OBSERVABILITY_RUNBOOK.md](OBSERVABILITY_RUNBOOK.md) — Metrics and alerts
- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) — Security incident response
- [SCHEDULER_JOBS_CATALOG.md](SCHEDULER_JOBS_CATALOG.md) — Scheduler troubleshooting
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) — Admin operations
