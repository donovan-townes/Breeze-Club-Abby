"""
Schedule Normalization Utilities

Provides helpers to read/write job schedules in a normalized format while maintaining
backward compatibility with legacy field names.

Phase 2: Schedule Type Normalization
=====================================

New Structure:
--------------
{
    "schedule": {
        "type": "daily",
        "time": "08:00"
    }
}

or

{
    "schedule": {
        "type": "interval",
        "every_minutes": 480,
        "jitter_minutes": 30  # Optional: adds ±30min variance
    }
}

Legacy Support:
---------------
- "time" field (daily jobs)
- "interval_hours" field (interval jobs)
- "check_interval_minutes" field (polling jobs)

All functions provide transparent backward compatibility.
"""

from typing import Dict, Any, Optional, Literal
from datetime import datetime, timedelta
import random

ScheduleType = Literal["daily", "interval", "date_based"]


def normalize_schedule_read(job_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read schedule from job config, normalizing legacy fields to new structure.
    
    Returns normalized schedule dict with:
        - type: "daily" | "interval"
        - time: HH:MM (for daily)
        - every_minutes: int (for interval)
    
    Backward compatible with:
        - time (daily)
        - interval_hours (interval)
        - check_interval_minutes (interval)
    
    Args:
        job_config: Job configuration dict
    
    Returns:
        Normalized schedule dict with type and timing fields
    
    Example:
        >>> normalize_schedule_read({"time": "08:00"})
        {"type": "daily", "time": "08:00"}
        
        >>> normalize_schedule_read({"interval_hours": 8})
        {"type": "interval", "every_minutes": 480}
    """
    # If already normalized, return as-is
    if "schedule" in job_config:
        return job_config["schedule"]
    
    # Legacy: time field means daily schedule
    if "time" in job_config:
        return {
            "type": "daily",
            "time": job_config["time"]
        }
    
    # Legacy: interval_hours means interval schedule
    if "interval_hours" in job_config:
        return {
            "type": "interval",
            "every_minutes": job_config["interval_hours"] * 60
        }
    
    # Legacy: check_interval_minutes means interval schedule
    if "check_interval_minutes" in job_config:
        return {
            "type": "interval",
            "every_minutes": job_config["check_interval_minutes"]
        }
    
    # Default: daily schedule at 08:00
    return {
        "type": "daily",
        "time": "08:00"
    }


def normalize_schedule_write(schedule_type: ScheduleType, **kwargs) -> Dict[str, Any]:
    """
    Create normalized schedule dict for writing to job config.
    
    Args:
        schedule_type: "daily" or "interval"
        **kwargs: Schedule parameters:
            - time: HH:MM (for daily)
            - every_minutes: int (for interval)
            - every_hours: int (for interval, converted to minutes)
    
    Returns:
        Normalized schedule dict ready for storage
    
    Example:
        >>> normalize_schedule_write("daily", time="08:00")
        {"type": "daily", "time": "08:00"}
        
        >>> normalize_schedule_write("interval", every_hours=8)
        {"type": "interval", "every_minutes": 480}
    """
    schedule = {"type": schedule_type}
    
    if schedule_type == "daily":
        if "time" not in kwargs:
            raise ValueError("Daily schedule requires 'time' parameter")
        schedule["time"] = kwargs["time"]
    
    elif schedule_type == "interval":
        if "every_minutes" in kwargs:
            schedule["every_minutes"] = kwargs["every_minutes"]
        elif "every_hours" in kwargs:
            schedule["every_minutes"] = kwargs["every_hours"] * 60
        else:
            raise ValueError("Interval schedule requires 'every_minutes' or 'every_hours' parameter")
    
    return schedule


def get_schedule_display(schedule: Dict[str, Any]) -> str:
    """
    Generate human-readable schedule display string.
    
    Args:
        schedule: Normalized schedule dict
    
    Returns:
        Display string (e.g., "08:00", "every 8h", "every 30m")
    
    Example:
        >>> get_schedule_display({"type": "daily", "time": "08:00"})
        "08:00"
        
        >>> get_schedule_display({"type": "interval", "every_minutes": 480})
        "every 8h"
    """
    if schedule["type"] == "daily":
        return schedule["time"]
    
    elif schedule["type"] == "interval":
        minutes = schedule["every_minutes"]
        
        # Display in hours if evenly divisible
        if minutes >= 60 and minutes % 60 == 0:
            hours = minutes // 60
            return f"every {hours}h"
        
        # Otherwise display in minutes
        return f"every {minutes}m"
    
    return "—"


def get_schedule_time(schedule: Dict[str, Any]) -> Optional[str]:
    """
    Extract time field from schedule (daily schedules only).
    
    Args:
        schedule: Normalized schedule dict
    
    Returns:
        HH:MM time string for daily schedules, None for interval schedules
    
    Example:
        >>> get_schedule_time({"type": "daily", "time": "08:00"})
        "08:00"
        
        >>> get_schedule_time({"type": "interval", "every_minutes": 480})
        None
    """
    if schedule["type"] == "daily":
        return schedule.get("time")
    return None


def get_schedule_interval_minutes(schedule: Dict[str, Any]) -> Optional[int]:
    """
    Extract interval from schedule (interval schedules only).
    
    Args:
        schedule: Normalized schedule dict
    
    Returns:
        Interval in minutes for interval schedules, None for daily schedules
    
    Example:
        >>> get_schedule_interval_minutes({"type": "daily", "time": "08:00"})
        None
        
        >>> get_schedule_interval_minutes({"type": "interval", "every_minutes": 480})
        480
    """
    if schedule["type"] == "interval":
        return schedule.get("every_minutes")
    return None


def get_schedule_interval_hours(schedule: Dict[str, Any]) -> Optional[float]:
    """
    Extract interval in hours from schedule (interval schedules only).
    
    Args:
        schedule: Normalized schedule dict
    
    Returns:
        Interval in hours for interval schedules, None for daily schedules
    
    Example:
        >>> get_schedule_interval_hours({"type": "daily", "time": "08:00"})
        None
        
        >>> get_schedule_interval_hours({"type": "interval", "every_minutes": 480})
        8.0
    """
    minutes = get_schedule_interval_minutes(schedule)
    if minutes is not None:
        return minutes / 60
    return None


def calculate_next_interval_slot(
    anchor_time: str,
    interval_minutes: int,
    last_executed_at: Optional[str],
    timezone_str: str = "UTC"
) -> datetime:
    """
    Calculate the next interval slot based on anchor time and interval.
    
    This finds the next "slot" after the last execution, where slots are
    aligned to the anchor time and repeat every interval_minutes.
    
    Args:
        anchor_time: HH:MM anchor time (e.g., "14:00")
        interval_minutes: Interval between slots in minutes
        last_executed_at: ISO timestamp of last execution (None for first run)
        timezone_str: Timezone for calculations (default UTC)
    
    Returns:
        Next slot datetime (without jitter)
    
    Example:
        >>> # Last executed at 13:37, anchor is 14:00, interval is 8h (480 min)
        >>> calculate_next_interval_slot("14:00", 480, "2026-01-20T13:37:00")
        # Returns: 2026-01-20T22:00:00 (next slot after 13:37 + 8h)
    """
    from datetime import datetime
    import pytz
    
    try:
        tz = pytz.timezone(timezone_str)
    except:
        tz = pytz.UTC
    
    now = datetime.now(tz)
    
    # Parse anchor time
    anchor_hour, anchor_minute = map(int, anchor_time.split(":"))
    
    # Find anchor slot today
    today_anchor = now.replace(hour=anchor_hour, minute=anchor_minute, second=0, microsecond=0)
    
    if last_executed_at is None:
        # First run: find next anchor slot from now
        if now < today_anchor:
            return today_anchor
        
        # Calculate slots from today's anchor
        interval_delta = timedelta(minutes=interval_minutes)
        next_slot = today_anchor
        while next_slot <= now:
            next_slot += interval_delta
        
        return next_slot
    
    # Parse last execution time
    try:
        last_exec = datetime.fromisoformat(last_executed_at.replace('Z', '+00:00'))
        if last_exec.tzinfo is None:
            last_exec = tz.localize(last_exec)
        else:
            last_exec = last_exec.astimezone(tz)
    except:
        # Fallback to now if parsing fails
        last_exec = now
    
    # Calculate next slot after last_executed_at + interval
    next_execution_time = last_exec + timedelta(minutes=interval_minutes)
    
    # Find the next anchor-aligned slot >= next_execution_time
    # Start from today's anchor and step forward
    interval_delta = timedelta(minutes=interval_minutes)
    next_slot = today_anchor
    
    # If today's anchor is in the future and >= next_execution_time, use it
    if next_slot >= next_execution_time:
        return next_slot
    
    # Step backward to find the anchor slot on or before last_exec
    while next_slot > last_exec:
        next_slot -= interval_delta
    
    # Step forward to find first slot >= next_execution_time
    while next_slot < next_execution_time:
        next_slot += interval_delta
    
    return next_slot


def apply_jitter(slot_time: datetime, jitter_minutes: int) -> datetime:
    """
    Apply random time jitter to a slot time.
    
    Args:
        slot_time: The base slot datetime
        jitter_minutes: Maximum jitter in minutes (will apply ±jitter_minutes)
    
    Returns:
        Jittered datetime within ±jitter_minutes of slot_time
    
    Example:
        >>> slot = datetime(2026, 1, 20, 14, 0)
        >>> jittered = apply_jitter(slot, 30)
        # Returns: somewhere between 13:30 and 14:30
    """
    if jitter_minutes <= 0:
        return slot_time
    
    # Random offset between -jitter_minutes and +jitter_minutes
    offset_minutes = random.randint(-jitter_minutes, jitter_minutes)
    return slot_time + timedelta(minutes=offset_minutes)


def calculate_next_interval_execution(
    anchor_time: str,
    interval_minutes: int,
    last_executed_at: Optional[str],
    jitter_minutes: int = 0,
    timezone_str: str = "UTC"
) -> datetime:
    """
    Calculate next execution time for interval-based job with optional jitter.
    
    Combines slot calculation and jitter application to determine when a job
    should next execute.
    
    Args:
        anchor_time: HH:MM anchor time (e.g., "14:00")
        interval_minutes: Interval between executions in minutes
        last_executed_at: ISO timestamp of last execution (None for first run)
        jitter_minutes: Random variance in minutes (±jitter_minutes, default 0)
        timezone_str: Timezone for calculations (default UTC)
    
    Returns:
        Next execution datetime with jitter applied
    
    Example:
        >>> # Calculate next execution for 8-hour interval job anchored at 14:00
        >>> # with ±30 minute jitter, last ran at 13:37
        >>> calculate_next_interval_execution(
        ...     "14:00", 480, "2026-01-20T13:37:00", jitter_minutes=30
        ... )
        # Returns: 2026-01-20T22:00:00 ± 30 minutes (e.g., 21:47)
    """
    # Find next anchor-aligned slot
    next_slot = calculate_next_interval_slot(
        anchor_time,
        interval_minutes,
        last_executed_at,
        timezone_str
    )
    
    # Apply jitter if configured
    if jitter_minutes > 0:
        return apply_jitter(next_slot, jitter_minutes)
    
    return next_slot


def should_run_date_based_job(job: Dict[str, Any], now: datetime) -> bool:
    """
    Determine if a date-based job should run right now.
    
    Date-based jobs execute once on a specific calendar date at a specific time.
    Examples: Scheduled announcements, one-time events, future platform updates.
    
    Args:
        job: Job configuration dict with:
            - scheduled_date: "YYYY-MM-DD" target date
            - scheduled_time: "HH:MM" target time
            - last_executed_at: ISO timestamp of last execution (prevents re-runs)
        now: Current datetime in job's timezone
    
    Returns:
        True if job should run (date/time match and not yet executed)
    """
    scheduled_date_str = job.get("scheduled_date")
    scheduled_time_str = job.get("scheduled_time")
    last_executed_at = job.get("last_executed_at")
    
    if not scheduled_date_str or not scheduled_time_str:
        return False
    
    # Check if today matches scheduled date
    today_str = now.strftime("%Y-%m-%d")
    if today_str != scheduled_date_str:
        return False
    
    # Check if current time matches scheduled time (within the minute)
    try:
        hour, minute = map(int, scheduled_time_str.split(":"))
        if now.hour != hour or now.minute != minute:
            return False
    except (ValueError, AttributeError):
        return False
    
    # Check idempotency: has already executed today?
    if last_executed_at:
        try:
            last_exec = datetime.fromisoformat(last_executed_at.replace('Z', '+00:00'))
            last_exec_date = last_exec.strftime("%Y-%m-%d")
            if last_exec_date == today_str:
                return False  # Already executed today
        except (ValueError, AttributeError):
            pass
    
    return True


def should_run_job_with_reason(
    job_config: Dict[str, Any],
    now: datetime,
    timezone_str: str
) -> tuple[bool, str]:
    """
    Determine if a job should run based on its schedule configuration.

    Returns:
        Tuple of (should_run: bool, reason: str)
    """
    if not job_config.get("enabled", False):
        return False, "job disabled"

    # Date-based jobs
    if "scheduled_date" in job_config and "scheduled_time" in job_config:
        if should_run_date_based_job(job_config, now):
            return True, "date-based job ready"
        return False, "date-based job not ready"

    schedule = normalize_schedule_read(job_config)
    if not schedule:
        return False, "no schedule configured"

    schedule_type = schedule.get("type")
    last_executed_at = job_config.get("last_executed_at") or job_config.get("last_run_at")

    if schedule_type == "daily":
        job_time = get_schedule_time(schedule)
        if not job_time:
            return False, "no time configured"
        try:
            job_hour, job_minute = map(int, job_time.split(":"))
        except (ValueError, AttributeError):
            return False, f"invalid time format: {job_time}"

        if now.hour != job_hour or now.minute != job_minute:
            return False, f"time mismatch (now={now.strftime('%H:%M')}, job={job_time})"

        if last_executed_at:
            try:
                last_exec = datetime.fromisoformat(last_executed_at.replace("Z", "+00:00"))
                last_exec_date = last_exec.strftime("%Y-%m-%d")
                if last_exec_date == now.strftime("%Y-%m-%d"):
                    return False, f"already ran today ({last_exec_date})"
            except Exception:
                pass

        return True, "ready to run"

    if schedule_type == "interval":
        interval_minutes = get_schedule_interval_minutes(schedule)
        if not interval_minutes:
            return False, "no interval configured"

        jitter_minutes = schedule.get("jitter_minutes", 0)
        anchor_time = schedule.get("time", "00:00")

        try:
            next_execution = calculate_next_interval_execution(
                anchor_time=anchor_time,
                interval_minutes=interval_minutes,
                last_executed_at=last_executed_at,
                jitter_minutes=jitter_minutes,
                timezone_str=timezone_str,
            )
        except Exception as e:
            return False, f"evaluation error: {e}"

        if now >= next_execution:
            return True, f"ready to run (scheduled for {next_execution.strftime('%H:%M:%S')})"

        time_until = (next_execution - now).total_seconds() / 60
        return False, f"not yet time (next in {time_until:.0f} minutes at {next_execution.strftime('%H:%M:%S')})"

    return False, f"unknown schedule type: {schedule_type}"


__all__ = [
    "ScheduleType",
    "normalize_schedule_read",
    "normalize_schedule_write",
    "get_schedule_display",
    "get_schedule_time",
    "get_schedule_interval_minutes",
    "get_schedule_interval_hours",
    "calculate_next_interval_slot",
    "apply_jitter",
    "calculate_next_interval_execution",
    "should_run_date_based_job",
    "should_run_job_with_reason",
]
