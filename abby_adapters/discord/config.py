"""
Centralized Configuration for Abby Discord Adapter

This module consolidates all environment variables, channel IDs, feature flags,
and system settings into a single, validated configuration system.

Usage:
    from abby_adapters.discord.config import config
    channel_id = config.channels.breeze_lounge
    api_key = config.api.stability_key
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def getenv_bool(key: str, default: str = "false") -> bool:
    """Get boolean environment variable."""
    return os.getenv(key, default).lower() == "true"


def getenv_int(key: str, default: str) -> int:
    """Get integer environment variable with fallback."""
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return int(default)


def getenv_float(key: str, default: str) -> float:
    """Get float environment variable with fallback."""
    try:
        return float(os.getenv(key, default))
    except (ValueError, TypeError):
        return float(default)


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
    
    # Configurable channels from env
    motd_channel: int = field(default_factory=lambda: getenv_int("MOTD_CHANNEL_ID", "0"))
    nudge_channel: int = field(default_factory=lambda: getenv_int("NUDGE_CHANNEL_ID", "0"))
    xp_channel: int = field(default_factory=lambda: getenv_int("XP_CHANNEL_ID", "802512963519905852"))
    xp_abby_chat: int = field(default_factory=lambda: getenv_int("XP_ABBY_CHAT_ID", "1103490012500201632"))


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
class APIKeys:
    """External API Keys and Credentials"""
    # Core bot
    discord_token: str = field(default_factory=lambda: os.getenv("ABBY_TOKEN", ""))
    developer_token: str = field(default_factory=lambda: os.getenv("DEVELOPER_TOKEN", ""))
    
    # AI Services
    openai_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    stability_key: str = field(default_factory=lambda: os.getenv("STABILITY_API_KEY", ""))
    
    # Social Media
    youtube_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    twitter_api_key: str = field(default_factory=lambda: os.getenv("TWITTER_API_KEY", ""))
    twitter_api_secret: str = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET", ""))
    twitter_access_token: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN", ""))
    twitter_access_token_secret: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""))
    twitter_bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))
    
    # Twitch
    twitch_client_id: str = field(default_factory=lambda: os.getenv("TWITCH_CLIENT_ID", ""))
    twitch_client_secret: str = field(default_factory=lambda: os.getenv("TWITCH_CLIENT_SECRET", ""))
    twitch_oauth: str = field(default_factory=lambda: os.getenv("TWITCH_OAUTH", ""))
    twitch_bot_id: str = field(default_factory=lambda: os.getenv("TWITCH_BOT_ID", ""))
    
    # Image Generation
    stability_api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "https://api.stability.ai"))


@dataclass
class DatabaseConfig:
    """Database Configuration"""
    # MongoDB
    mongodb_uri: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_URI"))
    mongodb_user: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_USER"))
    mongodb_pass: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_PASS"))
    mongodb_db: str = field(default_factory=lambda: os.getenv("MONGODB_DB", "Abby_Database"))
    
    # Qdrant (Vector DB for RAG)
    qdrant_host: str = field(default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"))
    qdrant_port: int = field(default_factory=lambda: getenv_int("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = field(default_factory=lambda: os.getenv("QDRANT_API_KEY"))
    
    # Chroma (Legacy Vector DB)
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./chroma-data"))


@dataclass
class LLMConfig:
    """Large Language Model Configuration"""
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama").lower())
    
    # Ollama
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    
    # OpenAI
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    
    # General
    timeout: float = field(default_factory=lambda: getenv_float("LLM_TIMEOUT", "30"))
    
    # Embeddings
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    embedding_device: str = field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))


@dataclass
class FeatureFlags:
    """Feature Toggles and Experimental Features"""
    # Core features
    rag_enabled: bool = field(default_factory=lambda: getenv_bool("RAG_CONTEXT_ENABLED", "false"))
    nudge_enabled: bool = field(default_factory=lambda: getenv_bool("NUDGE_ENABLED", "false"))
    image_auto_move_enabled: bool = field(default_factory=lambda: getenv_bool("IMAGE_AUTO_MOVE_ENABLED", "false"))
    
    # Development
    dry_run_mode: bool = field(default_factory=lambda: getenv_bool("MIGRATE_DRY_RUN", "false"))


@dataclass
class TimingConfig:
    """Timing, Intervals, and Cooldowns"""
    # XP System
    xp_message_cooldown_seconds: int = field(default_factory=lambda: getenv_int("XP_MESSAGE_COOLDOWN_SECONDS", "60"))
    xp_attachment_cooldown_seconds: int = field(default_factory=lambda: getenv_int("XP_ATTACHMENT_COOLDOWN_SECONDS", "600"))
    xp_stream_interval_minutes: int = field(default_factory=lambda: getenv_int("XP_STREAM_INTERVAL_MINUTES", "5"))
    xp_daily_start_hour: int = field(default_factory=lambda: getenv_int("XP_DAILY_START_HOUR", "5"))
    
    # Twitch
    twitch_poll_minutes: int = field(default_factory=lambda: getenv_int("TWITCH_POLL_MINUTES", "15"))
    
    # Nudges
    nudge_interval_hours: int = field(default_factory=lambda: getenv_int("NUDGE_INTERVAL_HOURS", "24"))
    
    # MOTD
    motd_start_hour: int = field(default_factory=lambda: getenv_int("MOTD_START_HOUR", "5"))


@dataclass
class PathConfig:
    """File System Paths"""
    # Base directories
    working_dir: Path = field(default_factory=lambda: Path(os.getenv("WORKING_DIRECTORY", os.getcwd())))
    
    # Media directories
    songs_dir: Path = field(default_factory=lambda: Path(os.getenv("SONGS_DIR", "songs")))
    images_dir: Path = field(default_factory=lambda: Path(os.getenv("IMAGES_DIR", "Images")))
    audio_recordings: Path = field(default_factory=lambda: Path(os.getenv("AUDIO_ROOT", "Audio_Recordings")))
    
    # Configuration files
    welcome_phrases_file: Path = field(default_factory=lambda: Path("abby_adapters/discord/data/welcome_phrases.json"))
    
    # TDOS Telemetry
    tdos_events_path: Path = field(default_factory=lambda: Path(os.getenv("TDOS_EVENTS_PATH", "shared/logs/events.jsonl")))


@dataclass
class StorageConfig:
    """Centralized File Storage Configuration"""
    # Storage root directory
    storage_root: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "shared")))
    
    # Storage limits (quota management)
    max_global_storage_mb: int = field(default_factory=lambda: getenv_int("MAX_GLOBAL_STORAGE_MB", "5000"))
    max_user_storage_mb: int = field(default_factory=lambda: getenv_int("MAX_USER_STORAGE_MB", "500"))
    max_user_daily_gens: int = field(default_factory=lambda: getenv_int("MAX_USER_DAILY_GENS", "5"))
    
    # Cleanup policy
    cleanup_days: int = field(default_factory=lambda: getenv_int("STORAGE_CLEANUP_DAYS", "7"))
    
    # Image generation specific
    image_generation_size_mb: float = field(default_factory=lambda: getenv_float("IMAGE_GEN_SIZE_MB", "1.5"))

    # Quota overrides
    @dataclass
    class QuotaOverrideConfig:
        owner_user_ids: List[str] = field(default_factory=lambda: [uid for uid in os.getenv("OWNER_USER_ID", "").split(",") if uid])
        owner_daily_limit: int = field(default_factory=lambda: getenv_int("OWNER_DAILY_GENS", "9999"))
        role_daily_limits: Dict[str, int] = field(default_factory=dict)
        level_bands: List[Dict[str, int]] = field(default_factory=lambda: [
            {"min_level": 1, "daily_limit": 10},
            {"min_level": 5, "daily_limit": 25},
            {"min_level": 10, "daily_limit": 50},
        ])

    quota_overrides: QuotaOverrideConfig = field(default_factory=QuotaOverrideConfig)
    
    def get_images_dir(self) -> Path:
        """Get images directory path."""
        return self.storage_root / "images"
    
    def get_temp_dir(self) -> Path:
        """Get temp directory path."""
        return self.storage_root / "temp"
    
    def get_user_images_dir(self) -> Path:
        """Get user images directory path."""
        return self.get_images_dir() / "users"


@dataclass
class TelemetryConfig:
    """TDOS Telemetry Configuration"""
    tenant_id: str = field(default_factory=lambda: os.getenv("TDOS_TENANT_ID", "TENANT:BREEZE_CLUB"))
    agent_subject_id: str = field(default_factory=lambda: os.getenv("TDOS_AGENT_SUBJECT_ID", "AGENT:ABBY-DISCORD"))
    machine_subject_id: str = field(default_factory=lambda: os.getenv("TDOS_MACHINE_SUBJECT_ID", "MACHINE:TSERVER"))
    event_id_prefix: str = field(default_factory=lambda: os.getenv("TDOS_EVENT_ID_PREFIX", "EVT-ABBY"))


@dataclass
class MiscConfig:
    """Miscellaneous Configuration"""
    salt: Optional[str] = field(default_factory=lambda: os.getenv("SALT"))
    giveaway_url: Optional[str] = field(default_factory=lambda: os.getenv("GIVEAWAY_URL"))


@dataclass
class BotConfig:
    """Master Configuration Object"""
    channels: DiscordChannels = field(default_factory=DiscordChannels)
    roles: DiscordRoles = field(default_factory=DiscordRoles)
    emojis: DiscordEmojis = field(default_factory=DiscordEmojis)
    server_info: DiscordServerInfo = field(default_factory=DiscordServerInfo)
    api: APIKeys = field(default_factory=APIKeys)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    timing: TimingConfig = field(default_factory=TimingConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    misc: MiscConfig = field(default_factory=MiscConfig)
    
    def validate(self) -> list[str]:
        """
        Validate configuration and return list of warnings/errors.
        
        Returns:
            List of validation messages (empty if all valid)
        """
        issues = []
        
        # Critical validations
        if not self.api.discord_token:
            issues.append("❌ CRITICAL: ABBY_TOKEN not set - bot cannot start")
        
        # Database warnings
        if not self.database.mongodb_uri and not (self.database.mongodb_user and self.database.mongodb_pass):
            issues.append("⚠️  WARNING: MongoDB credentials not fully configured")
        
        # Feature-specific validations
        if self.features.rag_enabled and not self.database.qdrant_host:
            issues.append("⚠️  WARNING: RAG enabled but Qdrant host not configured")
        
        # Path validations
        if not self.paths.working_dir.exists():
            issues.append(f"⚠️  WARNING: Working directory does not exist: {self.paths.working_dir}")
        
        return issues
    
    def load_welcome_phrases(self) -> list[str]:
        """Load welcome phrases from JSON file, with fallback to defaults."""
        import json
        
        try:
            phrases_file = self.paths.working_dir / self.paths.welcome_phrases_file
            if phrases_file.exists():
                with open(phrases_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('phrases', [])
        except Exception as e:
            print(f"⚠️  Failed to load welcome phrases: {e}")
        
        # Fallback to default phrases
        return [
            "Z8phyR here, and I'm really happy to have you here. Please feel free to tag me and chat!",
            "Hey there! Z8phyR here, ready to chat. Don't hesitate to tag me and let's have a great conversation!",
            "Z8phyR reporting for duty! Feel free to tag me and let's dive into a lively chat!",
        ]
    
    def print_summary(self):
        """Print configuration summary for debugging."""
        print("\n" + "="*60)
        print("🐰 ABBY DISCORD BOT CONFIGURATION")
        print("="*60)
        
        print(f"\n📂 Paths:")
        print(f"  Working Dir: {self.paths.working_dir}")
        print(f"  Songs Dir: {self.paths.songs_dir}")
        print(f"  Images Dir: {self.paths.images_dir}")
        
        print(f"\n🗄️ Storage:")
        print(f"  Root: {self.storage.storage_root}")
        print(f"  Global Limit: {self.storage.max_global_storage_mb}MB")
        print(f"  Per-User Limit: {self.storage.max_user_storage_mb}MB")
        print(f"  Daily Gen Limit: {self.storage.max_user_daily_gens}/day")
        print(f"  Cleanup: {self.storage.cleanup_days} days")
        
        print(f"\n🗄️  Database:")
        print(f"  MongoDB DB: {self.database.mongodb_db}")
        print(f"  Qdrant: {self.database.qdrant_host}:{self.database.qdrant_port}")
        
        print(f"\n🤖 LLM:")
        print(f"  Provider: {self.llm.provider}")
        print(f"  Model: {self.llm.ollama_model if self.llm.provider == 'ollama' else self.llm.openai_model}")
        
        print(f"\n🎚️  Features:")
        print(f"  RAG Enabled: {self.features.rag_enabled}")
        print(f"  Nudges Enabled: {self.features.nudge_enabled}")
        
        print(f"\n⏱️  Timing:")
        print(f"  XP Message Cooldown: {self.timing.xp_message_cooldown}s")
        print(f"  Twitch Poll Interval: {self.timing.twitch_poll_minutes}m")
        
        # Validation
        issues = self.validate()
        if issues:
            print(f"\n⚠️  Configuration Issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"\n✅ Configuration Valid")
        
        print("="*60 + "\n")


# Global configuration instance
config = BotConfig()


if __name__ == "__main__":
    # Test configuration when run directly
    config.print_summary()
