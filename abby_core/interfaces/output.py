"""
Platform-Agnostic Output Formatting Interfaces

Defines contracts for formatting bot outputs (text, images, rich content)
in a platform-independent way.

This allows generation and content systems to produce generic data structures
that can be formatted for Discord embeds, web HTML, CLI text, etc.

Architecture:
- Core systems produce OutputMessage objects
- Platform adapters implement IOutputFormatter
- Formatters convert OutputMessage → platform-specific format
- No Discord/platform imports in core generation code

Example:
    # Generation produces generic output
    output = OutputMessage(
        title="Generated Image",
        description="A beautiful sunset",
        image=ImageOutput(url="https://...", width=1024, height=1024)
    )
    
    # Discord formatter converts to Discord embed
    discord_formatter = DiscordOutputFormatter()
    embed = discord_formatter.format_message(output)
    
    # Web formatter converts to HTML
    web_formatter = WebOutputFormatter()
    html = web_formatter.format_message(output)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============================================================================
# OUTPUT DATA MODELS
# ============================================================================

class OutputColor(Enum):
    """Standard colors for output messages."""
    DEFAULT = "default"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass
class ImageOutput:
    """Platform-agnostic image output."""
    url: Optional[str] = None
    base64_data: Optional[str] = None  # For inline images
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "base64_data": self.base64_data,
            "width": self.width,
            "height": self.height,
            "alt_text": self.alt_text,
            "caption": self.caption,
        }


@dataclass
class FieldOutput:
    """Platform-agnostic field (name-value pair)."""
    name: str
    value: str
    inline: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline,
        }


@dataclass
class AuthorOutput:
    """Platform-agnostic author information."""
    name: str
    url: Optional[str] = None
    icon_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "icon_url": self.icon_url,
        }


@dataclass
class FooterOutput:
    """Platform-agnostic footer information."""
    text: str
    icon_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "icon_url": self.icon_url,
        }


@dataclass
class OutputMessage:
    """
    Platform-agnostic output message.
    
    This is the core data structure produced by generation, announcements,
    and other content systems. Platform adapters convert this to their
    native format (Discord embed, HTML, etc.).
    """
    # Basic content
    content: Optional[str] = None  # Plain text content
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    
    # Visual styling
    color: OutputColor = OutputColor.DEFAULT
    timestamp: Optional[datetime] = None
    
    # Rich content
    image: Optional[ImageOutput] = None
    thumbnail: Optional[ImageOutput] = None
    author: Optional[AuthorOutput] = None
    footer: Optional[FooterOutput] = None
    fields: List[FieldOutput] = field(default_factory=list)
    
    # Attachments (files, images not embedded)
    attachments: List[ImageOutput] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "color": self.color.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image": self.image.to_dict() if self.image else None,
            "thumbnail": self.thumbnail.to_dict() if self.thumbnail else None,
            "author": self.author.to_dict() if self.author else None,
            "footer": self.footer.to_dict() if self.footer else None,
            "fields": [f.to_dict() for f in self.fields],
            "attachments": [a.to_dict() for a in self.attachments],
        }
    
    def add_field(self, name: str, value: str, inline: bool = False) -> "OutputMessage":
        """Add a field to the message (builder pattern)."""
        self.fields.append(FieldOutput(name=name, value=value, inline=inline))
        return self
    
    def set_author(self, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> "OutputMessage":
        """Set author (builder pattern)."""
        self.author = AuthorOutput(name=name, url=url, icon_url=icon_url)
        return self
    
    def set_footer(self, text: str, icon_url: Optional[str] = None) -> "OutputMessage":
        """Set footer (builder pattern)."""
        self.footer = FooterOutput(text=text, icon_url=icon_url)
        return self
    
    def set_image(self, url: Optional[str] = None, base64_data: Optional[str] = None, **kwargs) -> "OutputMessage":
        """Set main image (builder pattern)."""
        self.image = ImageOutput(url=url, base64_data=base64_data, **kwargs)
        return self
    
    def set_thumbnail(self, url: Optional[str] = None, base64_data: Optional[str] = None, **kwargs) -> "OutputMessage":
        """Set thumbnail (builder pattern)."""
        self.thumbnail = ImageOutput(url=url, base64_data=base64_data, **kwargs)
        return self


# ============================================================================
# OUTPUT FORMATTER INTERFACE
# ============================================================================

class IOutputFormatter(ABC):
    """
    Interface for formatting OutputMessage into platform-specific formats.
    
    Each platform adapter implements this to convert generic OutputMessage
    objects into their native representation (Discord Embed, HTML, etc.).
    """
    
    @abstractmethod
    def format_message(self, output: OutputMessage) -> Any:
        """
        Format OutputMessage into platform-specific format.
        
        Args:
            output: Generic output message
            
        Returns:
            Platform-specific formatted output (discord.Embed, HTML string, etc.)
        """
        pass
    
    @abstractmethod
    def format_text(self, output: OutputMessage) -> str:
        """
        Format OutputMessage as plain text (fallback for platforms without rich formatting).
        
        Args:
            output: Generic output message
            
        Returns:
            Plain text representation
        """
        pass


# ============================================================================
# ANNOUNCEMENT DELIVERY INTERFACE
# ============================================================================

class IAnnouncementDelivery(ABC):
    """
    Interface for delivering announcements to platform-specific channels.
    
    This abstracts the delivery mechanism so announcements can be sent
    to Discord channels, web webhooks, email, SMS, etc.
    """
    
    @abstractmethod
    async def send_announcement(
        self,
        channel_id: str,
        output: OutputMessage,
        context: Dict[str, Any]
    ) -> bool:
        """
        Send an announcement to a channel.
        
        Args:
            channel_id: Platform-specific channel identifier
            output: Formatted announcement message
            context: Execution context (bot client, credentials, etc.)
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_bulk_announcements(
        self,
        announcements: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Send multiple announcements efficiently.
        
        Args:
            announcements: List of {channel_id, output} dicts
            context: Execution context
            
        Returns:
            Dict mapping channel_id → success status
        """
        pass


# ============================================================================
# FORMATTER FACTORY
# ============================================================================

class FormatterFactory:
    """
    Factory for registering and retrieving platform-specific formatters.
    
    Usage:
        # Register Discord formatter
        factory = FormatterFactory()
        factory.register("discord", DiscordOutputFormatter())
        
        # Get formatter for specific platform
        formatter = factory.get_formatter("discord")
        embed = formatter.format_message(output)
    """
    
    def __init__(self):
        self._formatters: Dict[str, IOutputFormatter] = {}
        self._delivery_handlers: Dict[str, IAnnouncementDelivery] = {}
    
    def register_formatter(self, platform: str, formatter: IOutputFormatter):
        """Register an output formatter for a platform."""
        self._formatters[platform] = formatter
    
    def register_delivery_handler(self, platform: str, handler: IAnnouncementDelivery):
        """Register an announcement delivery handler for a platform."""
        self._delivery_handlers[platform] = handler
    
    def get_formatter(self, platform: str) -> Optional[IOutputFormatter]:
        """Get formatter for a platform."""
        return self._formatters.get(platform)
    
    def get_delivery_handler(self, platform: str) -> Optional[IAnnouncementDelivery]:
        """Get delivery handler for a platform."""
        return self._delivery_handlers.get(platform)
    
    def has_formatter(self, platform: str) -> bool:
        """Check if platform has a registered formatter."""
        return platform in self._formatters
    
    def has_delivery_handler(self, platform: str) -> bool:
        """Check if platform has a registered delivery handler."""
        return platform in self._delivery_handlers
    
    def list_platforms(self) -> List[str]:
        """List all registered platforms."""
        platforms = set(self._formatters.keys()) | set(self._delivery_handlers.keys())
        return list(platforms)


# ============================================================================
# SINGLETON FACTORY
# ============================================================================

_formatter_factory: Optional[FormatterFactory] = None


def get_formatter_factory() -> FormatterFactory:
    """Get or create the singleton formatter factory."""
    global _formatter_factory
    if _formatter_factory is None:
        _formatter_factory = FormatterFactory()
    return _formatter_factory
