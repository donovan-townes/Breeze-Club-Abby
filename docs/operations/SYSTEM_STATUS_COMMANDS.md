# System Status Operator Commands

This document describes the `/operator system status` command suite for viewing platform state (seasons, events, effects, jobs).

## Command Implementation Guide

### Required Command Structure

```python
# Location: abby_core/discord/cogs/admin/operator_system_commands.py

@app_commands.command(name="status")
@app_commands.describe(
    section="What to display: [empty], seasons, events, effects, jobs, all"
)
async def operator_status(interaction: discord.Interaction, section: str = ""):
    """View platform state (seasons, events, effects, jobs)."""
    # Implementation below
```

### Command Options

The `/operator system status` command accepts these sections:

| Section   | Shows                                            | Command                           |
| --------- | ------------------------------------------------ | --------------------------------- |
| (none)    | Summary of all system state                      | `/operator system status`         |
| `seasons` | All seasons with dates and status                | `/operator system status seasons` |
| `events`  | All events with dates and auto-management status | `/operator system status events`  |
| `effects` | Currently active effects and their sources       | `/operator system status effects` |
| `jobs`    | Background job status and execution times        | `/operator system status jobs`    |
| `all`     | Complete system state (all sections)             | `/operator system status all`     |

---

## Output Format Examples

### Default (No Section)

```
/operator system status

OUTPUT:
═════════════════════════════════════════════════════════════
📋 PLATFORM STATE SUMMARY - February 4, 2026, 20:58 UTC
═════════════════════════════════════════════════════════════

🌍 ACTIVE SEASON
   Winter 2026 (Dec 21 - Mar 19)
   Days Remaining: 44
   Effects: xp_reset, persona_overlay, tone_shift

💕 ACTIVE EVENTS
   ✅ Valentine's Day 2026 (Feb 1-14)
      Days Remaining: 10
      Effect: crush_system_enabled
      Auto-Deactivates: February 15

🥚 UPCOMING EVENTS
   ⏸️ Easter 2026: Starts April 3 (58 days away)
   ⏸️ 21 Days of the Breeze: Starts December 1 (331 days away)

📅 BACKGROUND JOBS
   ✅ season_rollover: Enabled (Daily 00:00 UTC)
   ✅ event_lifecycle: Enabled (Daily 00:00 UTC)
   ✅ unified_content_dispatcher: Enabled (Every 60s)

✅ All systems operational
```

### Seasons Section

```
/operator system status seasons

OUTPUT:
═════════════════════════════════════════════════════════════
🌍 SEASONAL CYCLE - 2026
═════════════════════════════════════════════════════════════

Winter 2026
  Status: ✅ ACTIVE
  Date Range: Dec 21, 2025 - Mar 19, 2026
  Progress: Day 45 of 90
  Days Remaining: 44
  Effects Applied: xp_reset, persona_overlay, tone_shift
  XP Reset Applied: Yes (applied Dec 21, 2025)

Spring 2026
  Status: ⏸️ UPCOMING (45 days away)
  Date Range: Mar 20 - Jun 20
  Days Until: 45

Summer 2026
  Status: ⏸️ UPCOMING (103 days away)
  Date Range: Jun 21 - Sep 21
  Days Until: 103

Fall 2026
  Status: ⏸️ UPCOMING (185 days away)
  Date Range: Sep 22 - Dec 20
  Days Until: 185

ℹ️ Season transitions happen automatically at 00:00 UTC
ℹ️ XP resets apply to all users at transition time
```

### Events Section

```
/operator system status events

OUTPUT:
═════════════════════════════════════════════════════════════
📅 EVENT SCHEDULE - 2026
═════════════════════════════════════════════════════════════

Valentine's Day 2026
  Status: ✅ ACTIVE (4/14 days)
  Date Range: Feb 1-14, 2026
  Progress: 4 days active, 10 days remaining
  Effect: crush_system_enabled
  Game Features:
    • Secret admirer confessions
    • Heart currency rewards
    • Crush interaction system
  Auto-Deactivates: February 15, 2026 at 00:00 UTC
  Auto-Start Announcement: February 1, 2026 at 09:00 UTC ✅ Sent
  Auto-End Announcement: Will send February 15 at 09:00 UTC
  Operator Control: Can be manually activated/deactivated

Easter 2026
  Status: ⏸️ UPCOMING (58 days away)
  Date Range: Apr 3-5, 2026 (Good Friday - Easter Sunday)
  Effect: egg_hunt_enabled
  Game Features:
    • Egg hunting exploration
    • Easter-themed puzzles
    • Special seasonal content
  Auto-Activates: April 3, 2026 at 00:00 UTC
  Auto-Deactivates: April 6, 2026 at 00:00 UTC
  Operator Control: Can be manually activated/deactivated

21 Days of the Breeze 2026
  Status: ⏸️ UPCOMING (331 days away)
  Date Range: Dec 1-21, 2026 (21 days)
  Effect: breeze_event_enabled
  Game Features:
    • Holiday celebration activities
    • Winter-themed minigames
    • Special seasonal rewards
  Auto-Activates: December 1, 2026 at 00:00 UTC
  Auto-Deactivates: December 22, 2026 at 00:00 UTC
  Operator Control: Can be manually activated/deactivated

ℹ️ All events auto-manage: no operator action required
ℹ️ Announcements scheduled for: 09:00 UTC daily
ℹ️ Event dates are locked in system_state collection
```

### Effects Section

```
/operator system status effects

OUTPUT:
═════════════════════════════════════════════════════════════
⚙️ ACTIVE EFFECTS
═════════════════════════════════════════════════════════════

SEASON EFFECTS
Source: Winter 2026 (Active Season)
  ✅ xp_reset: Enabled
     └─ Effect: XP reset on season transition (applied Dec 21)
  ✅ persona_overlay: Enabled
     └─ Current Value: "cozy_ceremonial"
     └─ Effect: Seasonal dialogue tone adjustment
  ✅ tone_shift: Enabled
     └─ Effect: Winter-themed language and references

EVENT EFFECTS
Source: Valentine's Day 2026 (Active Event)
  ✅ crush_system_enabled: Enabled
     └─ Effect: Secret admirer system active
     └─ Effect: Heart economy active
     └─ Effect: Crush confessions available
     └─ Duration: Until February 15

BACKGROUND JOBS
  ✅ season_rollover: Enabled
     └─ Executes: Daily at 00:00 UTC
     └─ Purpose: Detect season boundaries, reset XP
  ✅ event_lifecycle: Enabled
     └─ Executes: Daily at 00:00 UTC
     └─ Purpose: Auto-activate/deactivate events
  ✅ unified_content_dispatcher: Enabled
     └─ Executes: Every 60 seconds
     └─ Purpose: Generate and deliver announcements

═════════════════════════════════════════════════════════════
Total Active Effects: 5 (3 seasonal + 2 event-based)
```

### Jobs Section

```
/operator system status jobs

OUTPUT:
═════════════════════════════════════════════════════════════
📅 BACKGROUND JOB STATUS
═════════════════════════════════════════════════════════════

season_rollover
  Status: ✅ ENABLED
  Job ID: system.season_rollover
  Schedule: Daily at 00:00 UTC
  Last Executed: 2026-02-02 00:00:47 UTC (2 days ago)
  Next Scheduled: 2026-02-05 00:00:00 UTC (in 3 days)
  Recent Execution History: ✅ ✅ ✅ (last 3 successful)
  Purpose: Detect season boundaries, activate new seasons, reset XP

event_lifecycle
  Status: ✅ ENABLED
  Job ID: system.event_lifecycle
  Schedule: Daily at 00:00 UTC
  Last Executed: 2026-02-04 00:00:45 UTC (today, 20 hours ago)
  Next Scheduled: 2026-02-05 00:00:00 UTC (tomorrow)
  Recent Execution History: ✅ (first run since deployment)
  Purpose: Auto-activate/deactivate events based on date boundaries
  Recent Actions:
    ✅ Verified Valentine's Day is active
    ✅ Verified Easter and 21 Days are inactive (not yet time)

unified_content_dispatcher
  Status: ✅ ENABLED
  Job ID: unified_content_dispatcher
  Schedule: Every 60 seconds (continuous)
  Last Executed: 2026-02-04 20:58:00 UTC (just now)
  Next Scheduled: 2026-02-04 20:59:00 UTC (in 60s)
  Recent Execution History: ✅ ✅ ✅ ✅ ✅ (continuous)
  Purpose: Generate and deliver all announcements
  Processing Queue:
    • 2 event announcements (waiting for scheduled time)
    • 0 season announcements

⚠️ NOTE: For detailed job logs, use /operator system jobs debug
```

---

## Related Operator Commands

### Manual Event Control

```
/operator system event status {event_id}
  View detailed event status

/operator system event activate {event_id}
  Manually activate an event (bypasses date check)

/operator system event deactivate {event_id} [reason]
  Manually deactivate an event with optional reason
```

### Manual Job Control

```
/operator system jobs run {job_id}
  Manually trigger a job immediately (for testing)

/operator system jobs enable {job_id}
  Enable a disabled job

/operator system jobs disable {job_id}
  Disable a job (careful!)

/operator system jobs debug
  View detailed job logs and execution history
```

### Announcement Management

```
/operator system announcements pending
  View all queued announcements awaiting delivery

/operator system announcements send-now {announcement_id}
  Send an announcement immediately (bypasses schedule)

/operator system announcements history [count]
  View recent announcement delivery history
```

---

## Database Queries for Verification

If you need to check the database directly to verify state:

### Check Active Season

```javascript
db.system_state.findOne({ state_type: "season", active: true });
```

### Check All Events and Status

```javascript
db.system_state.find({ state_type: "event" }).projection({
  state_id: 1,
  label: 1,
  active: 1,
  start_at: 1,
  end_at: 1,
});
```

### Check Valentine's Specifically

```javascript
db.system_state.findOne({ state_id: "valentines-2026" });
```

### Check Pending Announcements

```javascript
db.content_delivery_items.find({
  content_type: "event",
  lifecycle_state: { $in: ["draft", "generated"] },
});
```

### Check Job Status

```javascript
db.scheduler_jobs.findOne({ job_type: "system.event_lifecycle" });
```

---

## Implementation Checklist

- [ ] Command structure defined in codebase
- [ ] Default section returns summary (all systems status)
- [ ] `seasons` section shows all seasons with active indicator
- [ ] `events` section shows all events with auto-manage status
- [ ] `effects` section shows currently active effects with sources
- [ ] `jobs` section shows job status and last execution time
- [ ] All sections handle missing data gracefully
- [ ] Timestamps displayed in user's guild timezone (or UTC if not set)
- [ ] Formatting uses embeds with color coding (green=active, gray=upcoming)
- [ ] Command respects operator-only permissions
- [ ] Command includes help text with section options
- [ ] Output is paginated for large result sets (if needed)

---

## See Also

- [Platform State Operator Reference](PLATFORM_STATE_OPERATOR_REFERENCE.md) - Complete operator guide
- [Event Lifecycle System](../architecture/EVENT_LIFECYCLE_SYSTEM.md) - Technical implementation
- [Operator Panel Guide](../guides/OPERATOR_PANEL.md) - Full operator command documentation
