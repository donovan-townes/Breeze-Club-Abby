"""Core configuration definitions for Abby.

This module hosts adapter-agnostic configuration objects and singleton access.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .channels import ChannelMapping
from .features import FeatureFlags
from .utils import getenv_bool, getenv_float, getenv_int


@dataclass
class APIConfig:
    """API keys and external service configuration (non-Discord)."""
    openai_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_organization: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_ORG_ID"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    stability_key: str = field(default_factory=lambda: os.getenv("STABILITY_API_KEY", ""))
    stability_api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "https://api.stability.ai"))

    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))

    youtube_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))

    twitter_api_key: str = field(default_factory=lambda: os.getenv("TWITTER_API_KEY", ""))
    twitter_api_secret: str = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET", ""))
    twitter_access_token: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN", ""))
    twitter_access_token_secret: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""))
    twitter_bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))

    twitch_client_id: str = field(default_factory=lambda: os.getenv("TWITCH_CLIENT_ID", ""))
    twitch_client_secret: str = field(default_factory=lambda: os.getenv("TWITCH_CLIENT_SECRET", ""))
    twitch_oauth: str = field(default_factory=lambda: os.getenv("TWITCH_OAUTH", ""))
    twitch_bot_id: str = field(default_factory=lambda: os.getenv("TWITCH_BOT_ID", ""))

    emote_api_key: Optional[str] = field(default_factory=lambda: os.getenv("EMOTE_API_KEY"))


@dataclass
class DatabaseConfig:
    """Database configuration."""
    mongodb_uri: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_URI"))
    mongodb_user: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_USER"))
    mongodb_password: Optional[str] = field(default_factory=lambda: os.getenv("MONGODB_PASS"))
    mongodb_db: str = field(default_factory=lambda: os.getenv("MONGODB_DB", "Abby_Database"))

    qdrant_host: str = field(default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"))
    qdrant_port: int = field(default_factory=lambda: getenv_int("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = field(default_factory=lambda: os.getenv("QDRANT_API_KEY"))

    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./chroma-data"))


@dataclass
class LLMConfig:
    """Large language model configuration."""
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama").lower())
    temperature: float = field(default_factory=lambda: getenv_float("LLM_TEMPERATURE", "0.7"))
    max_tokens: int = field(default_factory=lambda: getenv_int("LLM_MAX_TOKENS", "2048"))
    timeout_seconds: int = field(default_factory=lambda: getenv_int("LLM_TIMEOUT", "30"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    embedding_device: str = field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))


@dataclass
class RAGConfig:
    """RAG system configuration."""
    vector_store: str = field(default_factory=lambda: os.getenv("VECTOR_STORE", "chroma"))
    chunk_size: int = field(default_factory=lambda: getenv_int("CHUNK_SIZE", "500"))
    chunk_overlap: int = field(default_factory=lambda: getenv_int("CHUNK_OVERLAP", "50"))


@dataclass
class TimingConfig:
    """Timing, intervals, and cooldowns."""
    xp_message_cooldown_seconds: int = field(default_factory=lambda: getenv_int("XP_MESSAGE_COOLDOWN_SECONDS", "60"))
    xp_attachment_cooldown_seconds: int = field(default_factory=lambda: getenv_int("XP_ATTACHMENT_COOLDOWN_SECONDS", "600"))
    xp_stream_interval_minutes: int = field(default_factory=lambda: getenv_int("XP_STREAM_INTERVAL_MINUTES", "5"))
    xp_daily_start_hour: int = field(default_factory=lambda: getenv_int("XP_DAILY_START_HOUR", "5"))
    twitch_poll_minutes: int = field(default_factory=lambda: getenv_int("TWITCH_POLL_MINUTES", "15"))
    nudge_interval_hours: int = field(default_factory=lambda: getenv_int("NUDGE_INTERVAL_HOURS", "24"))
    motd_start_hour: int = field(default_factory=lambda: getenv_int("MOTD_START_HOUR", "5"))


@dataclass
class PathConfig:
    """File system paths."""
    working_dir: Path = field(default_factory=lambda: Path(os.getenv("WORKING_DIRECTORY", os.getcwd())))
    songs_dir: Path = field(default_factory=lambda: Path(os.getenv("SONGS_DIR", "songs")))
    images_dir: Path = field(default_factory=lambda: Path(os.getenv("IMAGES_DIR", "Images")))
    audio_recordings: Path = field(default_factory=lambda: Path(os.getenv("AUDIO_ROOT", "Audio_Recordings")))
    welcome_phrases_file: Path = field(default_factory=lambda: Path("abby_adapters/discord/data/welcome_phrases.json"))
    tdos_events_path: Path = field(default_factory=lambda: Path(os.getenv("TDOS_EVENTS_PATH", "shared/logs/events.jsonl")))


@dataclass
class StorageConfig:
    """Centralized file storage configuration."""
    storage_root: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "shared")))
    max_global_storage_mb: int = field(default_factory=lambda: getenv_int("MAX_GLOBAL_STORAGE_MB", "5000"))
    max_user_storage_mb: int = field(default_factory=lambda: getenv_int("MAX_USER_STORAGE_MB", "500"))
    max_user_daily_gens: int = field(default_factory=lambda: getenv_int("MAX_USER_DAILY_GENS", "5"))
    cleanup_days: int = field(default_factory=lambda: getenv_int("STORAGE_CLEANUP_DAYS", "7"))
    image_generation_size_mb: float = field(default_factory=lambda: getenv_float("IMAGE_GEN_SIZE_MB", "1.5"))

    @dataclass
    class QuotaOverrides:
        """Per-user/role quota overrides."""
        owner_user_ids: List[str] = field(default_factory=lambda: [uid.strip() for uid in os.getenv("OWNER_USER_IDS", "").split(",") if uid.strip()])
        owner_daily_limit: int = field(default_factory=lambda: getenv_int("OWNER_DAILY_LIMIT", "9999"))
        role_daily_limits: Dict[str, int] = field(default_factory=dict)
        level_bands: List[Dict[str, int]] = field(default_factory=lambda: [
            {"min_level": 1, "daily_limit": 10},
            {"min_level": 5, "daily_limit": 25},
            {"min_level": 10, "daily_limit": 50},
        ])

    quota_overrides: QuotaOverrides = field(default_factory=QuotaOverrides)

    def get_images_dir(self) -> Path:
        """Return images directory path."""
        return self.storage_root / "images"

    def get_temp_dir(self) -> Path:
        """Return temp directory path."""
        return self.storage_root / "temp"

    def get_user_images_dir(self) -> Path:
        """Return user images directory path."""
        return self.get_images_dir() / "users"


@dataclass
class TelemetryConfig:
    """TDOS telemetry configuration."""
    tenant_id: str = field(default_factory=lambda: os.getenv("TDOS_TENANT_ID", "TENANT:BREEZE_CLUB"))
    agent_subject_id: str = field(default_factory=lambda: os.getenv("TDOS_AGENT_SUBJECT_ID", "AGENT:ABBY-DISCORD"))
    machine_subject_id: str = field(default_factory=lambda: os.getenv("TDOS_MACHINE_SUBJECT_ID", "MACHINE:TSERVER"))
    event_id_prefix: str = field(default_factory=lambda: os.getenv("TDOS_EVENT_ID_PREFIX", "EVT-ABBY"))


@dataclass
class MiscConfig:
    """Miscellaneous configuration."""
    salt: Optional[str] = field(default_factory=lambda: os.getenv("SALT"))
    giveaway_url: Optional[str] = field(default_factory=lambda: os.getenv("GIVEAWAY_URL"))


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_path: Path = field(default_factory=lambda: Path(os.getenv("LOG_PATH", "./logs")))
    json_logs: bool = field(default_factory=lambda: getenv_bool("JSON_LOGS", "false"))


@dataclass
class BotConfig:
    """Master configuration for Abby core (adapter-agnostic)."""

    api: APIConfig = field(default_factory=APIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    timing: TimingConfig = field(default_factory=TimingConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    misc: MiscConfig = field(default_factory=MiscConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    channels: ChannelMapping = field(default_factory=ChannelMapping)

    mode: str = field(default_factory=lambda: os.getenv("ABBY_MODE", "prod").lower())
    debug: bool = field(default_factory=lambda: getenv_bool("DEBUG", "false"))

    def __post_init__(self) -> None:
        """Validate and prepare configuration after initialization."""
        self.storage.storage_root.mkdir(parents=True, exist_ok=True)
        self.logging.file_path.mkdir(parents=True, exist_ok=True)
        self.storage.get_images_dir().mkdir(parents=True, exist_ok=True)
        self.storage.get_temp_dir().mkdir(parents=True, exist_ok=True)

    def validate(self) -> List[str]:
        """Validate configuration and return list of warnings/errors."""
        issues: List[str] = []

        if not self.api.openai_key and self.llm.provider == "openai":
            issues.append("❌ CRITICAL: OPENAI_API_KEY not set but LLM provider is OpenAI")

        if not self.database.mongodb_uri:
            issues.append("⚠️  WARNING: MongoDB URI not configured - persistence will be unavailable")

        if self.features.rag_enabled and not self.database.qdrant_host:
            issues.append("⚠️  WARNING: RAG enabled but Qdrant not configured")

        if not self.paths.working_dir.exists():
            issues.append(f"⚠️  WARNING: Working directory does not exist: {self.paths.working_dir}")

        return issues

    def print_summary(self) -> None:
        """Print configuration summary for debugging."""
        print("\n" + "=" * 70)
        print("🐰 ABBY CORE CONFIGURATION SUMMARY")
        print("=" * 70)

        print(f"\n🔧 Mode: {self.mode.upper()} | Debug: {self.debug}")

        print("\n📂 Paths:")
        print(f"  Working Dir: {self.paths.working_dir}")
        print(f"  Storage Root: {self.storage.storage_root}")
        print(f"  Logs: {self.logging.file_path}")

        print("\n💾 Storage:")
        print(f"  Global Limit: {self.storage.max_global_storage_mb}MB")
        print(f"  Per-User Limit: {self.storage.max_user_storage_mb}MB")
        print(f"  Daily Gen Limit: {self.storage.max_user_daily_gens}/day")
        print(f"  Cleanup After: {self.storage.cleanup_days} days")

        print("\n🗄️  Database:")
        print(f"  MongoDB DB: {self.database.mongodb_db}")
        print(f"  Qdrant: {self.database.qdrant_host}:{self.database.qdrant_port}")

        print("\n🤖 LLM:")
        print(f"  Provider: {self.llm.provider}")
        if self.llm.provider == "ollama":
            print(f"  Model: {self.llm.embedding_model}")
        elif self.llm.provider == "openai":
            print(f"  Model: {self.api.openai_model}")
        print(f"  Temperature: {self.llm.temperature}")
        print(f"  Max Tokens: {self.llm.max_tokens}")
        print(f"  Timeout: {self.llm.timeout_seconds}s")

        print("\n🎚️  Features:")
        print(f"  RAG Enabled: {self.features.rag_enabled}")
        print(f"  Nudges Enabled: {self.features.nudge_enabled}")
        print(f"  Image Auto-Move: {self.features.image_auto_move_enabled}")

        print("\n⏱️  Timing:")
        print(f"  XP Message Cooldown: {self.timing.xp_message_cooldown_seconds}s")
        print(f"  XP Daily Start: {self.timing.xp_daily_start_hour}:00 UTC")
        print(f"  MOTD Start: {self.timing.motd_start_hour}:00 UTC")
        print(f"  Twitch Poll: every {self.timing.twitch_poll_minutes}m")

        issues = self.validate()
        if issues:
            print("\n⚠️  Configuration Issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\n✅ Configuration Valid")

        print("=" * 70 + "\n")


_config: Optional[BotConfig] = None


def get_config() -> BotConfig:
    """Return the singleton BotConfig instance."""
    global _config
    if _config is None:
        _config = BotConfig()
        if _config.debug:
            _config.print_summary()
    return _config


__all__ = [
    "APIConfig",
    "DatabaseConfig",
    "LLMConfig",
    "RAGConfig",
    "TimingConfig",
    "PathConfig",
    "StorageConfig",
    "TelemetryConfig",
    "MiscConfig",
    "LoggingConfig",
    "ChannelMapping",
    "FeatureFlags",
    "BotConfig",
    "get_config",
]
