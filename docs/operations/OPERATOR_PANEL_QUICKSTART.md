# Operator Panel: Quick Start Guide

## Your New System Status Dashboard

**Location**: `/operator` → **System** button → **Status** tab (default)

---

## What Changed

### Before

```
/operator
  └─ System
     ├─ Events (management focus)
     ├─ DLQ Inspector
     └─ Metrics Dashboard
```

### Now

```
/operator
  └─ System
     ├─ Status (NEW - View state)
     │  ├─ All Systems
     │  ├─ Seasons
     │  ├─ Events
     │  ├─ Effects
     │  └─ Jobs
     ├─ Event Management (Moved)
     │  ├─ List Upcoming Events
     │  ├─ Create Event
     │  ├─ Preview States
     │  └─ Rollback Operation
     ├─ DLQ Inspector
     └─ Metrics Dashboard
```

---

## Status Dashboard Buttons

### 📋 All Systems (Default View)

Shows complete platform snapshot in one screen:

- ✅ Active season
- ✅ Active events
- ⏸️ Upcoming events
- 📅 Job status

**Use when**: You want a quick health check

---

### 🌍 Seasons

Shows all seasons (past, current, upcoming):

- Season name & dates
- Status (✅ Active or ⏸️ Upcoming)
- Applied effects

**Use when**: You need to check seasonal rotation

---

### 📅 Events

Shows all events with lifecycle status:

- Event name & dates
- Status (✅ Active or ⏸️ Upcoming)
- Applied effects
- Auto-manage flag (always YES)

**Use when**: You need to verify an event is active

---

### ⚙️ Effects

Shows what's currently active in the system:

- Season effects (e.g., crush_system_enabled)
- Event effects (e.g., egg_hunt_enabled)
- Running background jobs

**Use when**: You need to confirm effects are applied

---

### ⚙️ Jobs

Shows background job execution info:

- Job name & status (✅ Enabled/❌ Disabled)
- Schedule (Daily 00:00 UTC or Every 60s)
- Last execution time
- Next execution time

**Use when**: You need to verify jobs are running

---

## Common Workflows

### "Is Valentine's Day active?"

```
1. Click /operator
2. Click System button
3. Status tab is already selected
4. Click Events button
5. Find "Valentine's Day 2026" in the list
6. Check status (✅ ACTIVE = yes, ⏸️ UPCOMING = not yet)
```

### "What effects are currently active?"

```
1. Click /operator → System → Status
2. Click Effects button
3. See all active effects listed by source
```

### "Are the background jobs running?"

```
1. Click /operator → System → Status
2. Click Jobs button
3. Check each job status (should all show ✅ ENABLED)
4. Verify last run times are recent
```

### "Quick system health check"

```
1. Click /operator → System
2. Status tab opens by default
3. Click All Systems button
4. Review in one screen:
   - Active season
   - Active events
   - Job status
```

---

## Key Principles

### No Slash Commands Here

All status commands are now **buttons** accessed from `/operator System Status`:

- ✅ All Systems
- ✅ Seasons
- ✅ Events
- ✅ Effects
- ✅ Jobs

### No Hidden State

Everything is explicit and documented:

- ✅ Database queries are documented
- ✅ Output format is documented
- ✅ All effects are listed
- ✅ All jobs are visible

### Auto-Manage is Automatic

Events automatically manage themselves:

- ✅ No manual intervention needed
- ✅ Activates at start_at date
- ✅ Deactivates at end_at date
- ✅ Announcements auto-queue at 09:00 UTC

---

## Troubleshooting

### "Can't find the Status tab"

- Make sure you're in `/operator → System`
- Click the dropdown that says "Choose system subtab"
- Select "Status" (should be first option)

### "A button isn't working"

- Check if you have operator permissions
- Verify MongoDB connection is working
- Check logs for database errors

### "Event isn't showing as active"

- Click Status → Events
- Find the event in the list
- If shows ⏸️ UPCOMING: Wait until start_at date
- If shows ✅ ACTIVE: It's already active!
- If missing: Event might not be created yet

### "Need to check event dates"

- Click Status → Events
- See all event date ranges
- Or click Status → All Systems for quick overview

---

## Button Layout

```
┌─────────────────────────────────────┐
│ Status | Event Mgmt | DLQ | Metrics │  ← Subtab selector
├─────────────────────────────────────┤
│                                       │
│ [📋 All Systems] [🌍 Seasons]         │ ← Row 0
│ [📅 Events] [⚙️ Effects]              │
│                                       │
│ [⚙️ Jobs]                             │ ← Row 1
│                                       │
└─────────────────────────────────────┘
```

---

## Related Docs

For more details, see:

- [PLATFORM_STATE_OPERATOR_REFERENCE.md](PLATFORM_STATE_OPERATOR_REFERENCE.md) - Complete reference
- [SYSTEM_STATUS_COMMANDS.md](SYSTEM_STATUS_COMMANDS.md) - Command specs
- [VALENTINE_2026_PRODUCTION_STATE.md](VALENTINE_2026_PRODUCTION_STATE.md) - Current state

---

**Last Updated**: February 4, 2026  
**Status**: ✅ Live
