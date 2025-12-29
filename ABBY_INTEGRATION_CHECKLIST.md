# Abby: Integration Checklist

## Quick Overview

Abby needs to emit **events** to a shared log file. That's it. TDOS will watch those events and report health. No kernel jobs, no state changes, no extra APIs.

---

## Step 1: Set Up Event Log Path

### Environment Variable

```bash
# In your .env or launcher:
SHARED_LOGS_DIR=/path/to/TDOS/shared/logs
```

### Fallback (Hardcoded)

```javascript
const eventLogDir = process.env.SHARED_LOGS_DIR || "/shared/logs";
const eventLogFile = path.join(eventLogDir, "events.jsonl");
```

### Ensure Directory Exists

```javascript
const fs = require("fs");
const path = require("path");

function ensureEventLogDir() {
  if (!fs.existsSync(eventLogDir)) {
    fs.mkdirSync(eventLogDir, { recursive: true });
  }
}
```

---

## Step 2: Implement Event Emission Function

```javascript
function emitEvent(eventType, payload = {}) {
  const event = {
    event_id: `EVT-${Date.now()}`,
    type: eventType,
    timestamp: new Date().toISOString(),
    entity_id: "ENTITY:ABBY:DISCORD",
    payload,
  };

  try {
    const line = JSON.stringify(event) + "\n";
    fs.appendFileSync(eventLogFile, line, "utf8");
  } catch (err) {
    // Silently fail if event log is unavailable
    // (Don't let monitoring break Abby's primary function)
    console.error("[Abby] Event log append failed:", err.message);
  }
}
```

---

## Step 3: Emit Lifecycle Events

### On Startup

```javascript
emitEvent("HEARTBEAT", {
  message: "Abby started",
  version: ABBY_VERSION,
  discordServers: client.guilds.size,
});
```

### Periodic Heartbeat (Every 30 Seconds)

```javascript
setInterval(() => {
  emitEvent("HEARTBEAT", {
    discordServers: client.guilds.size,
    memoryUsage: process.memoryUsage().heapUsed,
    uptime: process.uptime(),
  });
}, 30000);
```

### On User Command Started

```javascript
client.on("messageCreate", (msg) => {
  if (msg.author.bot) return;

  emitEvent("JOB.STARTED", {
    command: msg.content.split(" ")[0],
    userId: msg.author.id,
    serverId: msg.guildId,
  });

  // ... handle command ...
});
```

### On Command Complete (Success)

```javascript
emitEvent("JOB.COMPLETED", {
  command: msg.content.split(" ")[0],
  userId: msg.author.id,
  result: "success",
  duration_ms: Date.now() - startTime,
});
```

### On Command Error

```javascript
emitEvent("JOB.FAILED", {
  command: commandName,
  userId: userId,
  error: err.message,
  error_code: err.code,
});
```

### On Unexpected Error

```javascript
process.on("uncaughtException", (err) => {
  emitEvent("ERROR", {
    type: "uncaughtException",
    message: err.message,
    stack: err.stack.split("\n").slice(0, 5).join(" | "),
  });

  // Handle error as before (restart, log, etc.)
});

process.on("unhandledRejection", (reason) => {
  emitEvent("ERROR", {
    type: "unhandledRejection",
    message: String(reason),
    stack: reason.stack
      ? reason.stack.split("\n").slice(0, 5).join(" | ")
      : "N/A",
  });
});
```

---

## Step 4: Add Message Activity (Optional)

```javascript
client.on("messageCreate", (msg) => {
  // ... existing code ...

  // Optional: Track outbound messages
  if (msg.author.id === client.user.id) {
    emitEvent("MESSAGE_SENT", {
      serverId: msg.guildId,
      channelId: msg.channelId,
      length: msg.content.length,
    });
  }
});
```

---

## Step 5: Test Event Emission

### Verify File Creation

```bash
ls -la shared/logs/events.jsonl
```

### Check Event Content

```bash
tail -20 shared/logs/events.jsonl | jq .
```

### Expected Output

```json
{
  "event_id": "EVT-1735246800123",
  "type": "HEARTBEAT",
  "timestamp": "2025-12-27T06:00:00.123Z",
  "entity_id": "ENTITY:ABBY:DISCORD",
  "payload": {
    "discordServers": 5,
    "memoryUsage": 52428800
  }
}
```

---

## Step 6: Verify TDOS Integration

### Run CLERK:ACTIVITY Analysis

```bash
tdos clerk run activity --entity ENTITY:ABBY:DISCORD --window 60
```

### View Snapshot

```bash
tdos clerk activity snapshot --entity ENTITY:ABBY:DISCORD
```

### Check Status Dashboard

```bash
tdos status
```

**Look for**: GOVERNED ENTITIES section with Abby's health.

---

## Event Types Reference

| Event Type      | When                       | Payload Notes                                       |
| --------------- | -------------------------- | --------------------------------------------------- |
| `HEARTBEAT`     | Every 30 seconds           | Optional: servers, memory, uptime                   |
| `JOB.STARTED`   | User command received      | Include: command name, user, server                 |
| `JOB.COMPLETED` | Command finished (success) | Include: duration, result details                   |
| `JOB.FAILED`    | Command errored            | Include: error message, error code                  |
| `ERROR`         | Uncaught error             | Include: error type, message, stack (first 5 lines) |
| `MESSAGE_SENT`  | Abby sends Discord message | Include: server, channel, message length            |

---

## Important Notes

### Performance

- Events are appended asynchronously (non-blocking)
- No network calls; local file write only
- ~1ms overhead per event (negligible)
- No impact on Discord bot responsiveness

### Reliability

- Event log is append-only (never corrupted by overwrites)
- File system handles concurrent writes safely
- If event log is unavailable, Abby continues normally
- TDOS continues work even if Abby is unavailable

### Privacy

- Event payloads are visible to TDOS operators
- Don't emit sensitive Discord tokens or user passwords
- Server IDs and user IDs are safe to include
- Keep payload size reasonable (< 1KB per event)

---

## Minimal Implementation (Just Heartbeat)

If you want to start simple:

```javascript
const fs = require("fs");
const path = require("path");

const eventLogFile = path.join(
  process.env.SHARED_LOGS_DIR || "/shared/logs",
  "events.jsonl"
);

function emitEvent(type, payload = {}) {
  try {
    fs.appendFileSync(
      eventLogFile,
      JSON.stringify({
        event_id: `EVT-${Date.now()}`,
        type,
        timestamp: new Date().toISOString(),
        entity_id: "ENTITY:ABBY:DISCORD",
        payload,
      }) + "\n"
    );
  } catch (_) {
    // Silent fail; don't break Abby
  }
}

// In your startup
emitEvent("HEARTBEAT");

// Every 30 seconds
setInterval(() => emitEvent("HEARTBEAT"), 30000);

// That's it! TDOS will handle the rest.
```

---

## Troubleshooting

### Events Not Appearing

1. ✅ Check `SHARED_LOGS_DIR` is set correctly
2. ✅ Verify file permissions: Abby can write to `shared/logs/`
3. ✅ Check `events.jsonl` file exists and grows
4. ✅ Verify JSON format: `tail events.jsonl | jq .`

### "No events found" in TDOS

1. ✅ Ensure `entity_id` is exactly `ENTITY:ABBY:DISCORD`
2. ✅ Check event timestamps are recent
3. ✅ Wait 60+ seconds for first window of events
4. ✅ Run `tdos clerk run activity --entity ENTITY:ABBY:DISCORD --window 60`

### File Permissions Error

```bash
chmod 666 shared/logs/events.jsonl
chmod 777 shared/logs
```

---

## Timeline

- **Week 1**: Implement event emission (2-3 hours)
- **Week 1**: Test with `tdos status` (30 minutes)
- **Week 2**: Add detailed payloads (command names, error details)
- **Week 2**: Monitor trends, adjust heartbeat interval if needed
- **Ongoing**: Abby runs independently, TDOS watches

---

## That's It!

You're not building a new API. You're not integrating into TDOS internals. You're just appending JSON lines to a file. TDOS does the heavy lifting (analysis, anomaly detection, operator dashboard).

Abby remains autonomous. TDOS gains visibility.

---

Questions? See [ABBY_GOVERNANCE_INTEGRATION.md](ABBY_GOVERNANCE_INTEGRATION.md) for the full context.
