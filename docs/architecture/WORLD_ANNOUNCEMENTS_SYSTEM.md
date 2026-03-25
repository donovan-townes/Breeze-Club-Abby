# World Announcements & Season Transition System

## Overview

The world announcements system automatically broadcasts system-wide changes (like season transitions) to all guilds. This document clarifies the architecture after consolidation into the unified content dispatcher.

## Architecture

### Components

1. **Season Rollover Job** (`system.season_rollover`)
   - Runs daily to check for season boundary crossings
   - Activates new seasons in `system_state` collection
   - Resets seasonal XP for all users across all guilds
   - Triggers announcement creation

2. **Event Recording** (`events_lifecycle.py`)
   - Records season transitions as content items
   - Creates one entry per guild in `content_delivery_items`
   - Marks items for immediate processing

3. **Unified Content Dispatcher** (`unified_content_dispatcher`)
   - Runs every 60 seconds
   - Processes all announcement types through 3 phases
   - Handles generation, delivery, and cleanup

### Flow Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ AUTOMATIC SEASON TRANSITION                                    │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 1. Season Rollover Job (Daily at 00:00) ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      ├─> Check current date vs active season
                      ├─> If outside boundaries:
                      │   ├─> activate_state(new_season_id)
                      │   ├─> reset_seasonal_xp(all_guilds)
                      │   └─> on_season_transition_success()
                      │
                      ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 2. Record Event (events_lifecycle.py)   ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      └─> record_season_transition_event()
                          └─> Creates in content_delivery_items:
                              - guild_id: <each guild>
                              - content_type: "system"
                              - trigger_type: "immediate"
                              - lifecycle_state: "draft"
                              - generation_status: "pending"
                              - title: "Season Transition: winter → spring"
                              - description: "" (empty, to be generated)
                      │
                      ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 3. Unified Content Dispatcher (every 60s)┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      ├─> PHASE 1: GENERATION
                      │   ├─> Query: lifecycle_state="draft"
                      │   ├─> For each system event:
                      │   │   ├─> prepare_season_transition_announcement()
                      │   │   ├─> generate_season_announcement() (LLM call)
                      │   │   └─> Mark: lifecycle_state="generated"
                      │   └─> Rate limited: 10 items/run max
                      │
                      ├─> PHASE 2: DELIVERY
                      │   ├─> Query: lifecycle_state="generated"
                      │   ├─> For each guild:
                      │   │   ├─> Build embed with announcement
                      │   │   ├─> Send to announcement channel
                      │   │   └─> Mark: lifecycle_state="delivered"
                      │   └─> Rate limited: 20 items/run max
                      │
                      └─> PHASE 3: CLEANUP
                          ├─> Query: lifecycle_state="delivered",
                          │          created_at < (now - 7 days)
                          └─> Archive or delete old items

┌────────────────────────────────────────────────────────────────┐
│ RESULT: All guilds receive season announcement within ~60s     │
└────────────────────────────────────────────────────────────────┘
```

## Manual Season Transitions

Operators can force a season change via `/operator state force-season`:

```
Manual Transition
    │
    └─> ForceSeasonModal.on_submit()
        ├─> activate_state(new_season_id, operator_id)
        ├─> reset_seasonal_xp(all_guilds)
        └─> on_season_transition_success(trigger="operator")
            └─> Same flow as automatic (creates content items)
```

## Key Files

### Job Handlers

- `abby_core/discord/cogs/system/jobs/season_rollover.py` - Season boundary detection
- `abby_core/discord/cogs/system/jobs/unified_content_dispatcher.py` - Content processing
- `abby_core/discord/cogs/system/job_handlers.py` - Handler registration

### Event Recording

- `abby_core/services/events_lifecycle.py` - Event recording and announcement preparation
- `abby_core/services/content_delivery.py` - Content item CRUD operations

### System State

- `abby_core/system/system_state.py` - Season definitions and state management
- `abby_core/database/collections/system_state.py` - Database operations

### Announcement Dispatch

- `abby_core/services/announcement_dispatcher.py` - Lifecycle state transitions
- `abby_core/discord/adapters/scheduler_bridge.py` - Job execution bridge

## Database Schema

### content_delivery_items Collection

```json
{
  "_id": ObjectId,
  "guild_id": 547471286801268777,
  "content_type": "system",
  "trigger_type": "immediate",
  "title": "Season Transition: winter-2026 → spring-2026",
  "description": "",  // Empty until generated
  "payload": {
    "old_season_id": "winter-2026",
    "new_season_id": "spring-2026",
    "trigger": "automatic"
  },
  "context_refs": {
    "operator_id": null,
    "reason": null,
    "event_type": "season_transition"
  },
  "idempotency_key": "season_transition:winter-2026:spring-2026:1738627200",
  "priority": 0,
  "delivery_channel_id": null,  // Resolved from guild config
  "delivery_roles": [],
  "lifecycle_state": "draft",
  "generation_status": "pending",
  "delivery_status": "pending",
  "created_at": "2026-02-04T08:00:00Z",
  "updated_at": "2026-02-04T08:00:00Z",
  "generated_at": null,
  "delivered_at": null,
  "generated_message": null,
  "delivery_result": null
}
```

### Lifecycle States

```
draft → generated → delivered → archived
  ↓         ↓           ↓
error    error      error
  ↓         ↓           ↓
retry    retry      retry
```

## Configuration

### Guild Configuration (scheduling.jobs.system)

```json
{
  "scheduling": {
    "jobs": {
      "system": {
        "daily_world_announcements": {
          "enabled": true,
          "time": "08:00",
          "last_executed_at": "2026-02-04T08:00:00Z"
        }
      }
    }
  }
}
```

**Note:** `daily_world_announcements` is a **legacy job identifier**. It's kept for backward compatibility but does nothing. The actual work happens in `unified_content_dispatcher`.

## Legacy Job: system.announcements.daily_world_announcements

### Status: DEPRECATED

This job identifier still exists in configurations but has been replaced by the unified content dispatcher. The handler is registered as a no-op to prevent warnings.

### Why It Was Deprecated

1. **Fragmentation:** Announcements were handled by multiple separate jobs
2. **Race Conditions:** Generation and delivery weren't atomic
3. **No Lifecycle Management:** Items couldn't track state transitions
4. **Limited Visibility:** Hard to audit what was sent when

### Migration

The new system:

- ✅ Single pipeline for all announcement types
- ✅ Atomic state transitions (draft → generated → delivered)
- ✅ Rate limiting to prevent Discord API throttling
- ✅ Idempotent (safe to run every minute)
- ✅ Full audit trail (timestamps, operator IDs, delivery results)

### Removing Legacy Config (Optional)

To clean up old configurations:

```python
from abby_core.database.collections.guild_configuration import get_all_guild_configs
from abby_core.database.mongodb import get_database

db = get_database()
guild_config = db["guild_configuration"]

# Remove legacy job config
guild_config.update_many(
    {},
    {"$unset": {"scheduling.jobs.system.daily_world_announcements": ""}}
)
```

**Warning:** This will remove the job from operator panels. Only do this if you're certain no operators rely on the legacy UI.

## Testing Season Transitions

### Manual Test

1. **Force a season change:**

   ```
   /operator state force-season season_id:spring-2026
   ```

2. **Check content_delivery_items:**

   ```python
   from abby_core.services.content_delivery import get_content_delivery_collection
   collection = get_content_delivery_collection()
   items = list(collection.find({"content_type": "system"}).sort("created_at", -1).limit(10))
   ```

3. **Wait for dispatcher:**
   - Within 60 seconds, items should move from `draft` → `generated` → `delivered`

4. **Check Discord:**
   - Announcement should appear in guild announcement channels
   - Check logs for delivery results

### Automated Test Scenarios

1. **Season Boundary Detection:** See `tests/test_season_rollover.py`
2. **Content Generation:** See `tests/test_content_delivery_lifecycle.py`
3. **Unified Dispatcher:** See `tests/test_unified_content_dispatcher.py`

## Troubleshooting

### Warning: "No handler registered for job type: system.announcements.daily_world_announcements"

**Cause:** Legacy job config still references the old job identifier.

**Solution:** This is harmless. The no-op handler prevents the warning. If you want to remove it entirely, clean up guild configs (see "Removing Legacy Config" above).

### Announcements Not Sending

1. **Check content_delivery_items:**

   ```python
   collection.find({"lifecycle_state": "draft"})
   ```

   - If items are stuck in `draft`, check generation logs
   - If items are stuck in `generated`, check delivery logs

2. **Check unified_content_dispatcher logs:**

   ```
   grep "unified_content_dispatcher" logs/abby.jsonl
   ```

3. **Verify guild announcement channel:**
   ```python
   from abby_core.database.collections.guild_configuration import get_guild_config
   config = get_guild_config(guild_id)
   print(config.get("announcement_channel_id"))
   ```

### Season Not Transitioning

1. **Check active season:**

   ```python
   from abby_core.system.system_state import get_active_season
   season = get_active_season()
   print(f"{season.get('state_id')}: {season.get('start_at')} - {season.get('end_at')}")
   ```

2. **Verify season boundaries:**

   ```python
   from datetime import datetime
   now = datetime.utcnow()
   print(f"Current date: {now.date()}")
   print(f"Season period: {season.get('start_at').date()} - {season.get('end_at').date()}")
   ```

3. **Check season_rollover logs:**
   ```
   grep "season_rollover" logs/abby.jsonl
   ```

## Future Enhancements

### Planned Features

- [ ] Multi-language support (localized announcements per guild)
- [ ] Rich embed customization (colors, images, footers)
- [ ] Announcement scheduling (e.g., delay until 8am local time)
- [ ] Retry logic for failed deliveries
- [ ] Operator notification on delivery failures
- [ ] Analytics dashboard (delivery success rate, average latency)

### Possible Extensions

- Webhook-based announcements (for external platforms)
- Template library (pre-written announcement templates)
- A/B testing (different announcement variants)
- User preferences (opt-out of certain announcement types)

## References

- [Content Delivery Lifecycle](../operations/CONTENT_DELIVERY.md)
- [System State Management](../reference/CANONICAL_STATE_MAP.md)
- [Scheduler Architecture](../runtime/SCHEDULER.md)
- [Announcement Dispatcher API](../reference/API_ANNOUNCEMENT_DISPATCHER.md)
