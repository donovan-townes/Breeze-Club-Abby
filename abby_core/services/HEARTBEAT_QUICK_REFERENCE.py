#!/usr/bin/env python3
"""
Quick Reference: Scheduler Heartbeat Service

Fast lookup for common heartbeat operations.
"""

# ============================================================================
# IMPORT
# ============================================================================

from abby_core.observability import get_scheduler_heartbeat

# ============================================================================
# INITIALIZE & LIFECYCLE
# ============================================================================

# Get the global heartbeat service
heartbeat = get_scheduler_heartbeat()

# Start heartbeat emissions
heartbeat.start()

# Stop heartbeat emissions
heartbeat.stop()

# ============================================================================
# REGISTER GUILDS
# ============================================================================

from datetime import datetime, timedelta

# Register a guild with active schedule
next_announce = datetime.utcnow() + timedelta(hours=1)
heartbeat.register_guild("guild-123", next_announce)

# Unregister a guild
heartbeat.unregister_guild("guild-123")

# ============================================================================
# RECORD ANNOUNCEMENTS
# ============================================================================

# Successful announcement
heartbeat.record_announcement_sent("guild-123")

# Failed announcement
heartbeat.record_announcement_failed("guild-123", "Connection timeout")

# Recovery attempt
heartbeat.record_recovery_attempt()

# ============================================================================
# CHECK STATUS
# ============================================================================

# Quick health check (True if HEALTHY or DEGRADED)
if heartbeat.is_healthy():
    print("Scheduler is operating normally")

# Get detailed health status
status = heartbeat.get_health_status()
# Returns: SchedulerHealth.HEALTHY | DEGRADED | UNHEALTHY | RECOVERING | OFFLINE

# Get uptime in seconds
uptime = heartbeat.get_uptime_seconds()

# Get last heartbeat
last = heartbeat.get_last_heartbeat()
if last and last.is_stale(threshold_seconds=120):
    print("Heartbeat is stale - no update in 2 minutes")

# ============================================================================
# RETRIEVE METRICS
# ============================================================================

# Generate current heartbeat
heartbeat_data = heartbeat.generate_heartbeat()

# Access specific metrics
print(f"Active guilds: {heartbeat_data.active_guilds}")
print(f"Sent this hour: {heartbeat_data.announcements_sent_this_hour}")
print(f"Failed this hour: {heartbeat_data.announcements_failed_this_hour}")
print(f"Last error: {heartbeat_data.last_error}")
print(f"Recovery attempts: {heartbeat_data.recovery_attempts}")

# ============================================================================
# SERIALIZE FOR TELEMETRY
# ============================================================================

# Convert to dict for JSON serialization
heartbeat_dict = heartbeat_data.to_dict()

# Send to telemetry system
import json
telemetry_payload = json.dumps(heartbeat_dict)

# Or use observability's emit_event
from abby_core.observability import emit_event
emit_event("scheduler.heartbeat", heartbeat_dict)

# ============================================================================
# GET COMPREHENSIVE SUMMARY
# ============================================================================

# Get all status information at once
summary = heartbeat.get_summary()

# summary contains:
# {
#     "status": {...heartbeat.to_dict()...},
#     "is_running": bool,
#     "is_healthy": bool,
#     "active_guild_ids": [list of guild IDs]
# }

# ============================================================================
# HEALTH STATUS INTERPRETATION
# ============================================================================

# HEALTHY - Operating normally (< 25% failure rate)
# DEGRADED - Warning state (25-50% failure rate)
# UNHEALTHY - Critical (> 50% failure rate)
# RECOVERING - Recently recovered from error (within 5 minutes)
# OFFLINE - Service not started

from abby_core.observability import SchedulerHealth

if heartbeat.get_health_status() == SchedulerHealth.UNHEALTHY:
    # Alert! High failure rate
    print(f"Last error: {heartbeat_data.last_error}")
    print(f"Affected guild: {heartbeat_data.last_error_guild_id}")
elif heartbeat.get_health_status() == SchedulerHealth.RECOVERING:
    # In recovery from recent error
    print(f"Recovery in progress ({heartbeat_data.recovery_attempts} attempts)")

# ============================================================================
# SCHEDULER INTEGRATION PATTERN
# ============================================================================

# Typical scheduler loop
async def scheduler_loop():
    heartbeat.start()
    
    try:
        while True:
            announcements = await get_pending_announcements()
            
            for announcement in announcements:
                try:
                    await send_announcement(announcement)
                    heartbeat.record_announcement_sent(announcement.guild_id)
                except Exception as e:
                    heartbeat.record_announcement_failed(
                        announcement.guild_id, 
                        str(e)
                    )
                    
                    try:
                        await recover_from_error(announcement)
                        heartbeat.record_recovery_attempt()
                    except:
                        pass  # Continue to next
            
            await asyncio.sleep(60)
    
    finally:
        heartbeat.stop()

# ============================================================================
# MONITORING TASK
# ============================================================================

# Typical monitoring/telemetry loop
async def monitoring_loop():
    heartbeat = get_scheduler_heartbeat()
    
    while True:
        hb = heartbeat.generate_heartbeat()
        
        # Check if stale
        if hb.is_stale(threshold_seconds=120):
            # Alert: No heartbeat in 2 minutes
            pass
        
        # Emit to telemetry
        emit_event("scheduler.heartbeat", hb.to_dict())
        
        # Sleep interval
        await asyncio.sleep(60)

# ============================================================================
# TESTING
# ============================================================================

# Reset heartbeat for testing
from abby_core.observability import reset_heartbeat_service

@pytest.fixture
def heartbeat_service():
    reset_heartbeat_service()
    service = get_scheduler_heartbeat()
    service.start()
    yield service
    service.stop()

def test_announcement_tracking(heartbeat_service):
    heartbeat_service.record_announcement_sent("guild-1")
    
    hb = heartbeat_service.generate_heartbeat()
    assert hb.announcements_sent_this_hour == 1

# ============================================================================
# COMMON PATTERNS
# ============================================================================

# Pattern 1: Health-based retry
async def send_with_retry(announcement):
    heartbeat = get_scheduler_heartbeat()
    
    for attempt in range(3):
        try:
            await send_announcement(announcement)
            heartbeat.record_announcement_sent(announcement.guild_id)
            return True
        except Exception as e:
            if attempt == 2:  # Last attempt
                heartbeat.record_announcement_failed(
                    announcement.guild_id, 
                    f"Failed after 3 attempts: {e}"
                )
                return False
            heartbeat.record_recovery_attempt()
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

# Pattern 2: Health-aware scheduling
async def check_before_schedule():
    heartbeat = get_scheduler_heartbeat()
    
    if not heartbeat.is_healthy():
        # Skip scheduling if unhealthy
        logger.warning(
            "Scheduler unhealthy, skipping announcements",
            extra={"status": heartbeat.get_health_status()}
        )
        return False
    
    return True

# Pattern 3: Dashboard endpoint
async def get_scheduler_health():
    heartbeat = get_scheduler_heartbeat()
    summary = heartbeat.get_summary()
    
    return {
        "status": summary["status"]["health_status"],
        "active_guilds": summary["status"]["active_guilds"],
        "uptime_hours": summary["status"]["uptime_seconds"] / 3600,
        "sent_today": summary["status"]["announcements_sent_this_hour"],
        "failed_today": summary["status"]["announcements_failed_this_hour"],
    }

# ============================================================================
# REFERENCE
# ============================================================================

"""
For more information:
- Full documentation: docs/SCHEDULER_HEARTBEAT.md
- Integration guide: docs/HEARTBEAT_MIGRATION_GUIDE.md
- Implementation: abby_core/services/scheduler_heartbeat.py
- Tests: tests/test_scheduler_heartbeat.py
"""
