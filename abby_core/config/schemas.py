"""Lightweight schemas for config validation and storage."""

from dataclasses import dataclass, field
from typing import Dict, Optional
from .channels import ChannelMapping


@dataclass
class GuildConfigSchema:
    """Schema representing persisted guild configuration overrides."""
    guild_id: int
    channels: ChannelMapping = field(default_factory=ChannelMapping)
    roles: Optional[Dict[str, int]] = None


__all__ = ["GuildConfigSchema"]
