"""Platform-agnostic interfaces for intent routing and context.

Enables LLM layer to work with any chat platform (Discord, Slack, etc.)
by defining abstract protocols instead of importing concrete types.

This eliminates Discord type leakage into llm/ and intent/ modules,
making them testable and reusable across adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from dataclasses import dataclass


# ============================================================================
# MESSAGE ABSTRACTIONS
# ============================================================================


class User(Protocol):
    """Minimal user interface across platforms."""

    @property
    def id(self) -> int:
        """Unique user identifier."""
        ...

    @property
    def name(self) -> str:
        """User's display name or username."""
        ...

    @property
    def mention(self) -> str:
        """Platform-specific user mention string (e.g., '<@id>' for Discord)."""
        ...


class Channel(Protocol):
    """Minimal channel interface across platforms."""

    @property
    def id(self) -> int:
        """Unique channel identifier."""
        ...

    @property
    def name(self) -> str:
        """Channel name or identifier."""
        ...

    @property
    def guild_id(self) -> Optional[int]:
        """Parent guild/server ID if applicable."""
        ...


class Message(Protocol):
    """Minimal message interface across platforms."""

    @property
    def content(self) -> str:
        """Message text content."""
        ...

    @property
    def author(self) -> User:
        """Message author/sender."""
        ...

    @property
    def channel(self) -> Channel:
        """Channel where message was sent."""
        ...

    @property
    def guild_id(self) -> Optional[int]:
        """Guild/server ID if applicable."""
        ...


# ============================================================================
# CLIENT ABSTRACTIONS
# ============================================================================


class PlatformClient(Protocol):
    """Minimal client interface for platform operations."""

    @property
    def user(self) -> Optional[User]:
        """The bot's own user/identity."""
        ...

    def get_channel(self, channel_id: int) -> Optional[Channel]:
        """Fetch a channel by ID."""
        ...

    def get_guild(self, guild_id: int) -> Optional[Any]:
        """Fetch a guild/server by ID."""
        ...


# ============================================================================
# TOOL RESULT ABSTRACTIONS
# ============================================================================


@dataclass
class ToolResult:
    """Standardized tool execution result across adapters."""

    text: str
    embed: Optional[Any] = None  # Platform-specific embed if available
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "text": self.text,
            "embed": self.embed,
            "success": self.success,
            "error_message": self.error_message,
        }


# ============================================================================
# CONTEXT ABSTRACTIONS
# ============================================================================


class ContextUser(ABC):
    """Adapter-agnostic user context for intent/action routing."""

    @property
    @abstractmethod
    def id(self) -> int:
        """User ID."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """User name/mention."""
        pass

    @property
    @abstractmethod
    def is_owner(self) -> bool:
        """Is this the guild owner."""
        pass

    @property
    @abstractmethod
    def user_level(self) -> str:
        """User privilege level: member, moderator, admin, owner."""
        pass


class ContextChannel(ABC):
    """Adapter-agnostic channel context for action dispatch."""

    @property
    @abstractmethod
    def id(self) -> int:
        """Channel ID."""
        pass

    @property
    @abstractmethod
    def guild_id(self) -> Optional[int]:
        """Parent guild ID if applicable."""
        pass

    @abstractmethod
    async def send_message(self, text: str) -> None:
        """Send a text message to this channel."""
        pass

    @abstractmethod
    async def send_embed(self, embed: Any) -> None:
        """Send an embed/rich message to this channel."""
        pass


class ActionContext(ABC):
    """Context provided to intent action handlers."""

    @property
    @abstractmethod
    def user(self) -> ContextUser:
        """Requesting user."""
        pass

    @property
    @abstractmethod
    def channel(self) -> ContextChannel:
        """Target channel for action output."""
        pass

    @property
    @abstractmethod
    def client(self) -> PlatformClient:
        """Platform client for state queries."""
        pass

    @property
    @abstractmethod
    def message_content(self) -> str:
        """Original user message."""
        pass
