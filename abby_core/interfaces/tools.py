"""
Platform-Agnostic Tool Interfaces

Defines contracts for intent-based tools (server info, user info, bot status, etc.)
that can be implemented by different platform adapters.

This enables the same intent system to work across Discord, web, CLI, Slack, etc.

Architecture:
- Core system uses these interfaces
- Each platform provides concrete implementations
- Tools are registered with factory pattern
- Results are normalized data structures (not platform-specific)

Example:
    # Discord adapter provides Discord implementation
    factory.register("discord", DiscordServerInfoTool())
    
    # Web adapter provides REST API implementation  
    factory.register("web", WebServerInfoTool())
    
    # Intent system uses factory to get correct implementation
    tool = factory.get_tool(platform, "server_info")
    result = await tool.execute(context)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


# ============================================================================
# DATA MODELS (Platform-Agnostic)
# ============================================================================

@dataclass
class ServerInfo:
    """Platform-agnostic server/guild information."""
    server_id: str
    name: str
    member_count: int
    owner_id: str
    owner_name: str
    created_at: datetime
    icon_url: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "member_count": self.member_count,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "created_at": self.created_at.isoformat(),
            "icon_url": self.icon_url,
            "description": self.description,
        }


@dataclass
class UserInfo:
    """Platform-agnostic user information."""
    user_id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    is_bot: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "is_bot": self.is_bot,
        }


@dataclass
class UserXPInfo:
    """Platform-agnostic user XP/leveling information."""
    user_id: str
    username: str
    display_name: str
    xp: int
    level: int
    xp_to_next_level: int
    current_level_xp: int
    xp_for_level: int
    rank: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "xp": self.xp,
            "level": self.level,
            "xp_to_next_level": self.xp_to_next_level,
            "current_level_xp": self.current_level_xp,
            "xp_for_level": self.xp_for_level,
            "rank": self.rank,
        }


@dataclass
class BotStatus:
    """Platform-agnostic bot status information."""
    status_type: str  # "playing", "watching", "listening", "streaming", "online", "idle", "dnd", "invisible"
    message: str
    url: Optional[str] = None  # For streaming
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status_type": self.status_type,
            "message": self.message,
            "url": self.url,
        }


@dataclass
class ToolResult:
    """Standard result from tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error,
        }


# ============================================================================
# TOOL INTERFACES
# ============================================================================

class IServerInfoTool(ABC):
    """Interface for fetching server/guild information."""
    
    @abstractmethod
    async def get_server_info(self, server_id: str, context: Dict[str, Any]) -> ToolResult:
        """
        Get server information.
        
        Args:
            server_id: Platform-specific server identifier
            context: Execution context (may include bot client, credentials, etc.)
            
        Returns:
            ToolResult with ServerInfo in data field
        """
        pass


class IUserInfoTool(ABC):
    """Interface for fetching user information."""
    
    @abstractmethod
    async def get_user_info(self, user_id: str, server_id: Optional[str], context: Dict[str, Any]) -> ToolResult:
        """
        Get user information.
        
        Args:
            user_id: Platform-specific user identifier
            server_id: Optional server context
            context: Execution context
            
        Returns:
            ToolResult with UserInfo in data field
        """
        pass


class IUserXPTool(ABC):
    """Interface for fetching user XP/leveling information."""
    
    @abstractmethod
    async def get_user_xp(self, user_id: str, server_id: Optional[str], context: Dict[str, Any]) -> ToolResult:
        """
        Get user XP and level information.
        
        Args:
            user_id: Platform-specific user identifier
            server_id: Optional server context
            context: Execution context
            
        Returns:
            ToolResult with UserXPInfo in data field
        """
        pass


class IBotStatusTool(ABC):
    """Interface for managing bot status/presence."""
    
    @abstractmethod
    async def set_status(self, status: BotStatus, context: Dict[str, Any]) -> ToolResult:
        """
        Set bot status/presence.
        
        Args:
            status: Desired bot status
            context: Execution context (bot client, etc.)
            
        Returns:
            ToolResult indicating success/failure
        """
        pass
    
    @abstractmethod
    async def get_status(self, context: Dict[str, Any]) -> ToolResult:
        """
        Get current bot status.
        
        Args:
            context: Execution context
            
        Returns:
            ToolResult with BotStatus in data field
        """
        pass


# ============================================================================
# TOOL FACTORY
# ============================================================================

class ToolFactory:
    """
    Factory for registering and retrieving platform-specific tool implementations.
    
    Usage:
        # Register Discord tools
        factory = ToolFactory()
        factory.register("discord", "server_info", DiscordServerInfoTool())
        factory.register("discord", "user_xp", DiscordUserXPTool())
        
        # Get tool for specific platform
        tool = factory.get_tool("discord", "server_info")
        result = await tool.get_server_info(server_id, context)
    """
    
    def __init__(self):
        # Structure: {platform: {tool_type: tool_instance}}
        self._tools: Dict[str, Dict[str, Any]] = {}
    
    def register(self, platform: str, tool_type: str, tool: Any):
        """
        Register a tool implementation for a platform.
        
        Args:
            platform: Platform identifier ("discord", "web", "slack", etc.)
            tool_type: Tool type ("server_info", "user_info", "user_xp", "bot_status")
            tool: Tool implementation instance
        """
        if platform not in self._tools:
            self._tools[platform] = {}
        
        self._tools[platform][tool_type] = tool
    
    def get_tool(self, platform: str, tool_type: str) -> Optional[Any]:
        """
        Get a tool implementation for a platform.
        
        Args:
            platform: Platform identifier
            tool_type: Tool type
            
        Returns:
            Tool implementation or None if not registered
        """
        return self._tools.get(platform, {}).get(tool_type)
    
    def has_tool(self, platform: str, tool_type: str) -> bool:
        """Check if a tool is registered."""
        return platform in self._tools and tool_type in self._tools[platform]
    
    def list_tools(self, platform: str) -> List[str]:
        """List all registered tools for a platform."""
        return list(self._tools.get(platform, {}).keys())
    
    def list_platforms(self) -> List[str]:
        """List all registered platforms."""
        return list(self._tools.keys())


# ============================================================================
# SINGLETON FACTORY
# ============================================================================

_tool_factory: Optional[ToolFactory] = None


def get_tool_factory() -> ToolFactory:
    """Get or create the singleton tool factory."""
    global _tool_factory
    if _tool_factory is None:
        _tool_factory = ToolFactory()
    return _tool_factory
