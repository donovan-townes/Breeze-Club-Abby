"""Guild-agnostic channel mapping templates."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChannelMapping:
    """Template for channel mappings per guild."""
    motd: Optional[int] = None
    announcements: Optional[int] = None
    xp: Optional[int] = None
    memes: Optional[int] = None
    welcome: Optional[int] = None
    radio: Optional[int] = None

    def get_channel(self, key: str, default: int) -> int:
        """Return the channel value with fallback to provided default."""
        value = getattr(self, key, None)
        return value or default


__all__ = ["ChannelMapping"]
