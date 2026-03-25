"""Discord platform adapter for intent actions.

Implements the abby_core.llm.interfaces abstractions for Discord,
providing type-safe context builders and tool execution helpers.

This module bridges the platform-agnostic intent routing (intent.py,
intent_tools.py) and Discord-specific client operations.
"""

from typing import Any, Dict, Optional
import logging

try:  # Prefer shared observability logger when available
    from tdos_intelligence.observability import logging as obs_logging  # type: ignore
    logger = obs_logging.getLogger(__name__)
except Exception:  # pragma: no cover - fallback to stdlib logger
    import logging
    logger = logging.getLogger(__name__)


def build_intent_context(
    *,
    user: Any,  # discord.User or discord.Member
    guild: Optional[Any] = None,  # discord.Guild
    bot: Optional[Any] = None,  # discord.Client
    message_content: str = "",
    user_level: str = "member",
    is_owner: bool = False,
) -> Dict[str, Any]:
    """Build platform-agnostic intent routing context from Discord objects.
    
    Args:
        user: Discord user/member making the request
        guild: Discord guild (server)
        bot: Discord bot client
        message_content: Original user message
        user_level: User privilege level (member, moderator, admin, owner)
        is_owner: Whether user is guild owner
    
    Returns:
        Context dict for intent routing
    """
    return {
        "user": user,
        "guild": guild,
        "bot": bot,
        "user_message": message_content,
        "user_level": user_level,
        "is_owner": is_owner,
        "is_owner_check": is_owner,  # Alias for clarity
    }
