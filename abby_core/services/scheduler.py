"""
Platform-Agnostic Scheduler Service

Canonical scheduler for all background jobs across platforms.
Enables background jobs to run on web servers, CLI tools, or any platform.

Architecture:
- Core scheduler runs on asyncio (not Discord)
- Job registry stored in MongoDB
- Handlers are platform-agnostic functions
- Adapters provide platform-specific I/O (Discord channels, web webhooks, etc.)

Design Goals:
- No Discord imports in core scheduler
- Reusable across Discord, web, CLI, cron jobs
- Testable without Discord bot running
- Hot-reloadable job configuration
- Idempotent execution (tracks last_run_at)

Job Types Supported:
- Interval jobs: Run every N minutes (e.g., interest cycle every 10 min)
- Daily jobs: Run at specific time in timezone (e.g., 9 AM announcements)
- Date-based jobs: Run once at specific date/time (e.g., event start)

Usage:
    from abby_core.services.scheduler import SchedulerService
    
    scheduler = SchedulerService()
    scheduler.register_handler("interest_cycle", process_interest_handler)
    await scheduler.start()
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable, List
from collections import deque
import pytz
from abc import ABC, abstractmethod

from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

# Environment flags
SCHEDULER_VERBOSE = os.getenv("ABBY_SCHEDULER_VERBOSE", "false").lower() == "true"
SCHEDULER_SUMMARY_INTERVAL_MINUTES = int(os.getenv("ABBY_SCHEDULER_SUMMARY_INTERVAL_MINUTES", "60"))
SCHEDULER_SUMMARY_WINDOW_HOURS = int(os.getenv("ABBY_SCHEDULER_SUMMARY_WINDOW_HOURS", "24"))


# ============================================================================
# JOB INTERFACES
# ============================================================================

class JobHandler(ABC):
    """Abstract base class for job handlers."""
    
    @abstractmethod
    async def execute(self, job_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the job.
        
        Args:
            job_config: Job configuration from MongoDB
            context: Execution context (guild_id, bot, etc.)
            
        Returns:
            Result dict with status and any output
        """
        pass


class ScheduleConfig:
    """Schedule configuration for a job."""
    
    def __init__(
        self,
        schedule_type: str,  # "interval", "daily", "date_based"
        enabled: bool = True,
        time: Optional[str] = None,  # "HH:MM" for daily
        every_minutes: Optional[int] = None,  # For interval
        jitter_minutes: Optional[int] = None,  # Random offset for intervals
        scheduled_date: Optional[str] = None,  # "YYYY-MM-DD" for date_based
        scheduled_time: Optional[str] = None,  # "HH:MM" for date_based
        timezone: str = "UTC",
        last_run_at: Optional[datetime] = None,
    ):
        self.schedule_type = schedule_type
        self.enabled = enabled
        self.time = time
        self.every_minutes = every_minutes
        self.jitter_minutes = jitter_minutes
        self.scheduled_date = scheduled_date
        self.scheduled_time = scheduled_time
        self.timezone = timezone
        self.last_run_at = last_run_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB-compatible dict."""
        return {
            "type": self.schedule_type,
            "enabled": self.enabled,
            "time": self.time,
            "every_minutes": self.every_minutes,
            "jitter_minutes": self.jitter_minutes,
            "scheduled_date": self.scheduled_date,
            "scheduled_time": self.scheduled_time,
            "timezone": self.timezone,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }


# ============================================================================
# SCHEDULER SERVICE
# ============================================================================

class SchedulerService:
    """
    Platform-agnostic scheduler service.
    
    Manages background job execution without Discord dependencies.
    """
    
    def __init__(self, tick_interval_seconds: int = 60, bot: Optional[Any] = None):
        """
        Initialize scheduler.
        
        Args:
            tick_interval_seconds: How often to check for jobs (default 60s)
            bot: Optional Discord bot instance for guild-specific job dispatch
        """
        self.tick_interval = tick_interval_seconds
        self.bot = bot  # Store bot for guild handler dispatch
        self.handlers: Dict[str, JobHandler] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None
        # Summary tracking
        self._last_summary_time: Optional[datetime] = None
        self._tick_count = 0
        self._recent_jobs: deque[tuple[datetime, str]] = deque()
        self._recent_errors: deque[datetime] = deque()
        self._bank_interest_runs_since_summary = 0
        self._bank_interest_processed_since_summary = 0
        self._bank_interest_paid_since_summary = 0
    
    def register_handler(self, job_type: str, handler: JobHandler):
        """Register a job handler for a specific job type."""
        self.handlers[job_type] = handler
        logger.debug(f"[⏰] Registered handler for job type: {job_type}")
    
    def unregister_handler(self, job_type: str):
        """Unregister a job handler."""
        if job_type in self.handlers:
            del self.handlers[job_type]
            logger.info(f"[⏰] Unregistered handler for job type: {job_type}")
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("[⏰] Scheduler already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"[⏰] Platform scheduler operational (tick interval: {self.tick_interval}s)")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[⏰] Scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop (runs every tick_interval seconds)."""
        self._last_summary_time = datetime.now(timezone.utc)
        while self.running:
            try:
                await self._tick()
                self._tick_count += 1
                
                # Check if we should emit summary
                await self._maybe_emit_summary()
            except Exception as e:
                logger.error(f"[⏰] Scheduler tick failed: {e}", exc_info=True)
            
            # Wait until next tick
            await asyncio.sleep(self.tick_interval)
    
    async def _tick(self):
        """Process one scheduler tick."""
        utc_now = datetime.now(timezone.utc)
        logger.debug(f"[⏰] Scheduler tick at {utc_now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Phase 1: Process system-level jobs from MongoDB
        try:
            await self._process_mongodb_jobs(utc_now)
        except Exception as e:
            logger.error(f"[⏰] Error processing MongoDB jobs: {e}", exc_info=True)
        
        # Phase 2: Process guild-scoped jobs from guild configuration
        try:
            await self._process_guild_config_jobs(utc_now)
        except Exception as e:
            logger.error(f"[⏰] Error processing guild config jobs: {e}", exc_info=True)
    
    async def _process_mongodb_jobs(self, utc_now: datetime):
        """Process system-level jobs from MongoDB scheduler_jobs collection."""
        db = get_database()
        jobs_collection = db["scheduler_jobs"]
        
        # Find all enabled jobs
        jobs = list(jobs_collection.find({"enabled": True}))
        
        if not jobs:
            logger.debug("[⏰] No MongoDB jobs to process")
            return
        
        logger.debug(f"[⏰] Processing {len(jobs)} MongoDB jobs")
        
        # Process each job
        for job in jobs:
            try:
                await self._process_job(job, utc_now)
            except Exception as e:
                job_id = job.get("_id", "unknown")
                job_type = job.get("job_type", "unknown")
                logger.error(f"[⏰] Error processing job {job_id} (type: {job_type}): {e}", exc_info=True)
    
    async def _process_guild_config_jobs(self, utc_now: datetime):
        """Process guild-scoped jobs from guild configuration files.
        
        Fetches all guild configs and processes their scheduling.jobs.* registry.
        This consolidates what was previously handled by the Discord scheduler cog.
        """
        try:
            from abby_core.database.collections.guild_configuration import get_all_guild_configs
        except ImportError:
            logger.debug("[⏰] Guild configuration module not available, skipping guild jobs")
            return
        
        try:
            all_configs = get_all_guild_configs()
        except Exception as e:
            logger.error(f"[⏰] Failed to fetch guild configs: {e}")
            return
        
        if not all_configs:
            logger.debug("[⏰] No guild configs found")
            return
        
        logger.debug(f"[⏰] Processing {len(all_configs)} guild configurations for jobs")
        
        # Process each guild
        for config in all_configs:
            try:
                await self._process_guild_config(config, utc_now)
            except Exception as e:
                guild_id = config.get("guild_id", "unknown")
                logger.error(f"[⏰] Error processing guild {guild_id}: {e}", exc_info=True)
    
    async def _process_guild_config(self, config: Dict[str, Any], utc_now: datetime):
        """Process all jobs for a single guild from its configuration.
        
        Args:
            config: Guild configuration dict
            utc_now: Current time in UTC
        """
        guild_id = self._normalize_guild_id(config.get("guild_id"))
        if not guild_id:
            return
        
        # Get guild timezone
        scheduling = config.get("scheduling", {})
        timezone_str = scheduling.get("timezone", "UTC")
        
        try:
            import pytz
            tz = pytz.timezone(timezone_str)
        except Exception:
            logger.debug(f"[⏰] Invalid timezone {timezone_str} for guild {guild_id}, using UTC")
            import pytz
            tz = pytz.UTC
        
        now_local = utc_now.astimezone(tz)
        
        logger.debug(f"[⏰] Processing guild {guild_id} at {now_local.strftime('%H:%M')} {timezone_str}")
        
        # Get jobs registry
        jobs = scheduling.get("jobs", {})
        if not jobs:
            logger.debug(f"[⏰] No jobs configured for guild {guild_id}")
            return
        
        # Process all jobs for this guild
        await self._process_guild_jobs_recursive(
            guild_id=guild_id,
            config=config,
            jobs=jobs,
            now_local=now_local,
            timezone_str=timezone_str,
            path=""
        )

    def _normalize_guild_id(self, guild_id: Any) -> Optional[int]:
        """Normalize guild_id values from configs (int, str, or MongoDB $numberLong)."""
        if guild_id is None:
            return None
        try:
            if isinstance(guild_id, dict):
                if "$numberLong" in guild_id:
                    guild_id = guild_id["$numberLong"]
                else:
                    logger.warning(f"[⏰] Invalid guild id format: {guild_id}")
                    return None

            if not isinstance(guild_id, (int, str)):
                logger.warning(f"[⏰] Invalid guild id format: {guild_id}")
                return None

            normalized = int(guild_id)
            if normalized <= 0:
                logger.debug(f"[⏰] Skipping invalid guild id {guild_id}")
                return None
            return normalized
        except Exception:
            logger.warning(f"[⏰] Invalid guild id format: {guild_id}")
            return None
    
    async def _process_guild_jobs_recursive(
        self,
        guild_id: int,
        config: Dict[str, Any],
        jobs: Dict[str, Any],
        now_local: datetime,
        timezone_str: str,
        path: str
    ):
        """Recursively process guild jobs, traversing the nested job registry.
        
        Job registry can be nested (e.g., jobs.games.emoji, jobs.motd).
        We need to traverse the tree and find actual job configs.
        """
        for key, value in jobs.items():
            if not isinstance(value, dict):
                continue
            
            current_path = f"{path}.{key}" if path else key
            
            # Check if this is a job config (has enabled/time/schedule fields)
            if "enabled" in value or "time" in value or "schedule" in value:
                # This is a job - evaluate and dispatch
                job_type = current_path
                
                # Enrich job config with feature flags
                job_config = self._enrich_guild_job_config(config, current_path, value)
                
                logger.debug(f"[⏰] Evaluating guild job {job_type} for guild {guild_id}")
                
                await self._evaluate_and_dispatch_guild_job(
                    guild_id=guild_id,
                    job_type=job_type,
                    job_config=job_config,
                    now_local=now_local,
                    timezone_str=timezone_str
                )
            else:
                # This is a namespace - recurse
                await self._process_guild_jobs_recursive(
                    guild_id=guild_id,
                    config=config,
                    jobs=value,
                    now_local=now_local,
                    timezone_str=timezone_str,
                    path=current_path
                )
    
    def _enrich_guild_job_config(
        self,
        config: Dict[str, Any],
        job_path: str,
        job: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich job config with feature flags and defaults.
        
        Maps job paths to their feature flags:
        - games.emoji -> features.auto_game
        - motd -> features.motd
        """
        enriched = job.copy()
        features = config.get("features", {})
        
        # Map job paths to feature flags
        if job_path == "games.emoji":
            enriched["enabled"] = features.get("auto_game", False)
        elif job_path == "motd":
            enriched["enabled"] = features.get("motd", False)
        else:
            # Default: check if job has enabled field, otherwise False
            enriched.setdefault("enabled", False)
        
        return enriched
    
    async def _evaluate_and_dispatch_guild_job(
        self,
        guild_id: int,
        job_type: str,
        job_config: Dict[str, Any],
        now_local: datetime,
        timezone_str: str
    ):
        """Evaluate if a guild job should run and dispatch to registered handler.
        
        Args:
            guild_id: Guild ID
            job_type: Job type string (e.g., "games.emoji", "motd")
            job_config: Job configuration
            now_local: Current time in guild timezone
            timezone_str: Guild timezone string
        """
        # Must be enabled
        if not job_config.get("enabled", False):
            logger.debug(f"[⏰] Guild job {job_type} (guild {guild_id}) is disabled")
            return
        
        # Import schedule utilities for job evaluation
        try:
            from abby_core.discord.cogs.system.schedule_utils import (
                normalize_schedule_read,
                get_schedule_time,
                get_schedule_interval_minutes,
                calculate_next_interval_execution,
                should_run_date_based_job,
            )
        except ImportError as e:
            logger.error(f"[⏰] Failed to import schedule utils: {e}")
            return
        
        # Check if job should run
        should_run = False
        reason = "unknown"
        
        try:
            # Must be enabled
            if not job_config.get("enabled", False):
                reason = "not enabled"
            # Check for date-based schedule first
            elif "scheduled_date" in job_config and "scheduled_time" in job_config:
                if should_run_date_based_job(job_config, now_local):
                    should_run = True
                    reason = f"date-based job ready (scheduled for {job_config['scheduled_date']} at {job_config['scheduled_time']})"
                else:
                    reason = f"date-based job not ready (scheduled for {job_config.get('scheduled_date', '?')} at {job_config.get('scheduled_time', '?')})"
            else:
                # Normalize schedule and evaluate
                schedule = normalize_schedule_read(job_config)
                if not schedule:
                    reason = "no schedule configured"
                else:
                    schedule_type = schedule.get("type")
                    
                    if schedule_type == "daily":
                        job_time = get_schedule_time(schedule)
                        if not job_time:
                            reason = "no time configured"
                        else:
                            try:
                                job_hour, job_minute = map(int, job_time.split(":"))
                                if now_local.hour == job_hour and now_local.minute == job_minute:
                                    today_str = now_local.strftime("%Y-%m-%d")
                                    last_executed_at = job_config.get("last_executed_at")
                                    
                                    if last_executed_at:
                                        try:
                                            last_executed_date = datetime.fromisoformat(last_executed_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                                            if last_executed_date == today_str:
                                                reason = f"already ran today ({today_str})"
                                            else:
                                                should_run = True
                                                reason = "ready to run"
                                        except Exception:
                                            should_run = True
                                            reason = "ready to run"
                                    else:
                                        should_run = True
                                        reason = "ready to run"
                                else:
                                    reason = f"time mismatch (now={now_local.strftime('%H:%M')}, job={job_time})"
                            except (ValueError, AttributeError):
                                reason = f"invalid time format: {job_time}"
                    
                    elif schedule_type == "interval":
                        interval_minutes = get_schedule_interval_minutes(schedule)
                        if not interval_minutes:
                            reason = "no interval configured"
                        else:
                            jitter_minutes = schedule.get("jitter_minutes", 0)
                            last_executed_at = job_config.get("last_executed_at")
                            anchor_time = schedule.get("time", "00:00")
                            
                            try:
                                next_execution = calculate_next_interval_execution(
                                    anchor_time=anchor_time,
                                    interval_minutes=interval_minutes,
                                    last_executed_at=last_executed_at,
                                    jitter_minutes=jitter_minutes,
                                    timezone_str=timezone_str
                                )
                                
                                if now_local >= next_execution:
                                    should_run = True
                                    reason = f"ready to run (scheduled for {next_execution.strftime('%H:%M:%S')})"
                                else:
                                    time_until = (next_execution - now_local).total_seconds() / 60
                                    reason = f"not yet time (next in {time_until:.0f} minutes at {next_execution.strftime('%H:%M:%S')})"
                            except Exception as e:
                                reason = f"evaluation error: {e}"
                    else:
                        reason = f"unknown schedule type: {schedule_type}"
        except Exception as e:
            logger.error(f"[⏰] Error evaluating guild job {job_type}: {e}", exc_info=True)
            return
        
        if not should_run:
            logger.debug(f"[⏰] Guild job {job_type} (guild {guild_id}) skipped: {reason}")
            return
        
        logger.debug(f"[⏰] Guild job {job_type} (guild {guild_id}) ready: {reason}")
        
        # Import JOB_HANDLERS registry (Discord-specific handlers)
        try:
            from abby_core.discord.cogs.system.registry import JOB_HANDLERS
        except ImportError:
            logger.warning("[⏰] Failed to import JOB_HANDLERS registry - guild jobs will be skipped")
            return
        
        # Find handler
        # Try exact path, then fallback to leaf key
        handler = JOB_HANDLERS.get(job_type)
        if not handler and "." in job_type:
            leaf = job_type.split(".")[-1]
            handler = JOB_HANDLERS.get(leaf)
        
        if not handler:
            logger.warning(f"[⏰] No handler registered for guild job type: {job_type}")
            return
        
        # Dispatch to handler (must have bot for Discord operations)
        if not self.bot:
            logger.error(f"[⏰] Cannot dispatch guild job {job_type}: bot not available in scheduler service")
            return
        
        try:
            logger.info(f"[⏰] Executing guild job {job_type} for guild {guild_id}")
            # Guild handlers expect (bot, guild_id, job_config)
            await handler(self.bot, guild_id, job_config)
            logger.info(f"[⏰] Guild job {job_type} (guild {guild_id}) executed successfully")
        except Exception as e:
            logger.error(f"[⏰] Guild job {job_type} (guild {guild_id}) failed: {e}", exc_info=True)
    
    async def _process_job(self, job: Dict[str, Any], now: datetime):
        """Process a single job with atomic claim-and-execute pattern.
        
        Uses MongoDB's find_one_and_update to atomically claim the job
        before execution, preventing duplicate execution by concurrent
        scheduler instances.
        """
        job_id = str(job.get("_id", "unknown"))
        job_type = str(job.get("job_type", "unknown"))
        
        logger.debug(f"[⏰] Processing job check: {job_type} (id: {job_id})")
        
        # Check if job should run (preliminary check to avoid unnecessary claims)
        should_run, reason = self._should_run_job(job, now)
        
        if not should_run:
            logger.debug(f"[⏰] Skipping {job_type}: {reason}")
            return
        
        logger.debug(f"[⏰] Job {job_type} should run: {reason}")
        
        # ATOMIC CLAIM: Use find_one_and_update to claim the job
        # This prevents race conditions with concurrent scheduler instances
        logger.debug(f"[⏰] Attempting to claim job {job_type}...")
        claimed_job = self._try_claim_job(job, now)
        
        if not claimed_job:
            # Another scheduler instance claimed this job first
            logger.debug(f"[⏰] Job {job_id} ({job_type}) already claimed by another instance")
            return
        
        logger.debug(f"[⏰] Job {job_type} claimed successfully, executing...")
        
        # Get handler
        handler = self.handlers.get(job_type)
        if not handler:
            logger.warning(f"[⏰] No handler registered for job type: {job_type}")
            return
        
        logger.debug(f"[⏰] Found handler for {job_type}, building context...")
        
        # Build execution context
        context = {
            "job_id": job_id,
            "now": now,
            "guild_id": claimed_job.get("guild_id"),
            "scope": claimed_job.get("scope", "guild"),  # "guild" or "system"
        }
        
        # Execute handler
        try:
            start_time = datetime.now(timezone.utc)
            result = await handler.execute(claimed_job, context)
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            if SCHEDULER_VERBOSE:
                logger.debug(f"[⏰] Job {job_id} completed: {result.get('status', 'ok')} ({duration_seconds:.2f}s)")
            
            # Warn about long-running jobs (>30 seconds)
            # Note: guild_jobs_tick includes game execution time, so we bypass the warning for it
            if duration_seconds > 30 and job_type != "guild_jobs_tick":
                logger.warning(
                    f"[⚠️ long_job] Job {job_type} (id={job_id}) took {duration_seconds:.2f}s to complete. "
                    f"Consider optimizing or breaking into smaller tasks."
                )
            
            self._recent_jobs.append((now, job_type))
            if job_type == "bank_interest":
                processed = result.get("processed", 0) if isinstance(result, dict) else 0
                interest_paid = result.get("interest_paid", 0) if isinstance(result, dict) else 0
                try:
                    self._bank_interest_runs_since_summary += 1
                    self._bank_interest_processed_since_summary += int(processed)
                    self._bank_interest_paid_since_summary += int(interest_paid)
                except Exception:
                    pass
            
            # Note: last_run_at already updated by _try_claim_job
            
        except Exception as e:
            logger.error(f"[⏰] Job {job_id} failed: {e}", exc_info=True)
            self._recent_errors.append(now)
            # Rollback last_run_at on failure so job can retry
            self._rollback_job_claim(job_id, job.get("last_run_at"))
    
    def _try_claim_job(self, job: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        """Atomically claim a job for execution.
        
        Uses find_one_and_update with a conditional filter to ensure only
        one scheduler instance can claim the job. This prevents duplicate
        execution in multi-instance deployments.
        
        Args:
            job: Job document to claim
            now: Current timestamp
            
        Returns:
            Updated job document if claim succeeded, None if already claimed
        """
        db = get_database()
        jobs_collection = db["scheduler_jobs"]
        job_id = job.get("_id")
        
        # Build atomic claim filter
        # Only claim if last_run_at hasn't changed since we read it
        claim_filter = {
            "_id": job_id,
            "enabled": True,
        }
        
        # Include last_run_at in filter to detect concurrent updates
        last_run_at = job.get("last_run_at")
        if last_run_at:
            # Match exact value if set
            claim_filter["last_run_at"] = last_run_at
        else:
            # If never run (None or missing), use $in to match both cases
            claim_filter["last_run_at"] = {"$in": [None]}
        
        # Atomically update last_run_at and return updated document
        claimed_job = jobs_collection.find_one_and_update(
            claim_filter,
            {"$set": {"last_run_at": now.isoformat()}},
            return_document=True  # Return document AFTER update
        )
        
        return claimed_job
    
    def _rollback_job_claim(self, job_id: str, previous_last_run_at: Optional[Any]) -> None:
        """Rollback job claim on execution failure.
        
        Reverts last_run_at to allow retry on next tick.
        
        Args:
            job_id: Job ID to rollback
            previous_last_run_at: Previous last_run_at value to restore
        """
        db = get_database()
        jobs_collection = db["scheduler_jobs"]
        
        if previous_last_run_at:
            # Restore previous timestamp
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {"last_run_at": previous_last_run_at}}
            )
        else:
            # Remove last_run_at to mark as never run
            jobs_collection.update_one(
                {"_id": job_id},
                {"$unset": {"last_run_at": ""}}
            )
        
        logger.debug(f"[⏰] Rolled back claim for job {job_id}")
    
    def _should_run_job(self, job: Dict[str, Any], now: datetime) -> tuple[bool, str]:
        """
        Determine if a job should run right now.
        
        Returns:
            Tuple of (should_run, reason)
        """
        # Must be enabled
        if not job.get("enabled", False):
            return False, "not enabled"
        
        # Get schedule config
        schedule = job.get("schedule", {})
        schedule_type = schedule.get("type")
        
        if not schedule_type:
            return False, "no schedule type"
        
        # Get timezone
        tz_str = schedule.get("timezone", "UTC")
        try:
            tz = pytz.timezone(tz_str)
        except Exception:
            tz = pytz.UTC
        
        now_local = now.astimezone(tz)
        
        # Check schedule type
        if schedule_type == "interval":
            return self._should_run_interval_job(job, schedule, now, now_local)
        
        elif schedule_type == "daily":
            return self._should_run_daily_job(job, schedule, now, now_local)
        
        elif schedule_type == "date_based":
            return self._should_run_date_based_job(job, schedule, now, now_local)
        
        else:
            return False, f"unknown schedule type: {schedule_type}"
    
    def _should_run_interval_job(
        self,
        job: Dict[str, Any],
        schedule: Dict[str, Any],
        now: datetime,
        now_local: datetime,
    ) -> tuple[bool, str]:
        """Check if interval job should run."""
        every_minutes = schedule.get("every_minutes")
        if not every_minutes:
            return False, "no every_minutes configured"
        
        # Get last run time
        last_run_at = job.get("last_run_at")
        if last_run_at:
            if isinstance(last_run_at, str):
                last_run_at = datetime.fromisoformat(last_run_at)
            
            # Check if enough time has passed
            elapsed = (now - last_run_at).total_seconds() / 60
            if elapsed < every_minutes:
                return False, f"interval not met (elapsed: {elapsed:.1f}min, need: {every_minutes}min)"
        
        return True, f"interval ready (every {every_minutes}min)"
    
    def _should_run_daily_job(
        self,
        job: Dict[str, Any],
        schedule: Dict[str, Any],
        now: datetime,
        now_local: datetime,
    ) -> tuple[bool, str]:
        """Check if daily job should run."""
        time_str = schedule.get("time")
        if not time_str:
            return False, "no time configured"
        
        # Parse time
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception:
            return False, f"invalid time format: {time_str}"
        
        # Check if current time matches
        if now_local.hour != hour or now_local.minute != minute:
            return False, f"time not met (current: {now_local.strftime('%H:%M')}, target: {time_str})"
        
        # Check if already run today
        last_run_at = job.get("last_run_at")
        if last_run_at:
            if isinstance(last_run_at, str):
                last_run_at = datetime.fromisoformat(last_run_at)
            
            last_run_date = last_run_at.date()
            now_date = now_local.date()
            
            if last_run_date == now_date:
                return False, "already ran today"
        
        return True, f"daily time met ({time_str})"
    
    def _should_run_date_based_job(
        self,
        job: Dict[str, Any],
        schedule: Dict[str, Any],
        now: datetime,
        now_local: datetime,
    ) -> tuple[bool, str]:
        """Check if date-based job should run."""
        scheduled_date = schedule.get("scheduled_date")
        scheduled_time = schedule.get("scheduled_time")
        
        if not scheduled_date or not scheduled_time:
            return False, "no scheduled_date or scheduled_time"
        
        # Parse target datetime
        try:
            target_datetime = datetime.strptime(
                f"{scheduled_date} {scheduled_time}",
                "%Y-%m-%d %H:%M"
            )
            # Make timezone-aware
            tz_str = schedule.get("timezone", "UTC")
            tz = pytz.timezone(tz_str)
            target_datetime = tz.localize(target_datetime)
        except Exception as e:
            return False, f"invalid date/time: {e}"
        
        # Check if time has passed
        if now < target_datetime:
            return False, f"not yet time (target: {target_datetime.isoformat()})"
        
        # Check if already run
        last_run_at = job.get("last_run_at")
        if last_run_at:
            if isinstance(last_run_at, str):
                last_run_at = datetime.fromisoformat(last_run_at)
            
            if last_run_at >= target_datetime:
                return False, "already ran"
        
        return True, f"date-based job ready (scheduled: {target_datetime.isoformat()})"
    
    async def _maybe_emit_summary(self):
        """Emit a summary every N minutes (based on SCHEDULER_SUMMARY_INTERVAL_MINUTES)."""
        if not self._last_summary_time:
            return
        
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_summary_time).total_seconds() / 60  # Convert to minutes
        
        if elapsed >= SCHEDULER_SUMMARY_INTERVAL_MINUTES:
            window_start = now - timedelta(hours=SCHEDULER_SUMMARY_WINDOW_HOURS)

            while self._recent_jobs and self._recent_jobs[0][0] < window_start:
                self._recent_jobs.popleft()
            while self._recent_errors and self._recent_errors[0] < window_start:
                self._recent_errors.popleft()

            total_jobs = len(self._recent_jobs)
            total_errors = len(self._recent_errors)

            job_counts: Dict[str, int] = {}
            for _, job_type in self._recent_jobs:
                job_counts[job_type] = job_counts.get(job_type, 0) + 1

            if job_counts:
                sorted_jobs = sorted(job_counts.items(), key=lambda item: item[1], reverse=True)
                max_items = 8
                top_items = sorted_jobs[:max_items]
                remaining = len(sorted_jobs) - len(top_items)
                jobs_summary = ", ".join([f"{name}={count}" for name, count in top_items])
                if remaining > 0:
                    jobs_summary = f"{jobs_summary}, +{remaining} more"
            else:
                jobs_summary = "none"

            summary_msg = (
                f"[⏰] Scheduler Summary (last {SCHEDULER_SUMMARY_WINDOW_HOURS}h): "
                f"{total_jobs} jobs executed, {total_errors} errors | Jobs: {jobs_summary}"
            )
            logger.info(summary_msg)

            if self._bank_interest_runs_since_summary > 0:
                logger.info(
                    f"[🏦] Interest summary (last {SCHEDULER_SUMMARY_INTERVAL_MINUTES}m): "
                    f"processed {self._bank_interest_processed_since_summary} accounts, "
                    f"paid {self._bank_interest_paid_since_summary} BC total"
                )

            # Reset counters
            self._last_summary_time = now
            self._bank_interest_runs_since_summary = 0
            self._bank_interest_processed_since_summary = 0
            self._bank_interest_paid_since_summary = 0


# ============================================================================
# SCHEDULER SINGLETON
# ============================================================================

_scheduler_service: Optional[SchedulerService] = None


def reset_scheduler_service():
    """Reset the scheduler service singleton. Use for clean restarts/testing."""
    global _scheduler_service
    if _scheduler_service and _scheduler_service.running:
        _scheduler_service.running = False
        if _scheduler_service._task:
            _scheduler_service._task.cancel()
    _scheduler_service = None


def get_scheduler_service(bot: Optional[Any] = None) -> SchedulerService:
    """Get or create the singleton scheduler service.
    
    Args:
        bot: Optional Discord bot instance (used for guild-specific job dispatch)
        
    Returns:
        SchedulerService singleton
    """
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService(bot=bot)
    elif bot and not _scheduler_service.bot:
        # If bot wasn't available at first creation but is now, update it
        _scheduler_service.bot = bot
    return _scheduler_service


# ============================================================================
# JOB MANAGEMENT FUNCTIONS
# ============================================================================

def create_job(
    job_type: str,
    schedule: ScheduleConfig,
    guild_id: Optional[str] = None,
    scope: str = "guild",
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a new scheduled job.
    
    Args:
        job_type: Type of job (must have registered handler)
        schedule: Schedule configuration
        guild_id: Guild ID (for guild-scoped jobs)
        scope: "guild" or "system"
        config: Additional job-specific configuration
        
    Returns:
        Job ID
    """
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    job_doc = {
        "job_type": job_type,
        "enabled": schedule.enabled,
        "schedule": schedule.to_dict(),
        "guild_id": guild_id,
        "scope": scope,
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": None,
    }
    
    result = jobs_collection.insert_one(job_doc)
    logger.info(f"[⏰] Created job: {result.inserted_id} (type: {job_type}, scope: {scope})")
    return str(result.inserted_id)


def update_job_schedule(job_id: str, schedule: ScheduleConfig):
    """Update a job's schedule."""
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    jobs_collection.update_one(
        {"_id": job_id},
        {"$set": {
            "schedule": schedule.to_dict(),
            "enabled": schedule.enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    logger.info(f"[⏰] Updated schedule for job: {job_id}")


def enable_job(job_id: str):
    """Enable a job."""
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    jobs_collection.update_one(
        {"_id": job_id},
        {"$set": {"enabled": True}}
    )
    logger.info(f"[⏰] Enabled job: {job_id}")


def disable_job(job_id: str):
    """Disable a job."""
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    jobs_collection.update_one(
        {"_id": job_id},
        {"$set": {"enabled": False}}
    )
    logger.info(f"[⏰] Disabled job: {job_id}")


def delete_job(job_id: str):
    """Delete a job."""
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    jobs_collection.delete_one({"_id": job_id})
    logger.info(f"[⏰] Deleted job: {job_id}")


def list_jobs(
    guild_id: Optional[str] = None,
    scope: Optional[str] = None,
    job_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List jobs with optional filters.
    
    Args:
        guild_id: Filter by guild
        scope: Filter by scope ("guild" or "system")
        job_type: Filter by job type
        
    Returns:
        List of job documents
    """
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    query = {}
    if guild_id:
        query["guild_id"] = guild_id
    if scope:
        query["scope"] = scope
    if job_type:
        query["job_type"] = job_type
    
    return list(jobs_collection.find(query))
