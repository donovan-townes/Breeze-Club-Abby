"""Platform-wide scheduler heartbeat service.

Provides non-blocking heartbeat monitoring for the scheduled announcement system.
Enables resilience, recovery, and observability independent of any adapter (Discord, Web, etc.).

Architecture:
- Platform-agnostic (no Discord imports)
- Adapter-independent (works with any scheduler backend)
- Async-friendly (non-blocking heartbeat emissions)
- FSM-aware (can be integrated with conversation FSM telemetry)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SchedulerHealth(Enum):
    """Scheduler health status."""
    HEALTHY = "healthy"          # Operating normally
    DEGRADED = "degraded"        # Running but with issues
    UNHEALTHY = "unhealthy"      # Failures detected
    RECOVERING = "recovering"    # Recovering from failure
    OFFLINE = "offline"          # Not running


@dataclass
class SchedulerHeartbeat:
    """Single heartbeat emission from scheduler.
    
    Emitted every 60 seconds (configurable) to track:
    - Scheduler status and health
    - Active guild count
    - Next announcement timing
    - Recent failures/recoveries
    - Performance metrics
    """
    
    timestamp: datetime
    health_status: SchedulerHealth
    active_guilds: int  # Number of guilds with active schedules
    next_announcement_at: Optional[datetime] = None  # Time of next scheduled announcement
    last_announcement_at: Optional[datetime] = None  # Time of last successful announcement
    last_announcement_guild_id: Optional[str] = None  # Which guild got the last announcement
    
    # Metrics
    announcements_sent_this_hour: int = 0
    announcements_failed_this_hour: int = 0
    recovery_attempts: int = 0  # Count of recovery attempts since startup
    uptime_seconds: float = 0.0  # Seconds since scheduler started
    
    # Error tracking
    last_error: Optional[str] = None
    last_error_guild_id: Optional[str] = None
    last_error_timestamp: Optional[datetime] = None
    
    # Metadata
    scheduler_name: str = "abby_scheduler"
    version: str = "1.0"  # Heartbeat contract version
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_stale(self, threshold_seconds: float = 120.0) -> bool:
        """Check if heartbeat is stale (missed 2 cycles at 60s intervals).
        
        Args:
            threshold_seconds: Age threshold (default 2 minutes)
            
        Returns:
            True if heartbeat is older than threshold
        """
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > threshold_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize heartbeat for telemetry."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "health_status": self.health_status.value,
            "active_guilds": self.active_guilds,
            "next_announcement_at": self.next_announcement_at.isoformat() if self.next_announcement_at else None,
            "last_announcement_at": self.last_announcement_at.isoformat() if self.last_announcement_at else None,
            "last_announcement_guild_id": self.last_announcement_guild_id,
            "announcements_sent_this_hour": self.announcements_sent_this_hour,
            "announcements_failed_this_hour": self.announcements_failed_this_hour,
            "recovery_attempts": self.recovery_attempts,
            "uptime_seconds": self.uptime_seconds,
            "last_error": self.last_error,
            "last_error_guild_id": self.last_error_guild_id,
            "last_error_timestamp": self.last_error_timestamp.isoformat() if self.last_error_timestamp else None,
            "scheduler_name": self.scheduler_name,
            "version": self.version,
            "metadata": self.metadata,
        }


class SchedulerHeartbeatService:
    """Platform-wide scheduler heartbeat service.
    
    Monitors scheduler health and emits periodic heartbeats for observability.
    Enables recovery, resilience, and monitoring across all adapters.
    
    Usage:
        service = SchedulerHeartbeatService()
        service.start()  # Start heartbeat emissions
        
        # In scheduler loop, update state
        service.record_announcement_sent(guild_id, "guild-456")
        service.record_announcement_failed(guild_id, "guild-456", "Connection timeout")
        
        # Get current status
        status = service.get_health_status()
        # => SchedulerHealth.HEALTHY
        
        # Stop when shutting down
        service.stop()
    """
    
    def __init__(self, heartbeat_interval_seconds: float = 60.0):
        """Initialize scheduler heartbeat service.
        
        Args:
            heartbeat_interval_seconds: Interval for heartbeat emissions (default 60s)
        """
        self.heartbeat_interval = heartbeat_interval_seconds
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # State tracking
        self._started_at = datetime.utcnow()
        self._last_heartbeat: Optional[SchedulerHeartbeat] = None
        self._active_guilds: Dict[str, Any] = {}  # guild_id -> config
        
        # Metrics (hourly rolling window)
        self._announcements_sent = []  # List of (timestamp, guild_id)
        self._announcements_failed = []  # List of (timestamp, guild_id, error)
        self._recovery_attempts = 0
        
        # Error tracking
        self._last_error: Optional[str] = None
        self._last_error_guild_id: Optional[str] = None
        self._last_error_at: Optional[datetime] = None
        
        # Next announcement tracking
        self._next_announcement_at: Optional[datetime] = None
        self._last_announcement_at: Optional[datetime] = None
        self._last_announcement_guild_id: Optional[str] = None
        
        logger.debug(
            "[Heartbeat] Scheduler heartbeat service initialized",
            extra={"interval_seconds": heartbeat_interval_seconds}
        )
    
    def start(self) -> None:
        """Start heartbeat emissions."""
        if self._running:
            logger.warning("[Heartbeat] Heartbeat already running")
            return
        
        self._running = True
        self._started_at = datetime.utcnow()
        logger.debug("[❤️] Scheduler heartbeat service started")
    
    def stop(self) -> None:
        """Stop heartbeat emissions."""
        if not self._running:
            return
        
        self._running = False
        logger.info("[Heartbeat] Scheduler heartbeat stopped")
    
    def register_guild(self, guild_id: str, next_announcement: Optional[datetime] = None) -> None:
        """Register a guild with active scheduler.
        
        Args:
            guild_id: Guild identifier
            next_announcement: When the next announcement for this guild is scheduled
        """
        self._active_guilds[guild_id] = {
            "registered_at": datetime.utcnow(),
            "next_announcement": next_announcement,
        }
        
        # Update next_announcement_at if this is earlier
        if next_announcement and (self._next_announcement_at is None or next_announcement < self._next_announcement_at):
            self._next_announcement_at = next_announcement
        
        logger.debug(
            "[Heartbeat] Guild registered",
            extra={"guild_id": guild_id, "next_announcement": next_announcement}
        )
    
    def unregister_guild(self, guild_id: str) -> None:
        """Unregister a guild (no active schedule).
        
        Args:
            guild_id: Guild identifier
        """
        self._active_guilds.pop(guild_id, None)
        logger.debug("[Heartbeat] Guild unregistered", extra={"guild_id": guild_id})
    
    def record_announcement_sent(self, guild_id: str) -> None:
        """Record successful announcement.
        
        Args:
            guild_id: Guild that received announcement
        """
        self._announcements_sent.append((datetime.utcnow(), guild_id))
        self._last_announcement_at = datetime.utcnow()
        self._last_announcement_guild_id = guild_id
        
        # Cleanup old entries (older than 1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        self._announcements_sent = [
            (ts, gid) for ts, gid in self._announcements_sent if ts > one_hour_ago
        ]
        
        logger.debug(
            "[Heartbeat] Announcement sent",
            extra={"guild_id": guild_id, "total_sent_hour": len(self._announcements_sent)}
        )
    
    def record_announcement_failed(self, guild_id: str, error: str) -> None:
        """Record failed announcement.
        
        Args:
            guild_id: Guild that failed
            error: Error message
        """
        self._announcements_failed.append((datetime.utcnow(), guild_id, error))
        self._last_error = error
        self._last_error_guild_id = guild_id
        self._last_error_at = datetime.utcnow()
        
        # Cleanup old entries (older than 1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        self._announcements_failed = [
            (ts, gid, err) for ts, gid, err in self._announcements_failed if ts > one_hour_ago
        ]
        
        logger.warning(
            "[Heartbeat] Announcement failed",
            extra={
                "guild_id": guild_id,
                "error": error,
                "total_failed_hour": len(self._announcements_failed)
            }
        )
    
    def record_recovery_attempt(self) -> None:
        """Record a recovery attempt (e.g., reconnection, resume from failure)."""
        self._recovery_attempts += 1
        logger.info(
            "[Heartbeat] Recovery attempt recorded",
            extra={"total_attempts": self._recovery_attempts}
        )
    
    def get_health_status(self) -> SchedulerHealth:
        """Determine scheduler health based on recent activity.
        
        Returns:
            SchedulerHealth enum value
        """
        if not self._running:
            return SchedulerHealth.OFFLINE
        
        # Check if recovering (recent recovery attempt)
        if self._recovery_attempts > 0 and self._last_error_at:
            time_since_error = (datetime.utcnow() - self._last_error_at).total_seconds()
            if time_since_error < 300:  # Within 5 minutes
                return SchedulerHealth.RECOVERING
        
        # Check if unhealthy (high failure rate)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_failures = len([
            (ts, _, _) for ts, _, _ in self._announcements_failed if ts > one_hour_ago
        ])
        recent_successes = len([
            (ts, _) for ts, _ in self._announcements_sent if ts > one_hour_ago
        ])
        
        total_recent = recent_failures + recent_successes
        if total_recent > 0:
            failure_rate = recent_failures / total_recent
            if failure_rate > 0.5:  # >50% failure rate
                return SchedulerHealth.UNHEALTHY
            elif failure_rate > 0.25:  # >25% failure rate
                return SchedulerHealth.DEGRADED
        
        return SchedulerHealth.HEALTHY
    
    def get_uptime_seconds(self) -> float:
        """Get scheduler uptime in seconds."""
        return (datetime.utcnow() - self._started_at).total_seconds()
    
    def generate_heartbeat(self) -> SchedulerHeartbeat:
        """Generate current heartbeat snapshot.
        
        Returns:
            SchedulerHeartbeat with current metrics
        """
        # Count announcements from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        sent_count = len([
            (ts, _) for ts, _ in self._announcements_sent if ts > one_hour_ago
        ])
        failed_count = len([
            (ts, _, _) for ts, _, _ in self._announcements_failed if ts > one_hour_ago
        ])
        
        heartbeat = SchedulerHeartbeat(
            timestamp=datetime.utcnow(),
            health_status=self.get_health_status(),
            active_guilds=len(self._active_guilds),
            next_announcement_at=self._next_announcement_at,
            last_announcement_at=self._last_announcement_at,
            last_announcement_guild_id=self._last_announcement_guild_id,
            announcements_sent_this_hour=sent_count,
            announcements_failed_this_hour=failed_count,
            recovery_attempts=self._recovery_attempts,
            uptime_seconds=self.get_uptime_seconds(),
            last_error=self._last_error,
            last_error_guild_id=self._last_error_guild_id,
            last_error_timestamp=self._last_error_at,
        )
        
        self._last_heartbeat = heartbeat
        return heartbeat
    
    def get_last_heartbeat(self) -> Optional[SchedulerHeartbeat]:
        """Get last emitted heartbeat."""
        return self._last_heartbeat
    
    def is_healthy(self) -> bool:
        """Quick health check."""
        status = self.get_health_status()
        return status in (SchedulerHealth.HEALTHY, SchedulerHealth.DEGRADED)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status summary."""
        heartbeat = self.generate_heartbeat()
        return {
            "status": heartbeat.to_dict(),
            "is_running": self._running,
            "is_healthy": self.is_healthy(),
            "active_guild_ids": list(self._active_guilds.keys()),
        }


# Global singleton instance
_heartbeat_service: Optional[SchedulerHeartbeatService] = None


def get_scheduler_heartbeat() -> SchedulerHeartbeatService:
    """Get or create global scheduler heartbeat service."""
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = SchedulerHeartbeatService()
    return _heartbeat_service


def reset_heartbeat_service() -> None:
    """Reset global heartbeat service (for testing)."""
    global _heartbeat_service
    _heartbeat_service = None
