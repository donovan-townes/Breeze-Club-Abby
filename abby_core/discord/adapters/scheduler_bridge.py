"""Discord Adapter: Scheduler Bridge

Bridges platform-agnostic SchedulerService to Discord bot lifecycle and cogs.

Architecture:
    Platform-Agnostic Core Services
               ↓
    SchedulerService (job registry, execution loop)
               ↓
    Discord Scheduler Bridge (this module)
               ↓
    Discord Cogs (ExperienceGainManager, GiveawayManager, etc.)

Responsibilities:
    - Implement JobHandler interfaces for Discord-specific tasks
    - Register handlers with SchedulerService
    - Convert platform-agnostic job results to Discord operations
    - Dispatch to cogs for UI/messaging

Note: Platform-agnostic handlers (heartbeat) live here because they're
part of Discord's scheduler integration. The SchedulerService itself
remains platform-agnostic.
"""

import asyncio
from typing import Any, Dict, Optional
from datetime import datetime

from abby_core.services.scheduler import (
    JobHandler,
    ScheduleConfig,
    create_job,
    get_scheduler_service,
)
from abby_core.services.economy_service import get_economy_service
from abby_core.economy.services.banking_service import BankingService
from abby_core.observability.logging import logging
from abby_core.database.mongodb import get_database
from abby_core.observability.telemetry import emit_heartbeat
from abby_core.database.mongodb import (
    get_active_sessions_count,
    get_pending_submissions_count,
)
# Import directly from source to help Pylance type inference
from abby_core.services.scheduler_heartbeat import (
    get_scheduler_heartbeat,
    SchedulerHeartbeatService,
)
from abby_core.services.heartbeat_service import get_heartbeat_service, HeartbeatType
from abby_core.discord.config import BotConfig
from abby_core.discord.cogs.system.registry import JOB_HANDLERS
from abby_core.discord.cogs.system.schedule_utils import should_run_job_with_reason

logger = logging.getLogger(__name__)


def get_guild_now(timezone_str: str) -> datetime:
    """Get current time in the guild's timezone."""
    import pytz
    try:
        tz = pytz.timezone(timezone_str)
    except Exception:
        tz = pytz.UTC
    return datetime.now(tz)


# ════════════════════════════════════════════════════════════════════════════════
# PLATFORM-AGNOSTIC JOB HANDLERS
# ════════════════════════════════════════════════════════════════════════════════

class HeartbeatJobHandler(JobHandler):
    """Emit system health metrics via unified heartbeat service.
    
    Consolidates all heartbeat emissions into UnifiedHeartbeatService.
    Replaces fragmented heartbeat logic from multiple independent emitters.
    
    Now runs via platform scheduler every 1 minute as single source of truth.
    """

    def __init__(self, bot: Optional[Any] = None):
        """Initialize heartbeat handler.
        
        Args:
            bot: Discord bot instance (optional, used only for metrics)
        """
        self.bot = bot
        self.scheduler_heartbeat: SchedulerHeartbeatService = get_scheduler_heartbeat()
        self.unified_heartbeat = get_heartbeat_service()

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute unified heartbeat emission.
        
        Emits all due heartbeats via UnifiedHeartbeatService:
        1. Platform heartbeat (uptime, sessions, submissions, latency)
        2. Scheduler heartbeat (announcement health, guild metrics)
        3. Discord heartbeat (guild count, member count, voice connections)
        
        Returns:
            {"status": "ok"} on success
            {"status": "error", "error": str} on failure
        """
        try:
            # Get metrics from platform-agnostic services
            loop = asyncio.get_event_loop()
            active_sessions = await loop.run_in_executor(None, get_active_sessions_count)
            pending_submissions = await loop.run_in_executor(None, get_pending_submissions_count)
            
            # Get bot metrics if available
            uptime_seconds = None
            ollama_latency_ms = None
            
            if self.bot and hasattr(self.bot, "start_time") and self.bot.start_time:
                uptime_seconds = int(datetime.now().timestamp() - self.bot.start_time)
            
            if self.bot and hasattr(self.bot, "_probe_ollama_latency"):
                try:
                    ollama_latency_ms = await self.bot._probe_ollama_latency()
                except Exception:
                    ollama_latency_ms = None
            
            # Emit platform heartbeat via unified service
            await self.unified_heartbeat.emit_platform_heartbeat(
                uptime_seconds=uptime_seconds,
                active_sessions=active_sessions,
                pending_submissions=pending_submissions,
                ollama_latency_ms=ollama_latency_ms,
            )
            
            # Emit Discord heartbeat if bot available
            if self.bot:
                guild_count = len(self.bot.guilds)
                total_members = sum(guild.member_count or 0 for guild in self.bot.guilds)
                
                # Count voice connections
                voice_connections = 0
                for guild in self.bot.guilds:
                    if guild.voice_client and guild.voice_client.is_connected():
                        voice_connections += 1
                
                await self.unified_heartbeat.emit_discord_heartbeat(
                    guild_count=guild_count,
                    total_members=total_members,
                    voice_connections=voice_connections,
                )
            
            # Emit scheduler heartbeat (announcement health)
            scheduler_hb = self.scheduler_heartbeat.generate_heartbeat()
            await self.unified_heartbeat.emit_scheduler_heartbeat(
                health_status=scheduler_hb.health_status.value,
                active_guilds=scheduler_hb.active_guilds,
                announcements_sent_hour=scheduler_hb.announcements_sent_this_hour,
                announcements_failed_hour=scheduler_hb.announcements_failed_this_hour,
                next_announcement_at=scheduler_hb.next_announcement_at,
            )
            
            logger.debug(
                "[❤️ Unified Heartbeat] Emitted all heartbeats",
                extra={
                    "uptime_seconds": uptime_seconds,
                    "active_sessions": active_sessions,
                    "scheduler_health": scheduler_hb.health_status.value,
                }
            )
            
            return {"status": "ok"}
            
        except Exception as e:
            logger.error(f"[❤️ Unified Heartbeat] Emission failed: {e}", exc_info=True)
            self.scheduler_heartbeat.record_recovery_attempt()
            return {"status": "error", "error": str(e)}


class XPStreamingJobHandler(JobHandler):
    """Apply XP streaming tick.
    
    Delegates XP processing to EconomyService (platform-agnostic),
    then dispatches results to Discord cogs for UI updates.
    """

    def __init__(self, bot: Optional[Any] = None, config: Optional[BotConfig] = None):
        """Initialize XP streaming handler.
        
        Args:
            bot: Discord bot instance (optional, for cog dispatch)
            config: Bot configuration
        """
        self.bot = bot
        self.config = config or BotConfig()

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute XP streaming tick.
        
        Flow:
            1. Call EconomyService for platform-agnostic XP processing
            2. Dispatch to Discord cogs for UI/messaging
        
        Returns:
            {"status": "ok"} on success
            {"status": "error", "error": str} on failure
        """
        try:
            # Phase 1: Platform-agnostic XP processing via service
            economy_service = get_economy_service()
            
            # TODO: Implement streaming_tick() method in EconomyService
            # For now, dispatch directly to cogs
            
            # Phase 2: Dispatch to Discord cogs (if present)
            if self.bot:
                # Modern XPRewardManager
                reward_cog = self.bot.get_cog("XPRewardManager")
                if reward_cog and hasattr(reward_cog, "streaming_tick"):
                    try:
                        await reward_cog.streaming_tick()
                    except Exception as e:
                        logger.error(f"[⏰] XPRewardManager tick failed: {e}")

            return {"status": "ok"}
            
        except Exception as e:
            logger.error(f"[⏰] XP streaming job failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


class BankInterestJobHandler(JobHandler):
    """Apply periodic bank interest across all accounts.

    Runs via the canonical SchedulerService.
    """

    def __init__(self):
        self.banking_service = BankingService()

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute interest cycle for all accounts.

        Returns:
            {"status": "ok", "processed": int, "interest_paid": int}
            {"status": "error", "error": str}
        """
        try:
            result = self.banking_service.process_interest_cycle(log=False)
            return {
                "status": "ok",
                "processed": result.get("processed", 0),
                "interest_paid": result.get("interest_paid", 0),
            }
        except Exception as e:
            logger.error(f"[🏦] Bank interest job failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


class GuildJobsTickHandler(JobHandler):
    """Run guild-scoped scheduling jobs via platform scheduler.

    Replaces the deprecated Discord Scheduler cog by executing the same
    guild job evaluation logic on SchedulerService ticks.
    """

    def __init__(self, bot: Optional[Any] = None):
        self.bot = bot

        # Import handlers to ensure registry population
        try:
            import abby_core.discord.cogs.system.job_handlers  # noqa: F401
        except Exception as e:
            logger.warning(f"[⏰] Failed to import guild job handlers: {e}")

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one full guild scheduling tick.

        Returns:
            {"status": "ok", "guilds_processed": int, "jobs_dispatched": int}
            {"status": "error", "error": str}
        """
        try:
            from abby_core.database.collections.guild_configuration import get_all_guild_configs
            from abby_core.database.collections.system_configuration import get_system_config

            jobs_dispatched = 0
            guilds_processed = 0

            # Process system jobs first
            system_config = get_system_config()
            if system_config:
                dispatched = await self._process_system_jobs(system_config)
                jobs_dispatched += dispatched

            # Process guild jobs
            for config in get_all_guild_configs() or []:
                guilds_processed += 1
                jobs_dispatched += await self._process_guild(config)

            return {
                "status": "ok",
                "guilds_processed": guilds_processed,
                "jobs_dispatched": jobs_dispatched,
            }
        except Exception as e:
            logger.error(f"[⏰] Guild jobs tick failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def _process_system_jobs(self, config: Dict[str, Any]) -> int:
        system_jobs = config.get("system_jobs", {})
        if not system_jobs:
            return 0

        timezone_str = config.get("timezone", "UTC")
        now = get_guild_now(timezone_str)
        return await self._process_jobs(
            guild_id=0,
            jobs=system_jobs,
            now=now,
            timezone_str=timezone_str,
            path="system",
            is_system_job=True,
            guild_config=None,
        )

    async def _process_guild(self, config: Dict[str, Any]) -> int:
        guild_id = config.get("guild_id")
        if not guild_id:
            return 0

        scheduling = config.get("scheduling", {})
        timezone_str = scheduling.get("timezone", "UTC")
        now = get_guild_now(timezone_str)

        jobs = scheduling.get("jobs", {})
        if not jobs:
            return 0

        return await self._process_jobs(
            guild_id=guild_id,
            jobs=jobs,
            now=now,
            timezone_str=timezone_str,
            path="",
            is_system_job=False,
            guild_config=config,
        )

    async def _process_jobs(
        self,
        guild_id: int,
        jobs: Dict[str, Any],
        now: datetime,
        timezone_str: str,
        path: str,
        is_system_job: bool,
        guild_config: Optional[Dict[str, Any]],
    ) -> int:
        dispatched = 0
        for key, value in jobs.items():
            if not isinstance(value, dict):
                continue

            current_path = f"{path}.{key}" if path else key

            # Job config if it has enabled/time/schedule fields
            if "enabled" in value or "time" in value or "schedule" in value:
                job_type = current_path
                enriched_job = self._enrich_job_config(current_path, value, guild_config)
                dispatched += await self._evaluate_and_dispatch(
                    guild_id,
                    job_type,
                    enriched_job,
                    now,
                    timezone_str,
                    is_system_job,
                )
            else:
                dispatched += await self._process_jobs(
                    guild_id,
                    value,
                    now,
                    timezone_str,
                    current_path,
                    is_system_job,
                    guild_config,
                )

        return dispatched

    def _enrich_job_config(
        self,
        job_path: str,
        job: Dict[str, Any],
        guild_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        enriched = job.copy()
        features = (guild_config or {}).get("features", {})

        # Feature gating (same mapping as deprecated scheduler cog)
        if job_path == "games.emoji":
            enriched["enabled"] = features.get("auto_game", False)
        elif job_path == "motd":
            enriched["enabled"] = features.get("motd", False)
        else:
            enriched.setdefault("enabled", False)
        return enriched

    async def _evaluate_and_dispatch(
        self,
        guild_id: int,
        job_type: str,
        job_config: Dict[str, Any],
        now: datetime,
        timezone_str: str,
        is_system_job: bool,
    ) -> int:
        should_run, _reason = should_run_job_with_reason(job_config, now, timezone_str)
        if not should_run:
            return 0

        handler = JOB_HANDLERS.get(job_type)
        if not handler and "." in job_type:
            handler = JOB_HANDLERS.get(job_type.split(".")[-1])
        if not handler:
            logger.warning(
                f"[⏰] No handler registered for job type: {job_type}"
            )
            return 0

        try:
            await handler(self.bot, guild_id, job_config)
            return 1
        except Exception as e:
            logger.error(
                f"[⏰] Job '{job_type}' failed for guild {guild_id}: {e}",
                exc_info=True,
            )
            return 0


class DLQRetryJobHandler(JobHandler):
    """Process DLQ retry queue.
    
    Checks for failed announcements in the DLQ that are ready for retry
    and attempts to reprocess them through AnnouncementDispatcher.
    
    Platform-agnostic: Uses DLQService and AnnouncementDispatcher.
    No Discord dependencies - could run on any platform.
    """

    def __init__(self, bot: Optional[Any] = None):
        """Initialize DLQ retry handler.
        
        Args:
            bot: Discord bot instance (optional, not used but kept for consistency)
        """
        self.bot = bot

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute DLQ retry processing.
        
        Flow:
            1. Query DLQService for pending retries (status=pending/retrying, next_retry_at <= now)
            2. For each item, call execute_retry() to attempt the operation
            3. Track results (resolved/failed)
        
        Returns:
            {"status": "ok", "processed": int, "resolved": int, "failed": int}
            {"status": "error", "error": str} on failure
        """
        try:
            from abby_core.services.dlq_service import get_dlq_service
            
            dlq_service = get_dlq_service()
            
            # Get items ready for retry
            pending_items = dlq_service.get_pending_retries()
            
            if not pending_items:
                return {"status": "ok", "processed": 0, "resolved": 0, "failed": 0}
            
            processed = 0
            resolved = 0
            failed = 0
            
            # Process each DLQ item
            for dlq_item in pending_items:
                dlq_id = str(dlq_item["_id"])
                announcement_id = str(dlq_item["announcement_id"])
                error_category = dlq_item.get("error_category", "unknown")
                
                try:
                    # Execute retry (will handle operation dispatch internally)
                    success = dlq_service.execute_retry(dlq_id, operator_id="system:dlq_retry")
                    
                    processed += 1
                    if success:
                        resolved += 1
                        logger.info(
                            f"[🔄 dlq_retry] SUCCESS "
                            f"dlq_id={dlq_id[:8]}... "
                            f"announcement_id={announcement_id[:8]}... "
                            f"category={error_category}"
                        )
                    else:
                        failed += 1
                        logger.debug(
                            f"[🔄 dlq_retry] RETRY_SCHEDULED "
                            f"dlq_id={dlq_id[:8]}... "
                            f"announcement_id={announcement_id[:8]}... "
                            f"category={error_category}"
                        )
                
                except Exception as e:
                    processed += 1
                    failed += 1
                    logger.error(
                        f"[🔄 dlq_retry] ERROR "
                        f"dlq_id={dlq_id[:8]}... "
                        f"announcement_id={announcement_id[:8]}... "
                        f"error={str(e)[:50]}",
                        exc_info=True
                    )
            
            # Log summary if any activity
            if processed > 0:
                logger.info(
                    f"[🔄 dlq_retry] Batch complete: "
                    f"processed={processed}, resolved={resolved}, failed={failed}"
                )
            
            return {
                "status": "ok",
                "processed": processed,
                "resolved": resolved,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"[⏰] DLQ retry job failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# DISCORD-SPECIFIC JOB HANDLERS
# ════════════════════════════════════════════════════════════════════════════════
# These handlers dispatch to cogs without a service equivalent.
# They could be extracted to services in future phases.

class GiveawayCheckJobHandler(JobHandler):
    """Check for giveaways to close.
    
    Discord-specific: dispatches to GiveawayManager cog.
    """

    def __init__(self, bot: Any):
        """Initialize giveaway check handler.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute giveaway check tick.
        
        Returns:
            {"status": "ok"} if executed
            {"status": "skipped"} if cog not loaded
        """
        cog = self.bot.get_cog("GiveawayManager")
        if not cog or not hasattr(cog, "check_giveaways_tick"):
            return {"status": "skipped", "reason": "GiveawayManager not loaded"}

        try:
            await cog.check_giveaways_tick()
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"[⏰] Giveaway check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


class NudgeJobHandler(JobHandler):
    """Send nudge messages to inactive users.
    
    Discord-specific: dispatches to NudgeHandler cog.
    """

    def __init__(self, bot: Any):
        """Initialize nudge handler.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute nudge tick.
        
        Returns:
            {"status": "ok"} if executed
            {"status": "skipped"} if cog not loaded
        """
        cog = self.bot.get_cog("NudgeHandler")
        if not cog or not hasattr(cog, "nudge_users_tick"):
            return {"status": "skipped", "reason": "NudgeHandler not loaded"}

        try:
            await cog.nudge_users_tick()
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"[⏰] Nudge check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


class UnifiedContentDispatcherHandler(JobHandler):
    """UNIFIED content lifecycle: generation → delivery → cleanup.
    
    Replaces separate announcement_generation and announcement_delivery handlers.
    Feature-flagged via USE_UNIFIED_DISPATCHER environment variable.
    
    Processes all content_delivery_items through complete lifecycle:
    - Generation: pending → generated (LLM calls for system events)
    - Delivery: generated → delivered (send to Discord)
    - Cleanup: delivered → archived (periodic purge)
    """

    def __init__(self, bot: Any):
        self.bot = bot
        self.scheduler_heartbeat: SchedulerHeartbeatService = get_scheduler_heartbeat()

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute unified content dispatcher tick.
        
        Returns:
            {"status": "ok", "generated": int, "delivered": int, "archived": int}
        """
        logger.debug("[⏰] UnifiedContentDispatcherHandler.execute() called")
        try:
            from abby_core.discord.cogs.system.jobs.unified_content_dispatcher import (
                execute_unified_content_dispatcher
            )
            
            logger.debug("[⏰] Calling execute_unified_content_dispatcher...")
            generated, delivered, archived = await execute_unified_content_dispatcher(
                bot=self.bot,
                job_config=job_config
            )
            
            # Record delivery metrics for monitoring
            if delivered:
                for _ in range(delivered):
                    self.scheduler_heartbeat.record_announcement_sent("")
            
            # Log only if there was activity
            if generated or delivered or archived:
                logger.info(
                    f"[⏰] Unified dispatcher: generated={generated}, delivered={delivered}, archived={archived}"
                )
            
            return {
                "status": "ok",
                "generated": generated,
                "delivered": delivered,
                "archived": archived
            }
        except Exception as e:
            logger.error(f"[⏰] Unified content dispatcher failed: {e}", exc_info=True)
            self.scheduler_heartbeat.record_recovery_attempt()
            return {"status": "error", "error": str(e)}


class EventLifecycleHandler(JobHandler):
    """Handler for system.event_lifecycle job - platform-wide event auto-start/end.
    
    This job runs daily at 00:00 UTC to check if any event boundaries have been crossed:
    - Activates events when current date reaches start_at
    - Deactivates events when current date passes end_at
    - Records event start/end for announcement generation
    
    Events handled:
    - Valentine's Day (Feb 1-14): crush_system_enabled
    - Easter (Good Friday-Easter Sunday): egg_hunt_enabled
    - 21 Days of the Breeze (Dec 1-21): breeze_event_enabled
    - Custom operator-created events with date boundaries
    """

    def __init__(self, bot: Any):
        self.bot = bot

    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute event lifecycle check.
        
        Returns:
            {"status": "ok", "events_activated": int, "events_deactivated": int}
        """
        logger.debug("[⏰] EventLifecycleHandler.execute() called")
        try:
            from abby_core.discord.cogs.system.jobs.event_lifecycle import execute_event_lifecycle
            
            logger.info("[📅] Executing platform-wide event lifecycle check...")
            await execute_event_lifecycle(
                bot=self.bot,
                guild_id=0,  # System job, not guild-specific
                job_config=job_config
            )
            
            logger.info("[✅] Event lifecycle check completed successfully")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"[❌] Event lifecycle check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# JOB REGISTRATION HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _ensure_job(job_type: str, schedule: ScheduleConfig, scope: str = "system") -> str:
    """Idempotently create a scheduler job if missing.
    
    Args:
        job_type: Job type identifier
        schedule: Schedule configuration
        scope: Job scope (default: "system")
    
    Returns:
        Job ID (string)
    """
    db = get_database()
    jobs = db["scheduler_jobs"]
    existing = jobs.find_one({"job_type": job_type, "scope": scope})
    if existing:
        return str(existing.get("_id"))
    return create_job(job_type=job_type, schedule=schedule, scope=scope)


def register_scheduler_jobs(bot: Any) -> None:
    """Register all Discord scheduler jobs and handlers.
    
    Call this during bot startup (e.g., in on_ready event or load hook).
    
    Args:
        bot: Discord bot instance
    """
    config = BotConfig()
    scheduler = get_scheduler_service(bot=bot)  # Pass bot for guild job dispatch
    
    # Initialize scheduler heartbeat service (platform-wide monitoring)
    heartbeat_service = get_scheduler_heartbeat()
    heartbeat_service.start()
    logger.debug("[⏰] Scheduler heartbeat service started")

    # Register job handlers with scheduler
    scheduler.register_handler("heartbeat", HeartbeatJobHandler(bot))
    scheduler.register_handler("xp_streaming", XPStreamingJobHandler(bot, config))
    scheduler.register_handler("bank_interest", BankInterestJobHandler())
    scheduler.register_handler("giveaway_check", GiveawayCheckJobHandler(bot))
    scheduler.register_handler("nudge_check", NudgeJobHandler(bot))
    scheduler.register_handler("guild_jobs_tick", GuildJobsTickHandler(bot))
    
    # Platform-wide event lifecycle: auto-activate/deactivate events based on date boundaries
    scheduler.register_handler("system.event_lifecycle", EventLifecycleHandler(bot))
    
    # Unified content dispatcher (PRIMARY) - consolidates all announcement types
    scheduler.register_handler("unified_content_dispatcher", UnifiedContentDispatcherHandler(bot))
    
    # DLQ retry processor - retries failed announcements
    scheduler.register_handler("dlq_retry", DLQRetryJobHandler(bot))

    # Seed default jobs if missing
    _ensure_job(
        "heartbeat",
        ScheduleConfig(schedule_type="interval", every_minutes=1, enabled=True),
        scope="system",
    )
    _ensure_job(
        "xp_streaming",
        ScheduleConfig(
            schedule_type="interval",
            every_minutes=max(1, int(config.timing.xp_stream_interval_minutes)),
            enabled=True,
        ),
        scope="system",
    )
    _ensure_job(
        "bank_interest",
        ScheduleConfig(schedule_type="interval", every_minutes=10, enabled=True),
        scope="system",
    )
    _ensure_job(
        "guild_jobs_tick",
        ScheduleConfig(schedule_type="interval", every_minutes=1, enabled=True),
        scope="system",
    )
    _ensure_job(
        "giveaway_check",
        ScheduleConfig(schedule_type="interval", every_minutes=1, enabled=True),
        scope="system",
    )
    _ensure_job(
        "nudge_check",
        ScheduleConfig(
            schedule_type="interval",
            every_minutes=max(1, int(config.timing.nudge_interval_hours * 60)),
            enabled=True,
        ),
        scope="system",
    )
    
    # Unified content dispatcher: every 1 minute (generation → delivery → cleanup)
    # Phase 2: Consolidated single job replaces announcement_generation + announcement_delivery
    _ensure_job(
        "unified_content_dispatcher",
        ScheduleConfig(schedule_type="interval", every_minutes=1, enabled=True),
        scope="system",
    )
    
    # DLQ retry processor: every 5 minutes (retries failed announcements with exponential backoff)
    _ensure_job(
        "dlq_retry",
        ScheduleConfig(schedule_type="interval", every_minutes=5, enabled=True),
        scope="system",
    )

    logger.debug("[⏰] Scheduler jobs registered for Discord adapter")
