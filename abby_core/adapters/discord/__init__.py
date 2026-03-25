"""Discord Adapter for Abby Core

This module re-exports Discord configuration from abby_core.discord.config
so that service adapters and other modules can import from a consistent location.

All Discord configuration lives in abby_core.discord.config - this is just
a convenience re-export for consistency with the adapter pattern.
"""

from abby_core.discord.config import (
    get_discord_config,
    get_guild_config,
    register_guild,
    clear_guild_config_cache,
    DiscordConfig,
    DiscordChannels,
    DiscordRoles,
    DiscordEmojis,
)

__all__ = [
    'get_discord_config',
    'get_guild_config',
    'register_guild',
    'clear_guild_config_cache',
    'DiscordConfig',
    'DiscordChannels',
    'DiscordRoles',
    'DiscordEmojis',
]
