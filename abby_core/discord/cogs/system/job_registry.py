"""
Job Handler Registry Configuration

This module registers all background job handlers with the scheduler.

Unified announcement system active
- Announcement generation and delivery consolidated into unified_content_dispatcher.py
- All content flows through content_delivery_items collection
"""

from typing import Any, Callable, Dict, Optional
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

# Global registry of job handlers
_job_handlers: Dict[str, Callable] = {}


def register_job_handler(job_name: str):
    """
    Decorator to register a job handler.
    
    Usage:
        @register_job_handler("community.daily_announcement")
        async def handle_daily_announcement(bot, guild_id, job_config):
            ...
    
    Args:
        job_name: Unique job identifier
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        _job_handlers[job_name] = func
        logger.debug(f"[Registry] Registered job handler: {job_name}")
        return func
    return decorator


def get_job_handler(job_name: str) -> Optional[Callable]:
    """Get a registered job handler by name."""
    return _job_handlers.get(job_name)


def list_job_handlers() -> Dict[str, Callable]:
    """List all registered job handlers."""
    return _job_handlers.copy()


# ==================== JOB HANDLER REGISTRATION ====================

# Unified content dispatcher (Phase 3: primary handler only)
try:
    from abby_core.discord.cogs.system.jobs.unified_content_dispatcher import (
        execute_unified_content_dispatcher,
    )
    
    @register_job_handler("community.unified_content_dispatcher")
    async def handle_unified_content_dispatch(
        bot: Any, 
        guild_id: Optional[int] = None, 
        job_config: Optional[Dict[str, Any]] = None
    ):
        """
        Unified content dispatcher: generation + delivery + cleanup.
        
        Consolidates all announcement types (system, world, scheduled) into a single
        pipeline with unified lifecycle management via content_delivery_items collection.
        
        Schedule: Every 60 seconds
        
        Returns:
            (generated_count, delivered_count, archived_count)
        """
        return await execute_unified_content_dispatcher(bot, job_config)
    
    logger.debug("[Registry] Unified content dispatcher registered")
    
except Exception as e:
    logger.error(f"[Registry] ❌ Failed to register unified dispatcher: {e}")


# ==================== OTHER JOB HANDLERS ====================

# These handlers are unaffected by the unification and remain unchanged

try:
    from abby_core.discord.cogs.system.jobs.season_rollover import (
        execute_season_rollover,
    )
    
    @register_job_handler("system.season_rollover")
    async def handle_season_rollover(
        bot: Any,
        guild_id: Optional[int] = None,
        job_config: Optional[Dict[str, Any]] = None
    ):
        """
        Season rollover: check if current season is due, transition if needed.
        
        Schedule: Daily at 00:00 UTC
        """
        return await execute_season_rollover(bot, guild_id or 0, job_config or {})
    
    logger.debug("[Registry] Season rollover registered")

except Exception as e:
    logger.warning(f"[Registry] Failed to register season_rollover: {e}")


# ==================== LOGGING ====================

def log_registry_status():
    """Log the current job handler registry status."""
    logger.info(
        f"[Registry] Job handler status:\n"
        f"  - Unified dispatcher active\n"
        f"  - Total handlers registered: {len(_job_handlers)}\n"
        f"  - Handlers: {list(_job_handlers.keys())}"
    )


def verify_job_registry() -> bool:
    """
    Verify that job registry is properly configured.
    
    Returns:
        bool: True if registry is valid, False otherwise
    """
    log_registry_status()
    
    if "community.unified_content_dispatcher" not in _job_handlers:
        logger.error("[Registry] ❌ Unified dispatcher not registered!")
        return False
    
    logger.debug("[Registry] ✅ Unified dispatcher verified and active")
    return True