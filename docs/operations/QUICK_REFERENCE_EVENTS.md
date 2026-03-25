# Quick Reference: Event & Season System

## Current Status (Feb 4, 2026)

```
🌍 SEASON:  Winter 2026 (44 days remaining)
💕 EVENT:   Valentine's Day 2026 ✅ ACTIVE (10 days remaining)
📅 JOBS:    All 3 background jobs running ✅
```

---

## Verify System State (Operator Commands)

### Full Status Check

```
/operator system status
```

Shows everything: active season, active events, upcoming events, job status

### Event Status Only

```
/operator system status events
```

Shows all events (active/upcoming) with dates and auto-management info

### Active Effects

```
/operator system status effects
```

Shows all effects currently applied to the platform

### Job Status

```
/operator system status jobs
```

Shows if season_rollover, event_lifecycle, and dispatcher are running

---

## How It Works (Simple Version)

### 1. Events Auto-Manage

- **Every day at 00:00 UTC**: event_lifecycle job checks all event dates
- **If today ≥ start_at AND ≤ end_at**: Event auto-activates
- **If today > end_at**: Event auto-deactivates
- **No operator action needed**

### 2. Announcements Are Scheduled

- **Not immediate**: Events queue announcements for 09:00 UTC daily
- **All guilds together**: Same announcement sent to all Discord channels
- **Automatic generation**: LLM generates the text, dispatcher sends it

### 3. Effects Are Applied

- **Automatic**: When event activates, its effects apply
- **Automatic removal**: When event deactivates, effects are removed
- **No operator action needed**

---

## Valentine's Day Event (Feb 1-14)

```
State:           ✅ ACTIVE
Days In:         4 of 14
Days Remaining:  10
Effect:          crush_system_enabled
Features:        Secret admirers, hearts, confessions
Auto-Ends:       February 15 at 00:00 UTC
```

### Check It's Active

```
/operator system status events
```

Look for: `💕 Valentine's Day 2026` with ✅ ACTIVE status

### Check Effect Is Applied

```
/operator system status effects
```

Look for: `✅ crush_system_enabled: Enabled`

---

## Upcoming Events (2026)

| Event          | Starts | Duration | Days Away |
| -------------- | ------ | -------- | --------- |
| Easter         | Apr 3  | 3 days   | 58        |
| 21 Days Breeze | Dec 1  | 21 days  | 331       |

Both will auto-activate when their dates arrive. No operator action required.

---

## Troubleshooting

### "Valentine's Day event is not active when it should be"

**Step 1**: Check if event exists

```
/operator system status events
```

Should show Valentine's Day listed

**Step 2**: Check if event_lifecycle job has run

```
/operator system status jobs
```

Look for `event_lifecycle` and check `Last Executed`

- Recent (today): Good, job is running
- Old (days ago): May need to manually trigger

**Step 3**: Manually trigger job for testing

```
/operator system jobs run event_lifecycle
```

This forces the job to run immediately

**Step 4**: Check database directly

```bash
# MongoDB
db.system_state.findOne({ state_id: "valentines-2026" })
```

Should show `"active": true`

### "Announcement was not sent"

**Check 1**: Is announcement queued?

```
/operator system announcements pending
```

Should show event announcements waiting

**Check 2**: Has scheduled time passed?

- Default scheduled time: 09:00 UTC
- If current time < 09:00 UTC: Wait until that time
- If current time > 09:00 UTC: Dispatcher should have sent it

**Check 3**: Is dispatcher running?

```
/operator system status jobs
```

Check `unified_content_dispatcher`: should show recent execution time

---

## What's Automatic (No Operator Action)

✅ Event activation on start date
✅ Event deactivation on end date
✅ Effect application/removal
✅ Announcement scheduling
✅ Announcement generation
✅ Announcement delivery

---

## What Requires Operator Action

❌ Creating new events (use `/operator system event create`)
❌ Changing event dates (edit system_state collection directly)
❌ Manually activating event out of sequence (use `/operator system event activate`)
❌ Sending announcement immediately (use `/operator system announcements send-now`)

---

## Key Database Locations

| What                  | Collection             | Query                                               |
| --------------------- | ---------------------- | --------------------------------------------------- |
| Valentine's status    | system_state           | `{state_id: "valentines-2026"}`                     |
| All events            | system_state           | `{state_type: "event"}`                             |
| Active season         | system_state           | `{state_type: "season", active: true}`              |
| event_lifecycle job   | scheduler_jobs         | `{job_type: "system.event_lifecycle"}`              |
| Pending announcements | content_delivery_items | `{content_type: "event", lifecycle_state: "draft"}` |

---

## Emergency Procedures

### If event_lifecycle job fails to run

**1. Check job status**

```
/operator system status jobs
```

**2. Manually trigger**

```
/operator system jobs run event_lifecycle
```

**3. If still broken**

```
/operator system jobs debug
```

Shows detailed logs

**4. Last resort: manually activate**

```
/operator system event activate valentines-2026
```

(This bypasses the job, but doesn't auto-deactivate)

### If announcement doesn't send

**1. Check if queued**

```
/operator system announcements pending
```

**2. Send immediately**

```
/operator system announcements send-now {announcement_id}
```

**3. Check dispatcher**

```
/operator system status jobs
```

If unified_content_dispatcher hasn't run, may need restart

---

## Related Documentation

- Full guide: [PLATFORM_STATE_OPERATOR_REFERENCE.md](PLATFORM_STATE_OPERATOR_REFERENCE.md)
- Commands: [SYSTEM_STATUS_COMMANDS.md](SYSTEM_STATUS_COMMANDS.md)
- Technical: [../architecture/EVENT_LIFECYCLE_SYSTEM.md](../architecture/EVENT_LIFECYCLE_SYSTEM.md)
- Current state: [VALENTINE_2026_PRODUCTION_STATE.md](VALENTINE_2026_PRODUCTION_STATE.md)

---

## Key Principle

**Everything is explicit and logged. No hidden actions.**

- Events defined in database
- Dates locked in system_state
- Jobs run on schedule (visible in logs)
- Announcements queued before delivery
- All changes recorded with operator audit trail

---

## One-Line Summary

Valentine's Day 2026 is active, auto-managed, and will auto-end on Feb 15. Check status anytime with `/operator system status`.
