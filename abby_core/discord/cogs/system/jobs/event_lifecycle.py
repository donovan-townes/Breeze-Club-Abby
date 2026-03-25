"""
Event Lifecycle Job Handler

System job that handles platform-wide event transitions (start/end).

Triggered by: scheduler (daily check for event boundary crossing)
Controlled by: operators via /operator system commands
Effect: Activates/deactivates events based on date boundaries

This is the canonical place where events auto-start and auto-end. When triggered, it:
1. Checks if current date crosses an event boundary (start or end)
2. Activates event at start_at, deactivates at end_at
3. Records event state changes for announcements
4. Emits audit events

Events handled:
- Valentine's Day (Feb 1-14)
- Easter (Good Friday through Easter Sunday, varies)
- 21 Days of the Breeze (Dec 1-21)
- Any operator-created custom events with date boundaries
"""

from datetime import datetime
from typing import Dict, Any, Optional
from abby_core.observability.logging import logging
from abby_core.services.events_lifecycle import record_event_start, record_event_end
from abby_core.system.system_state import (
    get_state_by_id,
    activate_state,
    deactivate_state,
    list_all_states,
)

logger = logging.getLogger(__name__)


async def execute_event_lifecycle(bot, guild_id: int, job_config: Dict[str, Any]):
    """Execute platform-wide event lifecycle checks.
    
    Note: This is a system job, so it runs once globally, not per-guild.
    The guild_id parameter is for consistency but is ignored.
    
    Job Flow:
    1. Get all event states from system_state collection
    2. For each event:
       a. Check if today's date is within [start_at, end_at]
       b. If within bounds and not active: activate + announce start
       c. If outside bounds and active: deactivate + announce end
    3. Log audit trail
    """
    logger.info("[📅] [SYSTEM] Executing platform-wide event lifecycle check...")
    
    try:
        now = datetime.utcnow()
        
        # Get all event states
        all_events = list_all_states("event")
        if not all_events:
            logger.debug("[📅] No events in system_state")
            return
        
        logger.debug(f"[📅] Checking {len(all_events)} event(s) for boundary crossings")
        
        for event in all_events:
            state_id = event.get("state_id")
            if not state_id:
                continue
            
            is_active = event.get("active", False)
            start_at = event.get("start_at")
            end_at = event.get("end_at")
            label = event.get("label", state_id)
            
            # Validate date boundaries
            if not isinstance(start_at, datetime) or not isinstance(end_at, datetime):
                logger.warning(f"[📅] Event {state_id} has invalid date boundaries, skipping")
                continue
            
            # Check if event should be active based on current date
            should_be_active = start_at <= now <= end_at
            
            # Case 1: Event should start (crossed start boundary)
            if should_be_active and not is_active:
                logger.info(f"[📅] Event START detected: {label} ({state_id})")
                logger.info(f"[📅] Date range: {start_at.date()} - {end_at.date()}, Current: {now.date()}")
                
                if activate_state(state_id, operator_id="system:event_lifecycle"):
                    logger.info(f"[✅] Event activated: {state_id}")
                    
                    # Record event start for announcement
                    await on_event_start(state_id, trigger="automatic")
                else:
                    logger.error(f"[❌] Failed to activate event {state_id}")
            
            # Case 2: Event should end (crossed end boundary)
            elif not should_be_active and is_active:
                logger.info(f"[📅] Event END detected: {label} ({state_id})")
                logger.info(f"[📅] Date range: {start_at.date()} - {end_at.date()}, Current: {now.date()}")
                
                if deactivate_state(state_id, operator_id="system:event_lifecycle"):
                    logger.info(f"[✅] Event deactivated: {state_id}")
                    
                    # Record event end for announcement
                    await on_event_end(state_id, trigger="automatic")
                else:
                    logger.error(f"[❌] Failed to deactivate event {state_id}")
            
            # Case 3: Event is correctly active (no action needed)
            elif should_be_active and is_active:
                logger.debug(f"[📅] Event {state_id} is active (ongoing)")
            
            # Case 4: Event is correctly inactive (no action needed)
            else:
                logger.debug(f"[📅] Event {state_id} is inactive (not in date range)")
        
        logger.info("[📅] [SYSTEM] Event lifecycle check complete")
        
    except Exception as e:
        logger.error(f"[❌] Event lifecycle failed: {e}", exc_info=True)
        raise


async def on_event_start(event_id: str, trigger: str = "automatic"):
    """Called when an event starts.
    
    Records event start for later announcement at the daily scheduled time.
    
    Args:
        event_id: Event state ID (e.g., "valentines-2026")
        trigger: "automatic" (boundary crossed) or "operator" (manual activation)
    """
    event_announcement_id = record_event_start(event_id, trigger)
    if event_announcement_id:
        logger.info(f"[📅] Event start announcement queued: {event_announcement_id}")
    else:
        logger.error(f"[📅] Failed to queue event start announcement for {event_id}")


async def on_event_end(event_id: str, trigger: str = "automatic"):
    """Called when an event ends.
    
    Records event end for later announcement at the daily scheduled time.
    
    Args:
        event_id: Event state ID (e.g., "valentines-2026")
        trigger: "automatic" (boundary crossed) or "operator" (manual deactivation)
    """
    event_announcement_id = record_event_end(event_id, trigger)
    if event_announcement_id:
        logger.info(f"[📅] Event end announcement queued: {event_announcement_id}")
    else:
        logger.error(f"[📅] Failed to queue event end announcement for {event_id}")


# Metadata for UI display
EVENT_LIFECYCLE_METADATA = {
    "category": "System Jobs",
    "label": "Event Lifecycle",
    "icon": "📅",
    "editable": False,  # Do not allow users to edit event lifecycle job
    "description": "Platform-wide event auto-start/auto-end based on date boundaries"
}
