"""
User Service - Platform-agnostic user profile and privacy operations

Provides centralized business logic for user data management:
- Profile management (user links, accounts)
- Privacy operations (opt-out, memory management)
- Data export (GDPR compliance)
- Conversation management

All methods return (success: bool, error: str | None) or (result, error).
Zero platform dependencies - usable by Discord, Web, CLI adapters.
"""

from typing import Optional, Any, Dict, List, Tuple
from datetime import datetime
from enum import Enum
import json
from io import BytesIO

from abby_core.database import mongodb as mongo_db
from abby_core.database.collections.guild_configuration import (
    get_guild_setting,
    set_guild_setting,
)
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class DataExportType(str, Enum):
    """Types of data exports."""
    MEMORY = "memory"
    CONVERSATIONS = "conversations"
    FULL = "full"


class UserAuditAction(str, Enum):
    """User service audit actions."""
    LINK_ACCOUNT = "link_account"
    UNLINK_ACCOUNT = "unlink_account"
    TOGGLE_OPTOUT = "toggle_optout"
    FORGET_MEMORY = "forget_memory"
    CLEAR_CONVERSATIONS = "clear_conversations"
    EXPORT_DATA = "export_data"


class UserService:
    """
    Platform-agnostic user data management service.
    
    Handles:
    - User profile and linked accounts
    - Privacy settings and opt-out
    - Memory management
    - Conversation history
    - Data export (GDPR)
    
    Thread-safe singleton pattern via get_user_service().
    """
    
    def __init__(self):
        """Initialize user service with database connection."""
        import os
        self.db_client = mongo_db.connect_to_mongodb()
        db_name = os.getenv("MONGODB_DB", "Abby_Database")
        self.db = self.db_client[db_name]
        logger.debug("[👤] UserService initialized")
    
    # ═══════════════════════════════════════════════════════════════════════
    # PROFILE & LINKED ACCOUNTS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_user_links(self, user_id: int | str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get linked accounts for user.
        
        Args:
            user_id: User ID (int or str)
        
        Returns:
            (links_dict, error): Links dict or None, error message or None
        """
        try:
            user_id_str = str(user_id)
            links_col = self.db["user_links"]
            links = links_col.find_one({"user_id": user_id_str})
            
            if not links:
                # Return empty dict with user_id as baseline
                return {"user_id": user_id_str}, None
            
            return links, None
        
        except Exception as e:
            error = f"Failed to get user links: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    def link_platform_account(
        self,
        user_id: int | str,
        platform: str,
        handle: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Link a platform account for user.
        
        Args:
            user_id: User ID
            platform: Platform name (e.g., "twitch_handle", "steam_id")
            handle: Platform handle/username
        
        Returns:
            (success, error): True on success, error message or None
        """
        try:
            user_id_str = str(user_id)
            links_col = self.db["user_links"]
            
            links_col.update_one(
                {"user_id": user_id_str},
                {"$set": {platform: handle}},
                upsert=True
            )
            
            self._log_audit(
                user_id_str,
                UserAuditAction.LINK_ACCOUNT,
                details={"platform": platform, "handle": handle}
            )
            
            logger.info(f"[👤] User {user_id} linked {platform}: {handle}")
            return True, None
        
        except Exception as e:
            error = f"Failed to link {platform}: {e}"
            logger.error(f"[❌] {error}")
            return False, error
    
    def unlink_platform_account(
        self,
        user_id: int | str,
        platform: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Unlink a platform account for user.
        
        Args:
            user_id: User ID
            platform: Platform name to unlink
        
        Returns:
            (success, error): True on success, error message or None
        """
        try:
            user_id_str = str(user_id)
            links_col = self.db["user_links"]
            
            links_col.update_one(
                {"user_id": user_id_str},
                {"$unset": {platform: ""}},
                upsert=True
            )
            
            self._log_audit(
                user_id_str,
                UserAuditAction.UNLINK_ACCOUNT,
                details={"platform": platform}
            )
            
            logger.info(f"[👤] User {user_id} unlinked {platform}")
            return True, None
        
        except Exception as e:
            error = f"Failed to unlink {platform}: {e}"
            logger.error(f"[❌] {error}")
            return False, error
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRIVACY & OPT-OUT
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_optout_status(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has opted out of memory collection.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional, 0 for global)
        
        Returns:
            (opted_out, error): True if opted out, error message or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_int = int(guild_id) if guild_id else 0
            
            opted_out = get_guild_setting(
                guild_id_int,
                f"user_opted_out_{user_id_str}",
                False
            )
            
            return bool(opted_out), None
        
        except Exception as e:
            error = f"Failed to check opt-out status: {e}"
            logger.error(f"[❌] {error}")
            return False, error
    
    def toggle_optout(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Toggle user opt-out status for memory collection.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional, 0 for global)
        
        Returns:
            (new_status, error): New opt-out status (True/False), error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_int = int(guild_id) if guild_id else 0
            
            # Get current status
            current_status = get_guild_setting(
                guild_id_int,
                f"user_opted_out_{user_id_str}",
                False
            )
            
            # Toggle it
            new_status = not current_status
            
            set_guild_setting(
                guild_id_int,
                f"user_opted_out_{user_id_str}",
                new_status
            )
            
            self._log_audit(
                user_id_str,
                UserAuditAction.TOGGLE_OPTOUT,
                details={"opted_out": new_status, "guild_id": str(guild_id_int)}
            )
            
            logger.info(f"[👤] User {user_id} opted out: {new_status}")
            return new_status, None
        
        except Exception as e:
            error = f"Failed to toggle opt-out: {e}"
            logger.error(f"[❌] {error}")
            return False, error
    
    # ═══════════════════════════════════════════════════════════════════════
    # MEMORY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_memory_stats(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get memory statistics for user.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            (stats_dict, error): Stats dict with counts/info, error or None
        """
        try:
            from abby_core.database.collections.users import Users
            
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            profiles_col = Users.get_collection()
            
            query: Dict[str, str] = {"user_id": user_id_str}
            if guild_id_str:
                query["guild_id"] = guild_id_str
            
            profile = profiles_col.find_one(query)
            
            if not profile:
                return {
                    "memory_count": 0,
                    "has_profile": False
                }, None
            
            facts = profile.get("creative_profile", {}).get("memorable_facts", [])
            
            return {
                "memory_count": len(facts),
                "has_profile": True,
                "username": profile.get("discord", {}).get("username") or profile.get("username"),
                "nickname": profile.get("nickname")
            }, None
        
        except Exception as e:
            error = f"Failed to get memory stats: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    def forget_memory(
        self,
        user_id: int | str,
        memory_text: str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Delete a specific memory by text match.
        
        Args:
            user_id: User ID
            memory_text: Exact text of memory to forget
            guild_id: Guild ID (optional)
        
        Returns:
            (success, error): True if found and deleted, error or None
        """
        try:
            from abby_core.database.collections.users import Users
            
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            profiles_col = Users.get_collection()
            
            query: Dict[str, str] = {"user_id": user_id_str}
            if guild_id_str:
                query["guild_id"] = guild_id_str
            
            result = profiles_col.update_one(
                query,
                {
                    "$pull": {
                        "creative_profile.memorable_facts": {
                            "text": {"$regex": f"^{memory_text}$", "$options": "i"}
                        }
                    }
                }
            )
            
            if result.modified_count > 0:
                self._log_audit(
                    user_id_str,
                    UserAuditAction.FORGET_MEMORY,
                    details={"memory_text": memory_text, "guild_id": guild_id_str}
                )
                
                logger.info(f"[👤] User {user_id} forgot memory: {memory_text}")
                return True, None
            else:
                return False, "Memory not found"
        
        except Exception as e:
            error = f"Failed to forget memory: {e}"
            logger.error(f"[❌] {error}")
            return False, error
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONVERSATION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_conversation_stats(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get conversation statistics for user.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            (stats_dict, error): Stats with session counts, error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            sessions_col = self.db["chat_sessions"]
            
            query: Dict[str, str] = {"user_id": user_id_str}
            if guild_id_str:
                query["guild_id"] = guild_id_str
            
            session_count = sessions_col.count_documents(query)
            
            # Get most recent session
            recent = sessions_col.find_one(query, sort=[("updated_at", -1)])
            
            return {
                "session_count": session_count,
                "last_session": recent.get("updated_at") if recent else None
            }, None
        
        except Exception as e:
            error = f"Failed to get conversation stats: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    def clear_conversations(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[int, Optional[str]]:
        """
        Clear all conversation sessions for user.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            (deleted_count, error): Number deleted, error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            sessions_col = self.db["chat_sessions"]
            
            query: Dict[str, str] = {"user_id": user_id_str}
            if guild_id_str:
                query["guild_id"] = guild_id_str
            
            result = sessions_col.delete_many(query)
            
            self._log_audit(
                user_id_str,
                UserAuditAction.CLEAR_CONVERSATIONS,
                details={"deleted_count": result.deleted_count, "guild_id": guild_id_str}
            )
            
            logger.info(f"[👤] User {user_id} cleared {result.deleted_count} sessions")
            return result.deleted_count, None
        
        except Exception as e:
            error = f"Failed to clear conversations: {e}"
            logger.error(f"[❌] {error}")
            return 0, error
    
    # ═══════════════════════════════════════════════════════════════════════
    # DATA EXPORT (GDPR)
    # ═══════════════════════════════════════════════════════════════════════
    
    def export_memory_data(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None,
        memory_service: Optional[Any] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Export memory data as JSON-serializable dict.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
            memory_service: Optional memory service instance
        
        Returns:
            (export_dict, error): Export data dict, error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            # Try to use memory service if provided
            if memory_service:
                profile = memory_service.get_profile(user_id_str, guild_id_str)
            else:
                # Fall back to Users collection
                from abby_core.database.collections.users import Users
                profiles_col = Users.get_collection()
                query: Dict[str, str] = {"user_id": user_id_str}
                if guild_id_str:
                    query["guild_id"] = guild_id_str
                profile = profiles_col.find_one(query)
            
            if not profile:
                return None, "No memory data found"
            
            # Build export dict
            memorable_facts = profile.get("creative_profile", {}).get("memorable_facts", [])
            
            # Convert datetime objects to strings
            for fact in memorable_facts:
                for date_field in ["added_at", "last_confirmed"]:
                    if date_field in fact and hasattr(fact[date_field], "isoformat"):
                        fact[date_field] = fact[date_field].isoformat()
            
            export_data = {
                "user_id": user_id_str,
                "guild_id": guild_id_str,
                "export_date": datetime.utcnow().isoformat(),
                "export_type": DataExportType.MEMORY.value,
                "profile": {
                    # Extract from discord object if available, else from platform-agnostic fields
                    "username": profile.get("discord", {}).get("username") or profile.get("username"),
                    "nickname": profile.get("nickname"),
                    "memorable_facts": memorable_facts
                }
            }
            
            self._log_audit(
                user_id_str,
                UserAuditAction.EXPORT_DATA,
                details={"export_type": "memory", "guild_id": guild_id_str}
            )
            
            logger.info(f"[👤] User {user_id} exported memory data")
            return export_data, None
        
        except Exception as e:
            error = f"Failed to export memory: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    def export_conversation_data(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Export conversation data as JSON-serializable dict.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            (export_dict, error): Export data dict, error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            sessions_col = self.db["chat_sessions"]
            
            query: Dict[str, str] = {"user_id": user_id_str}
            if guild_id_str:
                query["guild_id"] = guild_id_str
            
            sessions = list(sessions_col.find(query))
            
            if not sessions:
                return None, "No conversation data found"
            
            # Remove MongoDB _id and convert dates
            for session in sessions:
                if "_id" in session:
                    del session["_id"]
                for date_field in ["created_at", "updated_at"]:
                    if date_field in session and hasattr(session[date_field], "isoformat"):
                        session[date_field] = session[date_field].isoformat()
            
            export_data = {
                "user_id": user_id_str,
                "guild_id": guild_id_str,
                "export_date": datetime.utcnow().isoformat(),
                "export_type": DataExportType.CONVERSATIONS.value,
                "sessions": sessions
            }
            
            self._log_audit(
                user_id_str,
                UserAuditAction.EXPORT_DATA,
                details={"export_type": "conversations", "guild_id": guild_id_str}
            )
            
            logger.info(f"[👤] User {user_id} exported conversation data")
            return export_data, None
        
        except Exception as e:
            error = f"Failed to export conversations: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    def export_all_data(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None,
        memory_service: Optional[Any] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Export all user data as combined JSON-serializable dict.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
            memory_service: Optional memory service instance
        
        Returns:
            (export_dict, error): Combined export data, error or None
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            
            export_data: Dict[str, Any] = {
                "user_id": user_id_str,
                "guild_id": guild_id_str,
                "export_date": datetime.utcnow().isoformat(),
                "export_type": DataExportType.FULL.value,
                "memory": {},
                "conversations": []
            }
            
            # Try to include memory data
            memory_data, mem_error = self.export_memory_data(user_id_str, guild_id_str, memory_service)
            if memory_data:
                export_data["memory"] = memory_data.get("profile", {})
            elif mem_error:
                logger.warning(f"[👤] Failed to include memory in full export: {mem_error}")
            
            # Try to include conversation data
            conv_data, conv_error = self.export_conversation_data(user_id_str, guild_id_str)
            if conv_data:
                export_data["conversations"] = conv_data.get("sessions", [])
            elif conv_error:
                logger.warning(f"[👤] Failed to include conversations in full export: {conv_error}")
            
            self._log_audit(
                user_id_str,
                UserAuditAction.EXPORT_DATA,
                details={"export_type": "full", "guild_id": guild_id_str}
            )
            
            logger.info(f"[👤] User {user_id} exported full data")
            return export_data, None
        
        except Exception as e:
            error = f"Failed to export all data: {e}"
            logger.error(f"[❌] {error}")
            return None, error
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════
    
    def _log_audit(
        self,
        user_id: str,
        action: UserAuditAction,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit trail for user actions.
        
        Args:
            user_id: User ID
            action: Action type
            details: Additional details dict
        """
        try:
            audit_col = self.db["user_audit_log"]
            
            audit_entry = {
                "user_id": user_id,
                "action": action.value,
                "timestamp": datetime.utcnow(),
                "details": details or {}
            }
            
            audit_col.insert_one(audit_entry)
        
        except Exception as e:
            # Don't fail operations due to audit logging issues
            logger.error(f"[❌] Failed to log audit: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════

_user_service_instance: Optional[UserService] = None


def get_user_service() -> UserService:
    """
    Get or create the singleton UserService instance.
    
    Returns:
        UserService: The global service instance
    """
    global _user_service_instance
    
    if _user_service_instance is None:
        _user_service_instance = UserService()
    
    return _user_service_instance
