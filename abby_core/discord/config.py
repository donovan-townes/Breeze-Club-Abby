"""
Discord Configuration (abby_core)

This module contains Discord-specific configuration:
    - Channel IDs
    - Role IDs  
    - Custom Emoji mappings
    - Guild/Server information
    - Discord Bot Token

All other configuration (API keys, database, LLM, storage, etc.) is in:
    abby_core.config.BotConfig

This is the primary location for Discord configuration. Service adapters can import from here.

Usage:
    from abby_core.discord.config import get_discord_config
    
    discord_config = get_discord_config()
    channel_id = discord_config.channels.breeze_lounge
    role_id = discord_config.roles.musician
    emoji = discord_config.emojis.leaf_heart

For unified access (legacy cogs):
    from abby_core.discord.config import config
    channel_id = config.channels.breeze_lounge  # Discord config
    api_key = config.api.openai_key  # Core config (via bridge properties)
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
from abby_core.config import get_config as get_core_config

# Load environment variables
load_dotenv()


def getenv_int(key: str, default: str) -> int:
    """Get integer environment variable with fallback."""
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return int(default)


@dataclass
class DiscordChannels:
    """Discord Channel IDs"""
    # Main channels
    breeze_lounge: int = 802512963519905852
    breeze_club_general: int = 547471286801268777
    abby_chat: int = 1103490012500201632
    breeze_fam_role: int = 807664341158592543
    
    # Content channels
    breeze_memes: int = 1111136459072753664
    welcome_leaf: int = 858231410682101782
    
    # Giveaway & Events
    gust_channel: int = 802461884091465748
    giveaway_channel: int = 802461884091465748
    
    # Voice & Radio
    radio_channel: int = 839379779790438430
    
    # Testing
    test_channel: int = 1103490012500201632
    
    # Configurable channels from env (can be overridden per-guild)
    motd_channel: int = field(default_factory=lambda: getenv_int("MOTD_CHANNEL_ID", "0"))
    nudge_channel: int = field(default_factory=lambda: getenv_int("NUDGE_CHANNEL_ID", "0"))
    xp_channel: int = field(default_factory=lambda: getenv_int("XP_CHANNEL_ID", "802512963519905852"))
    xp_abby_chat: int = field(default_factory=lambda: getenv_int("XP_ABBY_CHAT_ID", "1103490012500201632"))
    auto_game_channel: int = field(default_factory=lambda: getenv_int("AUTO_GAME_CHANNEL_ID", "802512963519905852"))


@dataclass
class DiscordServerInfo:
    """Discord Server/Guild Information"""
    # Main guild ID (customize for your server)
    guild_id: int = field(default_factory=lambda: getenv_int("DISCORD_GUILD_ID", "547471286801268777"))
    
    # Developer/Admin IDs
    developer_id: int = 268871091550814209  # Customize for your developers
    owner_user_id: int = field(default_factory=lambda: getenv_int("OWNER_USER_ID", "0"))


@dataclass
class DiscordRoles:
    """Discord Role IDs"""
    musician: int = 808129993460023366
    streamer: int = 1131231727675768953
    gamer: int = 1131920998350995548
    developer: int = 1131231948862398625
    artist: int = 1131703899842154576
    nft_artist: int = 1131704410393813003
    writer: int = 1131704091366654094
    z8phyr_fan: int = 807678887777140786
    
    # Canon system roles (from .env)
    canon_editor: int = field(default_factory=lambda: getenv_int("CANON_EDITOR_ROLE_ID", "0"))
    trusted_contributor: int = field(default_factory=lambda: getenv_int("TRUSTED_CONTRIBUTOR_ROLE_ID", "0"))


@dataclass
class DiscordEmojis:
    """Discord Custom Emojis and Reactions"""
    leaf_heart: str = "<a:z8_leafheart_excited:806057904431693824>"
    abby_run: str = "<a:Abby_run:1135375927589748899>"
    abby_idle: str = "<a:Abby_idle:1135376647495884820>"
    up_arrow: str = "⬆️"
    down_arrow: str = "⬇️"
    next_arrow: str = "➡️"


@dataclass
class DiscordBotInfo:
    """Discord Bot Token and Auth"""
    token: str = field(default_factory=lambda: os.getenv("ABBY_TOKEN", "") or os.getenv("DISCORD_BOT_TOKEN", ""))
    developer_token: Optional[str] = field(default_factory=lambda: os.getenv("DEVELOPER_TOKEN") or os.getenv("DISCORD_BOT_TOKEN_DEV"))
    
    def get_token(self, is_dev: bool = False) -> str:
        """
        Get appropriate token based on environment.
        
        Args:
            is_dev: True if running in development mode
            
        Returns:
            Discord bot token (dev token if available and is_dev=True, otherwise prod token)
        """
        if is_dev and self.developer_token:
            return self.developer_token
        return self.token
    
    def validate(self) -> list[str]:
        """Validate Discord configuration."""
        issues = []
        if not self.token and not self.developer_token:
            issues.append("❌ CRITICAL: No Discord token configured (set DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN_DEV)")
        return issues


@dataclass
class DiscordConfig:
    """Master Discord Configuration"""
    channels: DiscordChannels = field(default_factory=DiscordChannels)
    roles: DiscordRoles = field(default_factory=DiscordRoles)
    emojis: DiscordEmojis = field(default_factory=DiscordEmojis)
    server_info: DiscordServerInfo = field(default_factory=DiscordServerInfo)
    bot: DiscordBotInfo = field(default_factory=DiscordBotInfo)
    
    def validate(self) -> list[str]:
        """Validate all Discord configuration."""
        issues = []
        issues.extend(self.bot.validate())
        return issues
    
    def print_summary(self):
        """Print Discord configuration summary for debugging."""
        print("\n" + "="*70)
        print("🎭 DISCORD CONFIGURATION")
        print("="*70)
        
        print(f"\n🤖 Bot:")
        print(f"  Token: {'✅ Set' if self.bot.token else '❌ NOT SET'}")
        print(f"  Developer Token: {'✅ Set' if self.bot.developer_token else '⚠️  Not set'}")
        
        print(f"\n📟 Server Info:")
        print(f"  Guild ID: {self.server_info.guild_id}")
        print(f"  Owner ID: {self.server_info.owner_user_id}")
        print(f"  Developer ID: {self.server_info.developer_id}")
        
        print(f"\n📍 Key Channels:")
        print(f"  Breeze Lounge: {self.channels.breeze_lounge}")
        print(f"  Breeze Club General: {self.channels.breeze_club_general}")
        print(f"  Abby Chat: {self.channels.abby_chat}")
        print(f"  MOTD: {self.channels.motd_channel if self.channels.motd_channel else '⚠️  Not configured'}")
        print(f"  XP: {self.channels.xp_channel}")
        
        print(f"\n👥 Sample Roles:")
        print(f"  Musician: {self.roles.musician}")
        print(f"  Developer: {self.roles.developer}")
        print(f"  Artist: {self.roles.artist}")
        
        # Validation
        issues = self.validate()
        if issues:
            print(f"\n⚠️  Configuration Issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"\n✅ Configuration Valid")
        
        print("="*70 + "\n")


# Singleton pattern for Discord configuration
_discord_config: Optional[DiscordConfig] = None


def get_discord_config() -> DiscordConfig:
    """
    Get or create the global DiscordConfig instance.
    
    This is a singleton - configuration is loaded once and reused.
    
    Returns:
        DiscordConfig: The global Discord configuration instance
    
    Usage:
        from abby_core.discord.config import get_discord_config
        
        discord_config = get_discord_config()
        channel_id = discord_config.channels.breeze_lounge
        role_id = discord_config.roles.musician
    """
    global _discord_config
    if _discord_config is None:
        _discord_config = DiscordConfig()
    return _discord_config


# ============================================================================
# GUILD-SPECIFIC CONFIGURATION
# ============================================================================
# Cache for guild-specific configs (loaded from database)
_guild_configs: dict[int, DiscordConfig] = {}


async def get_guild_config(guild_id: int) -> DiscordConfig:
    """
    Get guild-specific Discord configuration.
    
    Returns the default configuration with any guild-specific overrides
    applied from the database. If the guild hasn't been registered yet,
    returns the default configuration.
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        DiscordConfig: Configuration for the guild (defaults + overrides)
    
    Usage:
        # In a cog or command
        guild_config = await get_guild_config(ctx.guild.id)
        motd_channel = guild_config.channels.motd_channel
    """
    # Check cache first
    if guild_id in _guild_configs:
        return _guild_configs[guild_id]
    
    # Load from database if exists
    try:
        from abby_core.database.mongodb import get_database
        db = get_database()
        
        guild_settings = db.guild_settings.find_one({"guild_id": guild_id})
        if guild_settings and "discord_config" in guild_settings:
            # Create config from stored settings, with defaults as fallback
            config = DiscordConfig()
            stored = guild_settings["discord_config"]
            
            # Override channels if stored
            if "channels" in stored:
                for key, value in stored["channels"].items():
                    if hasattr(config.channels, key) and value:
                        setattr(config.channels, key, value)
            
            # Override roles if stored
            if "roles" in stored:
                for key, value in stored["roles"].items():
                    if hasattr(config.roles, key) and value:
                        setattr(config.roles, key, value)
            
            # Cache and return
            _guild_configs[guild_id] = config
            return config
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to load guild config for {guild_id}: {e}. Using defaults."
        )
    
    # Return defaults if not found or error
    default_config = get_discord_config()
    _guild_configs[guild_id] = default_config
    return default_config


async def register_guild(
    guild_id: int,
    channel_overrides: Optional[dict[str, int]] = None,
    role_overrides: Optional[dict[str, int]] = None,
) -> DiscordConfig:
    """
    Register a guild when the bot joins, optionally with custom channel/role settings.
    
    This creates a guild-specific configuration entry in the database.
    Future calls to get_guild_config(guild_id) will return these custom settings
    merged with defaults.
    
    Args:
        guild_id: Discord guild ID
        channel_overrides: Dict of channel names to IDs (e.g., {"motd_channel": 12345})
        role_overrides: Dict of role names to IDs (e.g., {"musician": 67890})
    
    Returns:
        DiscordConfig: The newly registered configuration for the guild
    
    Usage:
        # In on_guild_join event
        @bot.event
        async def on_guild_join(guild):
            config = await register_guild(guild.id)
            print(f"Registered {guild.name} with default config")
    """
    try:
        from abby_core.database.mongodb import get_database
        db = get_database()
        
        # Build guild settings document
        guild_settings = {
            "guild_id": guild_id,
            "discord_config": {}
        }
        
        if channel_overrides:
            guild_settings["discord_config"]["channels"] = channel_overrides
        if role_overrides:
            guild_settings["discord_config"]["roles"] = role_overrides
        
        # Upsert into database
        db.guild_settings.update_one(
            {"guild_id": guild_id},
            {"$set": guild_settings},
            upsert=True
        )
        
        # Clear cache to force reload
        _guild_configs.pop(guild_id, None)
        
        # Return the config
        return await get_guild_config(guild_id)
    
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to register guild {guild_id}: {e}")
        return get_discord_config()


def clear_guild_config_cache(guild_id: Optional[int] = None) -> None:
    """
    Clear the guild configuration cache.
    
    Call this after updating guild settings to force a reload from database.
    
    Args:
        guild_id: Specific guild to clear. If None, clears entire cache.
    """
    global _guild_configs
    if guild_id is None:
        _guild_configs.clear()
    else:
        _guild_configs.pop(guild_id, None)


# ============================================================================
# BACKWARDS COMPATIBILITY BRIDGE
# ============================================================================
# Create a unified configuration class for legacy cogs that import:
#   from abby_core.discord.config import config

@dataclass
class BotConfig:
    """
    Unified configuration combining core and Discord-specific settings.
    
    This class exists for backwards compatibility with legacy cogs.
    All existing cogs importing `from abby_core.discord.config import config`
    will continue to work without changes.
    
    NEW CODE should import directly:
        from abby_core.config import get_config
        from abby_core.discord.config import get_discord_config
    """
    
    # Core configuration (from abby_core)
    @property
    def api(self):
        """API configuration (OpenAI, Stability, etc.)"""
        return get_core_config().api
    
    @property
    def database(self):
        """Database configuration (MongoDB, Qdrant, etc.)"""
        return get_core_config().database
    
    @property
    def storage(self):
        """Storage configuration"""
        return get_core_config().storage
    
    @property
    def llm(self):
        """LLM configuration"""
        return get_core_config().llm
    
    @property
    def rag(self):
        """RAG configuration"""
        return get_core_config().rag
    
    @property
    def features(self):
        """Feature flags"""
        return get_core_config().features
    
    @property
    def timing(self):
        """Timing configuration"""
        return get_core_config().timing
    
    @property
    def paths(self):
        """Path configuration"""
        return get_core_config().paths
    
    @property
    def telemetry(self):
        """Telemetry configuration"""
        return get_core_config().telemetry
    
    @property
    def misc(self):
        """Miscellaneous configuration"""
        return get_core_config().misc
    
    @property
    def logging(self):
        """Logging configuration"""
        return get_core_config().logging
    
    # Discord-specific configuration
    @property
    def channels(self):
        """Discord channel IDs"""
        return get_discord_config().channels
    
    @property
    def roles(self):
        """Discord role IDs"""
        return get_discord_config().roles
    
    @property
    def emojis(self):
        """Discord custom emojis"""
        return get_discord_config().emojis
    
    @property
    def server_info(self):
        """Discord server/guild information"""
        return get_discord_config().server_info
    
    @property
    def bot(self):
        """Discord bot info (token, developer_token, etc.)"""
        return get_discord_config().bot
    
    @property
    def mode(self):
        """Bot mode (prod, dev, etc.)"""
        return get_core_config().mode
    
    @property
    def debug(self):
        """Debug flag"""
        return get_core_config().debug
    
    def load_welcome_phrases(self) -> list[str]:
        """
        Load welcome phrases from the configured JSON file.
        
        Returns:
            List of welcome phrase strings
        """
        import json
        from pathlib import Path
        
        try:
            # Use the path configured in core config
            phrases_path = Path(self.paths.welcome_phrases_file)
            
            if phrases_path.exists():
                with open(phrases_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle both list format and dict format with 'phrases' key
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and 'phrases' in data:
                        return data['phrases']
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load welcome phrases: {e}")
        
        # Return default phrases if file not found
        return [
            "Welcome to the Breeze Club!",
            "Glad to see you here!",
            "Thanks for joining our community!",
        ]


# Singleton instance for backwards compatibility
# This is what existing code uses: `from abby_core.discord.config import config`
config = BotConfig()

# Export for public API
__all__ = [
    'config',  # Legacy singleton instance
    'BotConfig',  # Legacy unified config class
    'get_discord_config',  # Default config singleton
    'get_guild_config',  # Guild-specific config with overrides
    'register_guild',  # Register guild on bot join
    'clear_guild_config_cache',  # Clear cache after updates
    'DiscordConfig',
    'DiscordChannels',
    'DiscordRoles',
    'DiscordEmojis',
    'DiscordServerInfo',
    'DiscordBotInfo',
]


if __name__ == "__main__":
    # Test configuration when run directly
    discord_cfg = get_discord_config()
    discord_cfg.print_summary()
