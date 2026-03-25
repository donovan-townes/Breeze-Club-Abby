"""
Scheduler Job Registry

Provides a single shared registry for scheduled job handlers and a decorator
for registration. Import from this module to avoid duplicate module instances
and keep the JOB_HANDLERS dict consistent across files.
"""

from typing import Dict, Any, Callable, Awaitable, TypedDict

try:
    from tdos_intelligence.observability import logging
    logger = logging.getLogger(__name__)
except Exception:
    logger = None


# ════════════════════════════════════════════════════════════════════════════════
# JOB METADATA - Display information for UI rendering
# ════════════════════════════════════════════════════════════════════════════════

class JobMetadata(TypedDict):
    """Metadata for displaying a job in the UI."""
    category: str      # Display grouping (e.g., "System Jobs")
    label: str         # Human-readable name
    icon: str          # Emoji icon
    editable: bool     # Whether users can edit the schedule
    description: str   # Optional description for tooltips/help


JOB_METADATA: Dict[str, JobMetadata] = {
    # System Jobs - Platform-level automation
    "system.season_rollover": {
        "category": "System Jobs",
        "label": "Season Rollover",
        "icon": "🌍",
        "editable": False,
        "description": "Platform-wide seasonal transitions (XP resets, canon changes)"
    },
    "system.event_lifecycle": {
        "category": "System Jobs",
        "label": "Event Lifecycle",
        "icon": "📅",
        "editable": False,
        "description": "Platform-wide event auto-start/auto-end based on date boundaries (Valentine's, Easter, etc.)"
    },
    "system.daily_world_announcements": {
        "category": "System Jobs",
        "label": "Daily World Announcements (Legacy)",
        "icon": "📢",
        "editable": False,
        "description": "DEPRECATED: Handled by unified_content_dispatcher. This job does nothing but prevents warnings."
    },
    "system.announcements.daily_world_announcements": {
        "category": "System Jobs",
        "label": "World Announcements (Legacy)",
        "icon": "🌍",
        "editable": False,
        "description": "DEPRECATED: Handled by unified_content_dispatcher. Season transitions automatically queue announcements."
    },
    "system.motd": {
        "category": "System Jobs",
        "label": "Message of the Day",
        "icon": "📅",
        "editable": True,
        "description": "Daily announcements in the MOTD channel"
    },
    "system.xp_rewards.daily_bonus": {
        "category": "System Jobs",
        "label": "XP Daily Bonus",
        "icon": "💰",
        "editable": True,
        "description": "Daily XP bonus rewards"
    },
    "system.giveaways": {
        "category": "System Jobs",
        "label": "Giveaway Checks",
        "icon": "🎁",
        "editable": True,
        "description": "Periodic giveaway winner selection"
    },
    "system.maintenance.memory_decay": {
        "category": "System Jobs",
        "label": "Memory Maintenance",
        "icon": "🤖",
        "editable": True,
        "description": "Automated memory decay cleanup"
    },
    
    # Games Jobs - Game-related automation
    "games.emoji": {
        "category": "Games Jobs",
        "label": "Emoji Game",
        "icon": "🎮",
        "editable": True,
        "description": "Automated emoji guessing game"
    },
    
    # Community Jobs - Community engagement automation
    "community.random_messages": {
        "category": "Community Jobs",
        "label": "Random Messages",
        "icon": "💬",
        "editable": True,
        "description": "Periodic random messages in designated channel"
    },
    "community.nudge": {
        "category": "Community Jobs",
        "label": "User Nudges",
        "icon": "👈",
        "editable": True,
        "description": "Engagement nudges for inactive users"
    },
}


# ════════════════════════════════════════════════════════════════════════════════
# JOB HANDLER REGISTRY - Execution handlers
# ════════════════════════════════════════════════════════════════════════════════

# Shared registry of job handlers
JOB_HANDLERS: Dict[str, Callable[[Any, int, Dict[str, Any]], Awaitable[None]]] = {}


def register_job_handler(job_type: str):
    """
    Decorator to register a job handler for the specified job type.

    Example:
        @register_job_handler("games.emoji")
        async def handle_emoji_game(bot, guild_id, job_config):
            pass
    """
    def decorator(func: Callable[[Any, int, Dict[str, Any]], Awaitable[None]]):
        JOB_HANDLERS[job_type] = func
        if logger:
            logger.debug(f"[⏰] Handler registered for job type: {job_type}")
        return func
    return decorator
