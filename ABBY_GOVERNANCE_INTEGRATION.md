# Abby + TDOS Governance Integration

## What This Means for Abby

### Before Integration

- Abby runs independently
- TDOS has no visibility into Abby's health
- If Abby crashes, TDOS doesn't know until something tries to use it
- Manual monitoring required

### After Integration

- Abby emits heartbeats and work events to `shared/logs/events.jsonl`
- TDOS CLERK:ACTIVITY continuously analyzes Abby's behavior
- `tdos status` shows Abby's health at a glance
- Anomalies surface automatically (EXCESSIVE_HEARTBEATS, ENTITY_SILENT, etc.)
- No kernel mutation—Abby's independence fully preserved

---

## Minimal Changes Required for Abby

### 1. Event Emission

Abby must append lines to `shared/logs/events.jsonl`:

```javascript
// In Abby startup
const eventLog = path.join(process.env.SHARED_LOGS_DIR, "events.jsonl");

function emitEvent(type, payload = {}) {
  const event = {
    event_id: `EVT-${Date.now()}`,
    type,
    timestamp: new Date().toISOString(),
    entity_id: "ENTITY:ABBY:DISCORD",
    payload,
  };
  fs.appendFileSync(eventLog, JSON.stringify(event) + "\n");
}

// Periodic heartbeat (e.g., every 30 seconds)
setInterval(() => emitEvent("HEARTBEAT"), 30000);

// On Discord command received/completed
emitEvent("JOB.STARTED", { command: msg.content });
emitEvent("JOB.COMPLETED", { command: msg.content, result: "success" });

// On error
emitEvent("ERROR", { message: err.message, stack: err.stack });
```

### 2. Environment Variables

Abby needs:

```bash
SHARED_LOGS_DIR=/path/to/TDOS/shared/logs
```

### 3. File Permissions

Event log must be writable by Abby's process. No special permissions needed beyond write access.

---

## Operational Impact

### For Operators

**Gain**:

- ✅ One-command visibility: `tdos status` shows Abby's health
- ✅ Anomaly detection: Flags surface behavioral changes
- ✅ Audit trail: All signals logged for forensics
- ✅ Historical analysis: Compare periods with `tdos clerk activity diff`

**No Loss**:

- ✅ Abby remains fully autonomous
- ✅ TDOS cannot restart, reconfigure, or control Abby
- ✅ No latency impact (events are appended asynchronously)
- ✅ No breaking changes to Abby's architecture

### For Abby

**Gain**:

- ✅ Visibility into own behavior (via `tdos status`)
- ✅ Anomaly detection without custom monitoring
- ✅ Integration with TDOS governance dashboard

**No Cost**:

- ✅ No kernel jobs or tasks forced onto Abby
- ✅ No registry writes or state mutations
- ✅ No API calls (append-only events, nothing pulls from Abby)
- ✅ No performance overhead (events are just file appends)

---

## Example Scenarios

### Scenario 1: Abby Goes Silent

**What Happens**:

```
1. Abby crashes (network issue, code bug, etc.)
2. Event emission stops
3. No new entries added to events.jsonl for 60 minutes
4. CLERK:ACTIVITY job detects: entity_id has 0 events
5. Flag: ENTITY_SILENT with severity MEDIUM
6. Operator sees on status dashboard: 🚩 1 flag (silence)
7. Operator checks Abby, restarts if needed
```

**Key**: TDOS detected it automatically. No auto-restart, but awareness enabled.

### Scenario 2: Abby Heartbeat Spam

**What Happens**:

```
1. Abby adds verbose debug logging
2. Event rate increases: 50,000/min (mostly HEARTBEAT)
3. Work events stay low: 1% ratio
4. Flag: EXCESSIVE_HEARTBEATS with severity MEDIUM
5. Operator sees on status: 7.5/min ✓ healthy (wait, no flag here, let me check)
6. Operator reviews latest snapshot via tdos clerk activity snapshot
7. Sees ratio is abnormal, logs are verbose
8. Disables verbose mode in Abby config
```

**Key**: Behavioral change visible before it becomes a problem.

### Scenario 3: Abby Handles Surge

**What Happens**:

```
1. Breeze Club event: 100 new members join
2. Message volume increases 10x (normal)
3. Event rate jumps: 2/min → 20/min (expected)
4. Work-to-heartbeat ratio stays healthy
5. No flags raised (activity matches HIGH expectation)
6. Operator notes trend, monitors for next 30 minutes
7. Rate returns to baseline → no action needed
```

**Key**: Temporary spikes don't false-alarm; behavior within expectation.

### Scenario 4: Abby Splits to New Server

**What Happens**:

```
1. Abby instance migrated to new hardware
2. Old instance: 0 events (goes ENTITY_SILENT)
3. New instance: ~7.5/min (normal)
4. CLERK:ACTIVITY reports for ENTITY:ABBY:DISCORD (new instance)
5. TDOS status shows healthy from migration onward
6. Old events in logs are historical (audit trail preserved)
```

**Key**: Signal continuity maintained even across infrastructure changes.

---

## Threshold Calibration

The Activity Clerk uses sensible defaults:

| Metric                  | Threshold               | Notes                    |
| ----------------------- | ----------------------- | ------------------------ |
| Work-to-Heartbeat Ratio | < 1%                    | Flags spam heartbeats    |
| Log Volume Spike        | 2σ above rolling avg    | Detects abnormal logging |
| Silence Window          | 0 events in 60 min      | Flags downtime           |
| Ratio Imbalance         | > 50% change from trend | Detects behavioral shift |

These thresholds are **deterministic and fully documented**, not magical.

---

## Future: Active Governance

Once MANAGED level is implemented, TDOS could:

- Request Abby restart (without force)
- Request config reload (Abby decides)
- Query Abby status directly (optional bidirectional API)
- Schedule maintenance windows
- Coordinate with other services

**But not yet**. Today: OBSERVED (read-only).

---

## Summary: Partnership Model

```
┌─────────────────────────────────────────────────────────────┐
│                      TDOS Kernel v1.4                       │
│  (Identity, Jobs, Pipelines, Ledger, Governance)            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ CLERK:ACTIVITY (New!)                                  │ │
│  │ Watches → Events → Signals → Flags → Proposals         │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ▲                                  │
│                    (reads events)                            │
│                           │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Abby Bot  │
                    │  (External) │
                    │  (Emits     │
                    │  Events)    │
                    └─────────────┘

Key: → (one-way), no ← control
```

**Abby** emits behavioral signals (events).  
**TDOS** observes and reports (CLERK:ACTIVITY).  
**No mutation**. **No control**. **Partnership**.

---

## Next Steps

1. **Enable Event Emission in Abby**: Modify Abby to append to events.jsonl
2. **Deploy CLERK:ACTIVITY Agent**: `tdos deploy agent --version 1.0` (when ready)
3. **Monitor Dashboard**: Run `tdos status` and watch GOVERNED ENTITIES
4. **Calibrate Thresholds**: Adjust based on Abby's normal behavior patterns
5. **Enable Trend Analysis**: Extend `tdos clerk activity trend` when temporal engine is ready

---

## Questions?

See:

- [CLERK_ACTIVITY_QUICK_REFERENCE.md](CLERK_ACTIVITY_QUICK_REFERENCE.md) — Operator commands
- [kernel/kernel/entity-governance.md](kernel/kernel/entity-governance.md) — Governance model
- [CLERK_ACTIVITY_IMPLEMENTATION.md](CLERK_ACTIVITY_IMPLEMENTATION.md) — Technical details
