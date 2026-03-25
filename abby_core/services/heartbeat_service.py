"""Unified Heartbeat Service

Central orchestrator for all platform heartbeats. Consolidates fragmented
heartbeat emissions into one service with configurable intervals.

**Architecture:**
- Single source of truth for heartbeat emissions
- Multiple heartbeat types (platform, scheduler, llm, discord)
- Configurable intervals per heartbeat type
- Platform-agnostic (no Discord dependencies)
- Integrates with scheduler for timing

**Heartbeat Types:**
1. Platform Heartbeat (every 60s)
   - Uptime, active sessions, pending submissions
   - MongoDB health, LLM provider latency
   
2. Scheduler Heartbeat (every 60s)
   - Announcement success/failure rates
   - Active guilds, recovery attempts
   - Next announcement timing
   
3. Discord Heartbeat (every 60s)
   - Guild count, member count
   - Command usage stats
   - Voice/streaming stats

**Benefits:**
- Unified emission point (easier to monitor/debug)
- No duplicate loops or emissions
- Consistent telemetry format
- Easy to add new heartbeat types
- Scheduler-driven timing (no independent loops)
"""

from typing import Any, Dict, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HeartbeatType(Enum):
    """Types of heartbeats emitted by the service."""
    PLATFORM = "platform"      # Core platform metrics (uptime, sessions, etc.)
    SCHEDULER = "scheduler"    # Scheduler health and announcement metrics
    DISCORD = "discord"        # Discord-specific metrics (guilds, members)
    LLM = "llm"               # LLM provider health and latency


@dataclass
class HeartbeatConfig:
    """Configuration for a heartbeat type."""
    interval_seconds: int = 60
    enabled: bool = True
    last_emission: Optional[datetime] = None
    emission_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedHeartbeatService:
    """Central heartbeat orchestrator for all platform telemetry.
    
    Consolidates fragmented heartbeat logic into one service.
    Runs via the canonical SchedulerService.
    """
    
    def __init__(self):
        """Initialize heartbeat service with default configurations."""
        self.configs: Dict[HeartbeatType, HeartbeatConfig] = {
            HeartbeatType.PLATFORM: HeartbeatConfig(interval_seconds=60),
            HeartbeatType.SCHEDULER: HeartbeatConfig(interval_seconds=60),
            HeartbeatType.DISCORD: HeartbeatConfig(interval_seconds=60),
            HeartbeatType.LLM: HeartbeatConfig(interval_seconds=300),  # 5 min
        }
        
        # Metric collectors (callables that return metric dicts)
        self._collectors: Dict[HeartbeatType, Callable[[], Dict[str, Any]]] = {}
        
        # Start time for uptime calculation
        self._start_time = datetime.now(timezone.utc)
        
        logger.info("[❤️ Heartbeat] Unified heartbeat service initialized (platform=60s, scheduler=60s, discord=60s, llm=300s)")
    
    def register_collector(
        self,
        heartbeat_type: HeartbeatType,
        collector: Callable[[], Dict[str, Any]],
    ) -> None:
        """Register a metric collector for a heartbeat type.
        
        Args:
            heartbeat_type: Type of heartbeat
            collector: Callable that returns metrics dict
        """
        self._collectors[heartbeat_type] = collector
        logger.debug(f"[❤️ Heartbeat] Registered collector for {heartbeat_type.value}")
    
    def configure(
        self,
        heartbeat_type: HeartbeatType,
        interval_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Configure a heartbeat type.
        
        Args:
            heartbeat_type: Type of heartbeat to configure
            interval_seconds: Override default interval
            enabled: Enable/disable this heartbeat type
        """
        config = self.configs[heartbeat_type]
        
        if interval_seconds is not None:
            config.interval_seconds = interval_seconds
        
        if enabled is not None:
            config.enabled = enabled
        
        logger.info(
            f"[❤️ Heartbeat] Configured {heartbeat_type.value}: "
            f"interval={config.interval_seconds}s, enabled={config.enabled}"
        )
    
    def should_emit(self, heartbeat_type: HeartbeatType) -> bool:
        """Check if a heartbeat type should emit now.
        
        Args:
            heartbeat_type: Type of heartbeat to check
        
        Returns:
            True if enough time has passed since last emission
        """
        config = self.configs[heartbeat_type]
        
        if not config.enabled:
            return False
        
        if config.last_emission is None:
            return True
        
        elapsed = (datetime.now(timezone.utc) - config.last_emission).total_seconds()
        return elapsed >= config.interval_seconds
    
    async def emit_platform_heartbeat(
        self,
        uptime_seconds: Optional[int] = None,
        active_sessions: Optional[int] = None,
        pending_submissions: Optional[int] = None,
        ollama_latency_ms: Optional[int] = None,
        mongodb_available: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Emit platform-level heartbeat with core metrics.
        
        Args:
            uptime_seconds: Platform uptime (defaults to calculated)
            active_sessions: Active conversation sessions
            pending_submissions: Pending database submissions
            ollama_latency_ms: Ollama API latency
            mongodb_available: MongoDB connection status
        
        Returns:
            Heartbeat payload dict
        """
        if not self.should_emit(HeartbeatType.PLATFORM):
            return {}
        
        # Calculate uptime if not provided
        if uptime_seconds is None:
            uptime_seconds = int((datetime.now(timezone.utc) - self._start_time).total_seconds())
        
        # Build payload
        payload = {
            "heartbeat_type": "platform",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
        }
        
        if active_sessions is not None:
            payload["active_sessions"] = active_sessions
        
        if pending_submissions is not None:
            payload["pending_submissions"] = pending_submissions
        
        if ollama_latency_ms is not None:
            payload["ollama_latency_ms"] = ollama_latency_ms
        
        if mongodb_available is not None:
            payload["mongodb_available"] = mongodb_available
        
        # Call collector if registered
        if HeartbeatType.PLATFORM in self._collectors:
            try:
                collected = self._collectors[HeartbeatType.PLATFORM]()
                payload.update(collected)
            except Exception as e:
                logger.warning(f"[❤️ Heartbeat] Platform collector failed: {e}")
        
        # Emit via telemetry (import here to avoid circular dependency)
        try:
            from abby_core.observability.telemetry import emit_event
            emit_event("HEARTBEAT", payload)
        except Exception as e:
            logger.error(f"[❤️ Heartbeat] Failed to emit platform heartbeat: {e}")
        
        # Update config
        config = self.configs[HeartbeatType.PLATFORM]
        config.last_emission = datetime.now(timezone.utc)
        config.emission_count += 1
        
        logger.debug(
            f"[❤️ Heartbeat] Emitted platform heartbeat "
            f"(uptime={uptime_seconds}s, count={config.emission_count})"
        )
        
        return payload
    
    async def emit_scheduler_heartbeat(
        self,
        health_status: str,
        active_guilds: int,
        announcements_sent_hour: int,
        announcements_failed_hour: int,
        next_announcement_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Emit scheduler-specific heartbeat.
        
        Args:
            health_status: Scheduler health (healthy/degraded/unhealthy)
            active_guilds: Number of active guilds
            announcements_sent_hour: Announcements sent in last hour
            announcements_failed_hour: Announcements failed in last hour
            next_announcement_at: Next scheduled announcement time
        
        Returns:
            Heartbeat payload dict
        """
        if not self.should_emit(HeartbeatType.SCHEDULER):
            return {}
        
        payload = {
            "heartbeat_type": "scheduler",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_status": health_status,
            "active_guilds": active_guilds,
            "announcements_sent_hour": announcements_sent_hour,
            "announcements_failed_hour": announcements_failed_hour,
        }
        
        if next_announcement_at:
            payload["next_announcement_at"] = next_announcement_at.isoformat()
        
        # Call collector if registered
        if HeartbeatType.SCHEDULER in self._collectors:
            try:
                collected = self._collectors[HeartbeatType.SCHEDULER]()
                payload.update(collected)
            except Exception as e:
                logger.warning(f"[❤️ Heartbeat] Scheduler collector failed: {e}")
        
        # Emit via telemetry (use HEARTBEAT event type with scheduler metadata)
        try:
            from abby_core.observability.telemetry import emit_event
            emit_event("HEARTBEAT", payload)
        except Exception as e:
            logger.error(f"[❤️ Heartbeat] Failed to emit scheduler heartbeat: {e}")
        
        # Update config
        config = self.configs[HeartbeatType.SCHEDULER]
        config.last_emission = datetime.now(timezone.utc)
        config.emission_count += 1
        
        logger.debug(
            f"[❤️ Heartbeat] Emitted scheduler heartbeat "
            f"(health={health_status}, guilds={active_guilds})"
        )
        
        return payload
    
    async def emit_discord_heartbeat(
        self,
        guild_count: int,
        total_members: int,
        voice_connections: int = 0,
        command_usage_hour: int = 0,
    ) -> Dict[str, Any]:
        """Emit Discord-specific heartbeat.
        
        Args:
            guild_count: Number of guilds bot is in
            total_members: Total member count across guilds
            voice_connections: Active voice connections
            command_usage_hour: Commands executed in last hour
        
        Returns:
            Heartbeat payload dict
        """
        if not self.should_emit(HeartbeatType.DISCORD):
            return {}
        
        payload = {
            "heartbeat_type": "discord",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guild_count": guild_count,
            "total_members": total_members,
            "voice_connections": voice_connections,
            "command_usage_hour": command_usage_hour,
        }
        
        # Call collector if registered
        if HeartbeatType.DISCORD in self._collectors:
            try:
                collected = self._collectors[HeartbeatType.DISCORD]()
                payload.update(collected)
            except Exception as e:
                logger.warning(f"[❤️ Heartbeat] Discord collector failed: {e}")
        
        # Emit via telemetry (use HEARTBEAT event type with discord metadata)
        try:
            from abby_core.observability.telemetry import emit_event
            emit_event("HEARTBEAT", payload)
        except Exception as e:
            logger.error(f"[❤️ Heartbeat] Failed to emit discord heartbeat: {e}")
        
        # Update config
        config = self.configs[HeartbeatType.DISCORD]
        config.last_emission = datetime.now(timezone.utc)
        config.emission_count += 1
        
        logger.debug(
            f"[❤️ Heartbeat] Emitted discord heartbeat "
            f"(guilds={guild_count}, members={total_members})"
        )
        
        return payload
    
    async def emit_all_due(self) -> Dict[str, Dict[str, Any]]:
        """Emit all heartbeats that are due (called by scheduler tick).
        
        Returns:
            Dict of emitted heartbeats by type
        """
        emitted = {}
        
        # Platform heartbeat (uptime, sessions, etc.)
        if self.should_emit(HeartbeatType.PLATFORM):
            try:
                payload = await self.emit_platform_heartbeat()
                if payload:
                    emitted["platform"] = payload
            except Exception as e:
                logger.error(f"[❤️ Heartbeat] Platform emission failed: {e}")
        
        # Scheduler heartbeat (announcement health)
        if self.should_emit(HeartbeatType.SCHEDULER):
            try:
                # Get scheduler heartbeat service
                from abby_core.services.scheduler_heartbeat import get_scheduler_heartbeat
                
                scheduler_hb_service = get_scheduler_heartbeat()
                scheduler_hb = scheduler_hb_service.generate_heartbeat()
                
                payload = await self.emit_scheduler_heartbeat(
                    health_status=scheduler_hb.health_status.value,
                    active_guilds=scheduler_hb.active_guilds,
                    announcements_sent_hour=scheduler_hb.announcements_sent_this_hour,
                    announcements_failed_hour=scheduler_hb.announcements_failed_this_hour,
                    next_announcement_at=scheduler_hb.next_announcement_at,
                )
                if payload:
                    emitted["scheduler"] = payload
            except Exception as e:
                logger.error(f"[❤️ Heartbeat] Scheduler emission failed: {e}")
        
        # Discord heartbeat (guilds, members)
        if self.should_emit(HeartbeatType.DISCORD):
            try:
                payload = await self.emit_discord_heartbeat(
                    guild_count=0,  # Will be filled by collector
                    total_members=0,
                )
                if payload:
                    emitted["discord"] = payload
            except Exception as e:
                logger.error(f"[❤️ Heartbeat] Discord emission failed: {e}")
        
        return emitted
    
    def get_uptime_seconds(self) -> int:
        """Get platform uptime in seconds.
        
        Returns:
            Seconds since service started
        """
        return int((datetime.now(timezone.utc) - self._start_time).total_seconds())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get heartbeat service statistics.
        
        Returns:
            Dict with emission counts and last emission times
        """
        stats = {}
        
        for hb_type, config in self.configs.items():
            stats[hb_type.value] = {
                "enabled": config.enabled,
                "interval_seconds": config.interval_seconds,
                "emission_count": config.emission_count,
                "last_emission": config.last_emission.isoformat() if config.last_emission else None,
            }
        
        return stats


# Singleton instance
_heartbeat_service: Optional[UnifiedHeartbeatService] = None


def get_heartbeat_service() -> UnifiedHeartbeatService:
    """Get or create the singleton heartbeat service.
    
    Returns:
        UnifiedHeartbeatService instance
    """
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = UnifiedHeartbeatService()
    return _heartbeat_service


def reset_heartbeat_service() -> None:
    """Reset singleton (for testing).
    
    Resets the global heartbeat service instance.
    """
    global _heartbeat_service
    _heartbeat_service = None
