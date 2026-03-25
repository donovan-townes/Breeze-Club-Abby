"""
NotificationService - Platform-Agnostic Notification Delivery

Extracts notification logic from Discord adapter, providing a unified interface
for sending notifications across all platforms (Discord, Web, CLI, Slack, etc.).

Architecture:
    Discord Adapter  ─┐
    Web Adapter      ─┼──→ NotificationService ──→ Platform Delivery
    CLI Adapter      ─┘

Responsibilities:
- Notification queueing and delivery
- Severity-based formatting and routing
- Platform-agnostic notification data models
- Error handling and retry logic

Platform adapters implement the actual delivery mechanism:
- Discord: Embeds to mod channels
- Web: Browser notifications, toast messages
- CLI: Console output with ANSI colors
- Slack: Rich message blocks
"""

from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import logging

from abby_core.database.collections.guild_configuration import get_guild_setting
from abby_core.interfaces.output import OutputMessage, OutputColor

try:
    from tdos_intelligence.observability import logging as tdos_logging  # type: ignore
    logger = tdos_logging.getLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA MODELS
# ════════════════════════════════════════════════════════════════════════════════

class NotificationLevel(str, Enum):
    """Notification severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NotificationTarget(str, Enum):
    """Where to send the notification."""
    MODERATORS = "moderators"  # Mod channel, admin users
    USERS = "users"            # General announcement
    SYSTEM = "system"          # System logs, operator console


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_notification_service: Optional['NotificationService'] = None


def get_notification_service() -> 'NotificationService':
    """Get or create NotificationService singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# ════════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE CLASS
# ════════════════════════════════════════════════════════════════════════════════

class NotificationService:
    """Platform-agnostic notification management.
    
    All methods return (result, error) tuples for consistent error handling:
    - Success: (result_value, None)
    - Failure: (None, error_message_str)
    """

    def __init__(self):
        """Initialize notification service."""
        self.queue: List[Dict[str, Any]] = []
        logger.debug("[🔔] NotificationService initialized")

    # ════════════════════════════════════════════════════════════════════════════════
    # NOTIFICATION CREATION
    # ════════════════════════════════════════════════════════════════════════════════

    def create_notification(
        self,
        workspace_id: int | str,
        level: NotificationLevel | str,
        title: str,
        description: str,
        *,
        fields: Optional[Dict[str, str]] = None,
        target: NotificationTarget = NotificationTarget.MODERATORS,
        tag_recipients: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """Create a platform-agnostic notification.
        
        Args:
            workspace_id: Workspace/guild/tenant identifier
            level: Notification severity (INFO, WARNING, ERROR, CRITICAL)
            title: Notification title
            description: Notification body/description
            fields: Optional key-value pairs to display
            target: Who should receive this (moderators, users, system)
            tag_recipients: Whether to @mention recipients (for critical alerts)
            metadata: Additional platform-specific data
            
        Returns:
            (notification_dict, None) on success
            (None, error_message) on failure
        """
        try:
            # Normalize level to enum
            if isinstance(level, str):
                level = NotificationLevel(level.upper())
            
            # Determine color based on level
            color_map = {
                NotificationLevel.INFO: OutputColor.INFO,
                NotificationLevel.WARNING: OutputColor.WARNING,
                NotificationLevel.ERROR: OutputColor.ERROR,
                NotificationLevel.CRITICAL: OutputColor.ERROR,
            }
            
            notification = {
                "workspace_id": str(workspace_id),
                "level": level.value,
                "title": title,
                "description": description,
                "fields": fields or {},
                "target": target.value if isinstance(target, NotificationTarget) else target,
                "tag_recipients": tag_recipients,
                "color": color_map.get(level, OutputColor.INFO).value,
                "metadata": metadata or {},
                "created_at": datetime.utcnow(),
                "delivered": False,
            }
            
            logger.debug(
                f"[🔔] Created {level.value} notification for workspace {workspace_id}: {title}"
            )
            
            return notification, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to create notification: {e}")
            return None, f"Failed to create notification: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # NOTIFICATION QUEUEING
    # ════════════════════════════════════════════════════════════════════════════════

    def queue_notification(
        self,
        workspace_id: int | str,
        level: NotificationLevel | str,
        title: str,
        description: str,
        **kwargs
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """Queue a notification for async delivery.
        
        Useful for non-blocking notification sending from sync contexts.
        Background task will process queue periodically.
        
        Args:
            workspace_id: Workspace identifier
            level: Notification level
            title: Title
            description: Description
            **kwargs: Additional args passed to create_notification
            
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            notification, error = self.create_notification(
                workspace_id=workspace_id,
                level=level,
                title=title,
                description=description,
                **kwargs
            )
            
            if error:
                return None, error
            
            if notification is None:
                return None, "Failed to create notification"
            
            self.queue.append(notification)
            
            logger.debug(
                f"[🔔] Queued notification for workspace {workspace_id}. "
                f"Queue size: {len(self.queue)}"
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to queue notification: {e}")
            return None, f"Failed to queue notification: {str(e)}"

    def get_queued_notifications(
        self,
        workspace_id: Optional[int | str] = None,
        level: Optional[NotificationLevel | str] = None,
        max_count: int = 10
    ) -> Tuple[List[Dict[str, Any]], None] | Tuple[None, str]:
        """Get notifications from the queue.
        
        Args:
            workspace_id: Filter by workspace (optional)
            level: Filter by level (optional)
            max_count: Maximum number to return
            
        Returns:
            (notifications_list, None) on success
            (None, error_message) on failure
        """
        try:
            notifications = self.queue.copy()
            
            # Filter by workspace
            if workspace_id is not None:
                notifications = [
                    n for n in notifications 
                    if n["workspace_id"] == str(workspace_id)
                ]
            
            # Filter by level
            if level is not None:
                level_str = level.value if isinstance(level, NotificationLevel) else level.upper()
                notifications = [
                    n for n in notifications 
                    if n["level"] == level_str
                ]
            
            # Limit count
            notifications = notifications[:max_count]
            
            return notifications, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to get queued notifications: {e}")
            return None, f"Failed to get queued notifications: {str(e)}"

    def clear_queue(
        self,
        workspace_id: Optional[int | str] = None
    ) -> Tuple[int, None] | Tuple[None, str]:
        """Clear notifications from queue.
        
        Args:
            workspace_id: Clear only for specific workspace (optional)
            
        Returns:
            (cleared_count, None) on success
            (None, error_message) on failure
        """
        try:
            if workspace_id is None:
                count = len(self.queue)
                self.queue.clear()
            else:
                original_count = len(self.queue)
                self.queue = [
                    n for n in self.queue 
                    if n["workspace_id"] != str(workspace_id)
                ]
                count = original_count - len(self.queue)
            
            logger.debug(f"[🔔] Cleared {count} notifications from queue")
            return count, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to clear queue: {e}")
            return None, f"Failed to clear queue: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ════════════════════════════════════════════════════════════════════════════════

    def get_notification_channel(
        self,
        workspace_id: int | str,
        target: NotificationTarget = NotificationTarget.MODERATORS
    ) -> Tuple[Optional[str], None] | Tuple[None, str]:
        """Get the notification channel ID for a workspace.
        
        Platform adapters use this to determine where to send notifications.
        
        Args:
            workspace_id: Workspace identifier
            target: Notification target type
            
        Returns:
            (channel_id, None) on success
            (None, error_message) on failure
        """
        try:
            # Map target to guild setting key
            setting_keys = {
                NotificationTarget.MODERATORS: "mod_channel_id",
                NotificationTarget.USERS: "announcements_channel_id",
                NotificationTarget.SYSTEM: "system_logs_channel_id",
            }
            
            setting_key = setting_keys.get(target)
            if not setting_key:
                return None, f"Unknown notification target: {target}"
            
            # Get channel from workspace settings
            channel_id = get_guild_setting(int(workspace_id), setting_key)
            
            return channel_id, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to get notification channel: {e}")
            return None, f"Failed to get notification channel: {str(e)}"

    def to_output_message(
        self,
        notification: Dict[str, Any]
    ) -> Tuple[OutputMessage, None] | Tuple[None, str]:
        """Convert notification to OutputMessage for platform rendering.
        
        Args:
            notification: Notification dict from create_notification
            
        Returns:
            (OutputMessage, None) on success
            (None, error_message) on failure
        """
        try:
            # Map string color to OutputColor enum
            color_map = {
                "info": OutputColor.INFO,
                "warning": OutputColor.WARNING,
                "error": OutputColor.ERROR,
                "success": OutputColor.SUCCESS,
            }
            color = color_map.get(notification.get("color", "info"), OutputColor.INFO)
            
            output = OutputMessage(
                title=notification.get("title"),
                description=notification.get("description"),
                color=color,
                timestamp=notification.get("created_at")
            )
            
            # Add fields
            fields = notification.get("fields", {})
            for name, value in fields.items():
                output.add_field(name, str(value), inline=True)
            
            # Set footer
            level = notification.get("level", "INFO")
            output.set_footer(f"{level} Notification", None)
            
            return output, None
            
        except Exception as e:
            logger.error(f"[🔔] Failed to convert to OutputMessage: {e}")
            return None, f"Failed to convert to OutputMessage: {str(e)}"
