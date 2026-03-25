"""Feature flag configuration for Abby core."""

from dataclasses import dataclass, field
from .utils import getenv_bool


@dataclass
class FeatureFlags:
    """Feature toggles and experimental flags."""
    rag_enabled: bool = field(default_factory=lambda: getenv_bool("RAG_CONTEXT_ENABLED", "false"))
    nudge_enabled: bool = field(default_factory=lambda: getenv_bool("NUDGE_ENABLED", "false"))
    image_auto_move_enabled: bool = field(default_factory=lambda: getenv_bool("IMAGE_AUTO_MOVE_ENABLED", "false"))
    dry_run_mode: bool = field(default_factory=lambda: getenv_bool("MIGRATE_DRY_RUN", "false"))


__all__ = ["FeatureFlags"]
