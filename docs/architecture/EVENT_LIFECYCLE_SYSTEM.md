# Event Lifecycle System

## Overview

The Event Lifecycle System automatically starts and ends platform-wide events based on their date boundaries. It works in tandem with the World Announcements System to notify users when events begin and end.

## Architecture

### Components

1. **Event Lifecycle Job** (`system.event_lifecycle`)
   - Runs daily at midnight UTC (configurable)
   - Checks all events in `system_state` collection
   - Auto-activates events when `start_at` is reached
   - Auto-deactivates events when `end_at` is passed
   - Records event transitions for announcement

2. **Event Recording** (`events_lifecycle.py`)
   - `record_event_start()`: Queues event start announcement
   - `record_event_end()`: Queues event end announcement
   - Creates content items scheduled for daily announcement time
   - Follows same pattern as season transitions

3. **Unified Content Dispatcher** (`unified_content_dispatcher`)
   - Processes event announcements like any other content
   - Generates announcement text via LLM
   - Delivers to Discord channels at scheduled time

### Supported Events

| Event                     | State ID Pattern      | Date Range                  | Effects                | Features                       |
| ------------------------- | --------------------- | --------------------------- | ---------------------- | ------------------------------ |
| **Valentine's Day**       | `valentines-YYYY`     | Feb 1-14                    | `crush_system_enabled` | Secret admirers, heart economy |
| **Easter**                | `easter-YYYY`         | Good Friday - Easter Sunday | `egg_hunt_enabled`     | Egg hunting minigame           |
| **21 Days of the Breeze** | `21_days_breeze-YYYY` | Dec 1-21                    | `breeze_event_enabled` | Holiday celebration            |

## Flow Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ AUTOMATIC EVENT LIFECYCLE                                       │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 1. Event Lifecycle Job (Daily at 00:00)  ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      ├─> For each event in system_state:
                      │   ├─> Check if today ∈ [start_at, end_at]
                      │   ├─> If should be active but isn't:
                      │   │   ├─> activate_state(event_id)
                      │   │   └─> record_event_start()
                      │   └─> If should be inactive but is:
                      │       ├─> deactivate_state(event_id)
                      │       └─> record_event_end()
                      │
                      ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 2. record_event_start/end()              ┃
        ┃    (events_lifecycle.py)                 ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      ├─> Get daily announcement schedule
                      ├─> Calculate next scheduled time
                      ├─> For each guild:
                      │   └─> create_announcement_for_delivery()
                      │       ├─> content_type: "event"
                      │       ├─> trigger_type: "scheduled"
                      │       ├─> scheduled_at: next daily time
                      │       └─> lifecycle_state: "draft"
                      │
                      ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 3. Content Items Created                 ┃
        ┃    (content_delivery_items)              ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      │   Document per guild:
                      │   {
                      │     "content_type": "event",
                      │     "trigger_type": "scheduled",
                      │     "scheduled_at": "2026-02-01T09:00:00Z",
                      │     "lifecycle_state": "draft",
                      │     "context_refs": {
                      │       "event_type": "event_start",
                      │       "event_id": "valentines-2026"
                      │     }
                      │   }
                      │
                      ▼
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ 4. Unified Content Dispatcher            ┃
        ┃    (runs every 60s)                      ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                      │
                      ├─> Phase 1: Check scheduled_at <= now
                      ├─> Phase 2: Generate (LLM call)
                      ├─> Phase 3: Deliver (Discord channels)
                      └─> Phase 4: Cleanup (archive)
```

## Database Schema

### system_state Collection (Event Documents)

```json
{
  "_id": ObjectId("..."),
  "state_id": "valentines-2026",
  "state_type": "event",
  "key": "valentines",
  "label": "Valentine's Day 2026",
  "active": false,
  "start_at": ISODate("2026-02-01T00:00:00Z"),
  "end_at": ISODate("2026-02-14T23:59:59Z"),
  "effects": {
    "crush_system_enabled": {
      "value": true,
      "scoped_to": null
    }
  },
  "metadata": {
    "created_by": "operator:123456789",
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

### scheduler_jobs Collection (Event Lifecycle Job)

```json
{
  "_id": ObjectId("..."),
  "job_type": "system.event_lifecycle",
  "enabled": true,
  "schedule": {
    "type": "daily",
    "time": "00:00",
    "timezone": "UTC"
  },
  "last_run_at": ISODate("2026-02-01T00:00:00Z"),
  "next_run_at": ISODate("2026-02-02T00:00:00Z"),
  "created_at": ISODate("2026-01-15T10:00:00Z"),
  "updated_at": ISODate("2026-02-01T00:00:00Z"),
  "description": "Platform-wide event auto-start/auto-end based on date boundaries"
}
```

### content_delivery_items Collection (Event Announcements)

```json
{
  "_id": ObjectId("..."),
  "guild_id": 547471286801268777,
  "content_type": "event",
  "trigger_type": "scheduled",
  "title": "Event Start: valentines-2026",
  "description": "",
  "generated_content": "🌹 Love is in the air! Valentine's Day has begun...",
  "lifecycle_state": "generated",
  "scheduled_at": ISODate("2026-02-01T09:00:00Z"),
  "generated_at": ISODate("2026-02-01T08:30:00Z"),
  "context_refs": {
    "event_type": "event_start",
    "event_id": "valentines-2026",
    "operator_id": null,
    "reason": "Event boundary crossed - auto-start"
  },
  "created_at": ISODate("2026-02-01T00:05:00Z"),
  "updated_at": ISODate("2026-02-01T08:30:00Z")
}
```

## Key Files

### Job Handlers

- [event_lifecycle.py](../abby_core/discord/cogs/system/jobs/event_lifecycle.py) - Event boundary detection and activation
- [job_handlers.py](../abby_core/discord/cogs/system/job_handlers.py) - Handler registration
- [registry.py](../abby_core/discord/cogs/system/registry.py) - Job metadata

### Event Recording

- [events_lifecycle.py](../abby_core/services/events_lifecycle.py) - Event recording functions
  - `record_event_start()`: Queue event start announcement
  - `record_event_end()`: Queue event end announcement
  - `_get_daily_world_schedule()`: Get announcement schedule from system config
  - `_next_daily_world_dt()`: Calculate next scheduled announcement time

### System State

- [system_state.py](../abby_core/system/system_state.py) - Event activation/deactivation
  - `activate_state()`: Enable event and apply effects
  - `deactivate_state()`: Disable event and remove effects
  - `list_all_states()`: Query events by type
- [state_registry.py](../abby_core/system/state_registry.py) - Event templates
  - `APPROVED_EVENT_TEMPLATES`: Valentine's, Easter, 21 Days definitions
  - `_compute_easter_sunday()`: Calculate Easter date

### Content Dispatch

- [unified_content_dispatcher.py](../abby_core/discord/cogs/system/jobs/unified_content_dispatcher.py) - Announcement delivery
- [content_delivery.py](../abby_core/services/content_delivery.py) - Content item CRUD

## Configuration

### System Configuration (system_config collection)

```json
{
  "system_jobs": {
    "announcements": {
      "daily_world_announcements": {
        "enabled": true,
        "schedule": {
          "time": "09:00",
          "timezone": "UTC"
        }
      }
    }
  }
}
```

**Note:** Event announcements use the same daily schedule as season transitions. They are NOT immediate - they queue for the next scheduled announcement time.

## Operations

### Creating a New Event

Using operator panel:

```
/operator system create-event
Event ID: easter-2026
Label: Easter 2026
Start Date: 2026-04-17
End Date: 2026-04-19
Effects: egg_hunt_enabled=true
```

This creates the event in `system_state` but does NOT activate it. The event will auto-activate on April 17, 2026 at midnight UTC.

### Manually Activating an Event

```python
from abby_core.system.system_state import activate_state
from abby_core.services.events_lifecycle import record_event_start

# Activate event
activate_state("valentines-2026")

# Queue announcement
record_event_start("valentines-2026", trigger="operator", operator_id=123456789, reason="Manual activation for testing")
```

### Manually Deactivating an Event

```python
from abby_core.system.system_state import deactivate_state
from abby_core.services.events_lifecycle import record_event_end

# Deactivate event
deactivate_state("valentines-2026", operator_id="operator:123456789")

# Queue announcement
record_event_end("valentines-2026", trigger="operator", operator_id=123456789, reason="Manual deactivation")
```

### Checking Event Status

```python
from abby_core.system.system_state import get_state_by_id

event = get_state_by_id("valentines-2026")
print(f"Active: {event['active']}")
print(f"Start: {event['start_at']}")
print(f"End: {event['end_at']}")
print(f"Effects: {event['effects']}")
```

### Viewing Pending Announcements

```python
from abby_core.services.events_lifecycle import get_pending_announcements

# Get all event announcements
event_announcements = get_pending_announcements(event_type="event_start")
for announcement in event_announcements:
    print(f"Guild {announcement['guild_id']}: {announcement['title']} at {announcement['scheduled_at']}")
```

## Troubleshooting

### Event didn't auto-start

**Check 1: Is the event in system_state?**

```python
from abby_core.system.system_state import get_state_by_id
event = get_state_by_id("valentines-2026")
print("Event exists:", event is not None)
```

**Check 2: Is the event_lifecycle job enabled?**

```python
from abby_core.database.mongodb import get_database
db = get_database()
job = db.scheduler_jobs.find_one({"job_type": "system.event_lifecycle"})
print("Job enabled:", job["enabled"] if job else "Job not found")
```

**Check 3: Has the job run recently?**

```python
job = db.scheduler_jobs.find_one({"job_type": "system.event_lifecycle"})
print("Last run:", job["last_run_at"])
print("Next run:", job["next_run_at"])
```

**Check 4: Are we past the start date?**

```python
from datetime import datetime
event = get_state_by_id("valentines-2026")
now = datetime.utcnow()
print(f"Now: {now}")
print(f"Start: {event['start_at']}")
print(f"Should be active: {event['start_at'] <= now <= event['end_at']}")
```

### Event announcement not delivered

**Check 1: Is announcement queued?**

```python
from abby_core.services.content_delivery import get_content_items
items = get_content_items(content_type="event", lifecycle_state="draft")
print(f"Queued announcements: {len(items)}")
for item in items:
    print(f"  - {item['title']} scheduled for {item['scheduled_at']}")
```

**Check 2: Has scheduled time passed?**

```python
from datetime import datetime
items = get_content_items(content_type="event")
now = datetime.utcnow()
for item in items:
    scheduled = item.get("scheduled_at")
    print(f"{item['title']}: scheduled={scheduled}, now={now}, ready={scheduled <= now if scheduled else 'N/A'}")
```

**Check 3: Is unified_content_dispatcher running?**

```bash
# Check logs for dispatcher activity
tail -f logs/abby.jsonl | grep "unified_content_dispatcher"
```

### Event effects not working

**Check 1: Is event active?**

```python
from abby_core.system.system_state import get_state_by_id
event = get_state_by_id("valentines-2026")
print("Active:", event["active"])
print("Effects:", event["effects"])
```

**Check 2: Are effects registered?**

```python
from abby_core.system.effects_registry import is_effect_active
print("crush_system_enabled:", is_effect_active("crush_system_enabled"))
```

**Check 3: Check game logic**

- Valentine hearts: `abby_core/discord/cogs/events/valentine_hearts.py` checks `is_effect_active("crush_system_enabled")`
- Easter eggs: `abby_core/discord/cogs/events/easter_eggs.py` checks `is_effect_active("egg_hunt_enabled")`

## Testing

### Test Event Lifecycle Detection

```python
# Create a test event with near-future dates
from datetime import datetime, timedelta
from abby_core.system.system_state import create_custom_state

tomorrow = datetime.utcnow() + timedelta(days=1)
day_after = tomorrow + timedelta(days=1)

create_custom_state(
    state_id="test-event-2026",
    state_type="event",
    key="test",
    label="Test Event 2026",
    start_at=tomorrow,
    end_at=day_after,
    effects={"test_event_enabled": {"value": True, "scoped_to": None}},
    operator_id="operator:test"
)

# Wait for event_lifecycle job to run (midnight UTC)
# Check if event was activated
from abby_core.system.system_state import get_state_by_id
event = get_state_by_id("test-event-2026")
print("Active after start:", event["active"])

# Check if announcement was queued
from abby_core.services.content_delivery import get_content_items
items = get_content_items(content_type="event", context_refs__event_id="test-event-2026")
print("Announcements:", len(items))
```

### Test Manual Event Activation

```python
from abby_core.system.system_state import activate_state, get_state_by_id
from abby_core.services.events_lifecycle import record_event_start

# Activate
activate_state("test-event-2026")
event = get_state_by_id("test-event-2026")
print("Active:", event["active"])

# Queue announcement
content_id = record_event_start("test-event-2026", trigger="operator", operator_id=123456789)
print("Content ID:", content_id)

# Check content item
from abby_core.services.content_delivery import get_content_item_by_id
item = get_content_item_by_id(content_id)
print("Scheduled for:", item["scheduled_at"])
```

## Migration Notes

### From Manual Event Management

Before the lifecycle system:

- Operators manually activated/deactivated events
- Announcements were immediate or not sent
- Easy to forget to enable/disable events

After the lifecycle system:

- Events automatically start/end based on date boundaries
- Announcements are scheduled and consistent
- No operator intervention needed

### Compatibility

- Existing event documents in `system_state` are compatible
- Just ensure they have `start_at` and `end_at` fields
- The `active` field will be managed automatically

## See Also

- [World Announcements System](WORLD_ANNOUNCEMENTS_SYSTEM.md) - Season transition and announcement architecture
- [Scheduler Architecture](../runtime/SCHEDULER_ARCHITECTURE.md) - Background job execution
- [System State Management](../reference/SYSTEM_STATE.md) - State activation and effects
- [Operator Panel Guide](../guides/OPERATOR_PANEL.md) - Event creation and management
