# Platform State System - Operator Reference

## Overview

This document describes how the platform state system works, including seasons, events, effects, and how operators verify system status through the `/operator` command.

---

## Current System State (February 4, 2026)

### Active Season

- **Label**: Winter 2026
- **Date Range**: December 21, 2025 – March 19, 2026
- **Days Remaining**: ~44 days
- **Effects Applied**:
  - `xp_reset`: XP resets occur at season transitions
  - `persona_overlay`: Seasonal personality overlay enabled
  - `tone_shift`: Seasonal dialogue tone adjustments

### Active Events

- **Valentine's Day 2026**
  - **Date Range**: February 1-14, 2026
  - **Days Remaining**: 10 days
  - **Effects Applied**: `crush_system_enabled`
  - **Game Features**:
    - Secret admirer system
    - Heart currency exchange
    - Crush confession mechanics
    - Special Valentine's-themed dialogue
  - **Automatic Management**: Will auto-deactivate on February 15

### Upcoming Events

- **Easter 2026** - April 3-5 (Easter Sunday is April 5)
  - Effect: `egg_hunt_enabled`
  - Features: Egg hunting minigame, spring-themed content
- **21 Days of the Breeze 2026** - December 1-21
  - Effect: `breeze_event_enabled`
  - Features: Holiday celebration, winter activities

---

## Checking System State via `/operator` Command

### Command Syntax

```
/operator system status [section]
```

### Available Sections

#### 1. View All System State

```
/operator system status
```

**Output Shows:**

```
📋 PLATFORM STATE SUMMARY
════════════════════════════════════════════

🌍 ACTIVE SEASON
  Winter 2026 (Dec 21 - Mar 19)
  Days Remaining: 44
  Effects: xp_reset, persona_overlay, tone_shift

💕 ACTIVE EVENTS
  Valentine's Day 2026 (Feb 1-14)
    Days Remaining: 10
    Effect: crush_system_enabled
    Status: Locked in (auto-deactivate on Feb 15)

🥚 UPCOMING EVENTS
  Easter 2026: Starts Apr 3 (58 days)
  21 Days of the Breeze: Starts Dec 1 (331 days)

📅 SYSTEM JOBS
  ✅ season_rollover: Daily at 00:00 UTC
  ✅ event_lifecycle: Daily at 00:00 UTC
  ✅ unified_content_dispatcher: Every 60s

✅ All systems operational
```

#### 2. View Season Details

```
/operator system status seasons
```

**Output Shows:**

```
🌍 SEASONAL CYCLE (2026)

Winter 2026
  Status: ✅ ACTIVE
  Date Range: Dec 21, 2025 - Mar 19, 2026
  Days In: 45 | Days Remaining: 44
  Effects: xp_reset, persona_overlay, tone_shift
  XP Reset Applied: Yes
  Canon Reference: Winter theme (reflection, gathering)

Spring 2026
  Status: ⏸️ UPCOMING
  Date Range: Mar 20 - Jun 20
  Days Until: 45
  Effects: [awaiting Spring transition]
  Features: Growth, renewal, awakening

Summer 2026
  Status: ⏸️ UPCOMING
  Date Range: Jun 21 - Sep 21

Fall 2026
  Status: ⏸️ UPCOMING
  Date Range: Sep 22 - Dec 20
```

#### 3. View Event Details

```
/operator system status events
```

**Output Shows:**

```
📅 EVENT SCHEDULE (2026)

Valentine's Day 2026
  Status: ✅ ACTIVE (4/14 days)
  Date Range: Feb 1-14, 2026
  Effect: crush_system_enabled
  Auto-Management: YES (auto-deactivates Feb 15)
  Game Features:
    • Secret admirer confessions
    • Heart currency rewards
    • Special crush dialogue
  Last Started: [timestamp]

Easter 2026
  Status: ⏸️ UPCOMING (58 days until)
  Date Range: Apr 3-5, 2026 (Good Friday - Easter Sunday)
  Effect: egg_hunt_enabled
  Auto-Management: YES
  Game Features:
    • Egg hunt exploration
    • Easter-themed puzzles
    • Special seasonal content

21 Days of the Breeze 2026
  Status: ⏸️ UPCOMING (331 days until)
  Date Range: Dec 1-21, 2026
  Effect: breeze_event_enabled
  Auto-Management: YES
  Game Features:
    • Holiday celebration activities
    • Winter-themed minigames
```

#### 4. View Active Effects

```
/operator system status effects
```

**Output Shows:**

```
⚙️ ACTIVE EFFECTS

SEASON EFFECTS (Winter 2026):
  ✅ xp_reset: Enabled
     └─ XP reset on season transition
  ✅ persona_overlay: Enabled
     └─ Current: "cozy_ceremonial"
  ✅ tone_shift: Enabled
     └─ Dialogue tone adjusted for winter

EVENT EFFECTS (Valentine's Day 2026):
  ✅ crush_system_enabled: Enabled
     └─ Secret admirer system active
     └─ Heart economy active
     └─ Crush confessions available

BACKGROUND JOBS:
  ✅ season_rollover: Enabled (Daily 00:00 UTC)
  ✅ event_lifecycle: Enabled (Daily 00:00 UTC)
  ✅ unified_content_dispatcher: Enabled (Every 60s)
```

---

## How the System Works: No Implicit Actions

### Clear Explicit Workflow

The event and season system is **explicit and transparent** - nothing happens without documented steps:

#### 1. Season Transitions (Automatic)

```
TRIGGER: Daily at 00:00 UTC (season_rollover job)
  ├─ Check: Is today's date past the current season's end_at?
  └─ If YES:
      ├─ STEP 1: Find the season for today's date
      ├─ STEP 2: Call activate_state(new_season_id)
      │          └─ Deactivates old season, activates new season
      ├─ STEP 3: Reset seasonal XP for all guilds
      ├─ STEP 4: Call record_season_transition_event()
      │          └─ Queues announcement for daily scheduled time (e.g., 09:00 UTC)
      ├─ STEP 5: Announcement is generated by unified_content_dispatcher
      ├─ STEP 6: Announcement delivered to all discord channels
      └─ AUDIT: Logged in system with timestamp and operator=system:scheduler
```

#### 2. Event Lifecycle (Automatic)

```
TRIGGER: Daily at 00:00 UTC (event_lifecycle job)
  ├─ LOOP: For each event in system_state:
  │   ├─ Check: Is today ≥ event.start_at AND today ≤ event.end_at?
  │   │
  │   ├─ If YES and event.active = FALSE:
  │   │   ├─ STEP 1: Call activate_state(event_id)
  │   │   ├─ STEP 2: Apply effects to the event
  │   │   ├─ STEP 3: Call record_event_start()
  │   │   ├─ STEP 4: Queue announcement for daily scheduled time
  │   │   └─ AUDIT: Logged with operator=system:event_lifecycle
  │   │
  │   ├─ If NO and event.active = TRUE:
  │   │   ├─ STEP 1: Call deactivate_state(event_id)
  │   │   ├─ STEP 2: Remove effects
  │   │   ├─ STEP 3: Call record_event_end()
  │   │   ├─ STEP 4: Queue announcement for daily scheduled time
  │   │   └─ AUDIT: Logged with operator=system:event_lifecycle
  │   │
  │   └─ Else: No action (event correctly active/inactive)
  │
  └─ All announcements scheduled for next daily time (e.g., 09:00 UTC)
     → NOT immediate
     → All announcements go through unified_content_dispatcher
     → Consistent delivery across all guilds
```

#### 3. Announcement Delivery (Automatic)

```
TRIGGER: Scheduled time (unified_content_dispatcher every 60s)
  ├─ QUERY: Find all content items where:
  │         content_type = "event" OR "season"
  │         lifecycle_state = "draft"
  │         scheduled_at ≤ now
  │
  ├─ PHASE 1 - Generation:
  │   ├─ For each item:
  │   ├─ Call LLM to generate announcement text
  │   ├─ Update lifecycle_state = "generated"
  │   └─ Store generated_content
  │
  ├─ PHASE 2 - Delivery:
  │   ├─ For each guild:
  │   ├─ Post announcement to configured channel
  │   ├─ Update lifecycle_state = "delivered"
  │   └─ Record delivery timestamp
  │
  └─ PHASE 3 - Cleanup:
      ├─ Archive delivered items
      └─ Move to history collection
```

### No Hidden/Implicit Actions

🚫 **What does NOT happen automatically:**

- Effects are NOT applied without state activation
- Events are NOT hidden from view
- Announcements are NOT sent immediately
- Seasons are NOT changed without explicit activation
- No background data modifications occur outside documented jobs

---

## Event Cycle Definition (Canon Events for 2026)

### Overview

Canon events are platform-wide events that are **automatically managed by the system**. They activate and deactivate based on date boundaries with no operator intervention required.

### Canon Event Template

```
state_id: {key}-{year}
state_type: "event"
key: {lowercase_identifier}
label: {Display name}
active: {true|false}
start_at: {ISO8601 UTC datetime}
end_at: {ISO8601 UTC datetime}
effects: {map of effect_key: {value, scoped_to}}
metadata:
  created_by: "system:canon"
  created_at: {ISO8601 UTC datetime}
  is_canon: true
  description: "Canon event definition for platform"
```

### 2026 Canon Events

#### Event #1: Valentine's Day

```
STATE ID: valentines-2026
LABEL: Valentine's Day 2026
DATE RANGE: February 1-14, 2026 (14 days)
EFFECTS:
  - crush_system_enabled: true
GAME FEATURES:
  - Secret admirer confessions
  - Heart currency rewards
  - Special Valentine's-themed dialogue
  - Crush interaction mechanics
AUTO-MANAGEMENT: YES
  - Activates: February 1, 2026 at 00:00 UTC
  - Deactivates: February 15, 2026 at 00:00 UTC
  - Announcement: "Valentine's Day begins!" (Feb 1 at 09:00 UTC)
  - Announcement: "Valentine's Day ends!" (Feb 15 at 09:00 UTC)
DATABASE LOCATION: system_state collection
OPERATOR OVERRIDE: Can be manually deactivated via /operator command
```

#### Event #2: Easter

```
STATE ID: easter-2026
LABEL: Easter 2026
DATE RANGE: April 3-5, 2026 (Good Friday to Easter Sunday)
  - Good Friday: April 3
  - Easter Sunday: April 5
EFFECTS:
  - egg_hunt_enabled: true
GAME FEATURES:
  - Egg hunting exploration
  - Easter egg puzzles
  - Special seasonal content
  - Bunny-themed dialogue
AUTO-MANAGEMENT: YES
  - Activates: April 3, 2026 at 00:00 UTC
  - Deactivates: April 6, 2026 at 00:00 UTC
  - Announcement: "Easter season begins!" (Apr 3 at 09:00 UTC)
  - Announcement: "Easter season ends!" (Apr 6 at 09:00 UTC)
DATABASE LOCATION: system_state collection
OPERATOR OVERRIDE: Can be manually deactivated via /operator command
NOTE: Easter date is computed annually; 2026 Easter Sunday is April 5
```

#### Event #3: 21 Days of the Breeze

```
STATE ID: 21_days_breeze-2026
LABEL: 21 Days of the Breeze 2026
DATE RANGE: December 1-21, 2026 (21 days)
EFFECTS:
  - breeze_event_enabled: true
GAME FEATURES:
  - Holiday celebration activities
  - Winter-themed minigames
  - Special seasonal rewards
  - Festive dialogue
AUTO-MANAGEMENT: YES
  - Activates: December 1, 2026 at 00:00 UTC
  - Deactivates: December 22, 2026 at 00:00 UTC
  - Announcement: "21 Days of the Breeze begins!" (Dec 1 at 09:00 UTC)
  - Announcement: "21 Days of the Breeze ends!" (Dec 22 at 09:00 UTC)
DATABASE LOCATION: system_state collection
OPERATOR OVERRIDE: Can be manually deactivated via /operator command
CANON NOTES: Celebrates winter season and approaching new year
```

---

## Operator Controls

### Manual Event Management

While events are auto-managed, operators can manually control them for testing or special circumstances:

#### Manually Activate an Event (Before Its Date)

```
/operator system event activate {event_id}

Example:
/operator system event activate easter-2026

Result:
✅ Easter 2026 manually activated
  Announcement queued for next scheduled time (09:00 UTC)
```

#### Manually Deactivate an Event (Before Its End Date)

```
/operator system event deactivate {event_id} [reason]

Example:
/operator system event deactivate valentines-2026 "Testing end-of-event flow"

Result:
✅ Valentine's Day 2026 deactivated
  Reason: Testing end-of-event flow
  Announcement queued for next scheduled time
```

#### View Event Status

```
/operator system event status {event_id}

Example:
/operator system event status valentines-2026

Result:
💕 Valentine's Day 2026
  State: ACTIVE
  Date Range: Feb 1-14, 2026
  Days In: 4 of 14
  Effect: crush_system_enabled
  Auto-Deactivates: Feb 15
  Announcement Status: [Pending/Sent/Scheduled]
```

---

## Job Status & Management

### Background Jobs

Three critical jobs manage the platform state:

| Job                            | Schedule        | Purpose                                                  | Failure Impact                          |
| ------------------------------ | --------------- | -------------------------------------------------------- | --------------------------------------- |
| **season_rollover**            | Daily 00:00 UTC | Detect season boundaries, activate new seasons, reset XP | Seasons stuck until manual intervention |
| **event_lifecycle**            | Daily 00:00 UTC | Detect event boundaries, auto-activate/deactivate        | Events stuck at boundaries              |
| **unified_content_dispatcher** | Every 60s       | Generate and deliver announcements                       | Announcements delayed/stuck             |

### View Job Status

```
/operator system jobs

Output:
📅 BACKGROUND JOBS

season_rollover
  Status: ✅ ENABLED
  Last Run: 2026-02-04 00:00:15 UTC
  Next Run: 2026-02-05 00:00:00 UTC
  Recent Runs: ✅ ✅ ✅ (last 3 successful)

event_lifecycle
  Status: ✅ ENABLED
  Last Run: 2026-02-04 00:00:45 UTC
  Next Run: 2026-02-05 00:00:00 UTC
  Recent Runs: ✅ (first run since deployment)

unified_content_dispatcher
  Status: ✅ ENABLED
  Last Run: 2026-02-04 20:58:00 UTC
  Next Run: 2026-02-04 20:59:00 UTC
  Recent Runs: ✅ ✅ ✅ ✅ ✅ (continuous)
```

### Manually Trigger a Job (For Testing)

```
/operator system jobs run {job_id}

Example:
/operator system jobs run event_lifecycle

Result:
📅 Running event_lifecycle job...
  Checking event boundaries
  Result: All events correctly active/inactive
✅ Job completed successfully in 245ms
```

---

## Troubleshooting

### Valentine's Event Not Active When It Should Be

**Check 1: Is the event in the database?**

```
/operator system event status valentines-2026
```

Should show: **ACTIVE**

**Check 2: Is event_lifecycle job enabled?**

```
/operator system jobs
```

Look for `event_lifecycle`: Should show **ENABLED**

**Check 3: When did event_lifecycle last run?**

```
/operator system jobs
```

Look for `event_lifecycle` → `Last Run`

- If < 24 hours ago: Job is running, wait for next cycle
- If > 24 hours ago: Job may be stuck, manually trigger with `/operator system jobs run event_lifecycle`

**Check 4: Are the effects being applied?**

```
/operator system status effects
```

Should show: `crush_system_enabled: ✅ Enabled`

### Announcement Not Sent for Event

**Check 1: Is announcement queued?**

```
/operator system announcements pending
```

Should show event announcement with `status: scheduled`

**Check 2: Has scheduled time passed?**

```
/operator system announcements pending
```

Check `scheduled_at` time:

- If future: Wait until that time
- If past: Check dispatcher logs for errors

**Check 3: Is dispatcher running?**

```
/operator system jobs
```

Look for `unified_content_dispatcher`:

- If disabled: Enable it
- If last run > 2min ago: May be stuck

---

## Production Checklist

Before going live with events, verify:

- [ ] Active season is marked as `active: true`
- [ ] Valentine's event exists and has `active: true`
- [ ] Easter and 21 Days events exist (can be `active: false` until their dates)
- [ ] `season_rollover` job is ENABLED
- [ ] `event_lifecycle` job is ENABLED
- [ ] `unified_content_dispatcher` job is ENABLED
- [ ] Daily announcement schedule is set (default: 09:00 UTC)
- [ ] All required effects exist in `effects_registry`
- [ ] Operator commands respond correctly to `/operator system status`
- [ ] Test manual event activation/deactivation works
- [ ] Verify announcements are queued (not immediate)

---

## Related Documentation

- [Event Lifecycle System](EVENT_LIFECYCLE_SYSTEM.md) - Technical architecture and code
- [World Announcements System](WORLD_ANNOUNCEMENTS_SYSTEM.md) - Announcement system architecture
- [Scheduler Architecture](../runtime/SCHEDULER_ARCHITECTURE.md) - Background jobs and execution
- [System State Management](../reference/SYSTEM_STATE.md) - State activation and effects
