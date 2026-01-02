"""
User and Global Storage Quota Management

Tracks storage usage per user and globally, enforcing limits to prevent:
- Server HD bloat from unlimited image generation
- Per-user hoarding of generated images
- Runaway quota usage
"""

import os
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from datetime import datetime, timedelta
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


class QuotaManager:
    """Manages storage quotas and rate limiting."""
    
    def __init__(
        self,
        storage_dir: Path,
        max_global_storage_mb: int = 5000,
        max_user_storage_mb: int = 500,
        max_user_daily_gens: int = 5,
        owner_ids: Optional[List[str]] = None,
        owner_daily_limit: Optional[int] = None,
        role_daily_limits: Optional[Dict[str, int]] = None,
        level_bands: Optional[List[Tuple[int, int]]] = None,
    ):
        """
        Initialize quota manager.
        
        Args:
            storage_dir: Root storage directory
            max_global_storage_mb: Maximum total storage in MB (default 5GB)
            max_user_storage_mb: Maximum per-user storage in MB (default 500MB)
            max_user_daily_gens: Maximum image generations per user per day
        """
        self.storage_dir = storage_dir
        self.max_global_storage_mb = max_global_storage_mb
        self.max_user_storage_mb = max_user_storage_mb
        self.max_user_daily_gens = max_user_daily_gens
        self.owner_ids = {str(uid) for uid in (owner_ids or []) if str(uid)}
        self.owner_daily_limit = owner_daily_limit if owner_daily_limit is not None else max_user_daily_gens * 10
        self.role_daily_limits = {str(role_id): limit for role_id, limit in (role_daily_limits or {}).items() if limit}
        normalized_bands: List[Tuple[int, int]] = []
        for band in level_bands or []:
            if isinstance(band, dict):
                min_level_val = band.get("min_level")
                daily_limit_val = band.get("daily_limit", max_user_daily_gens)
                if min_level_val is None or daily_limit_val is None:
                    continue
                min_level = int(min_level_val)
                daily_limit = int(daily_limit_val)
            else:
                try:
                    min_level, daily_limit = band
                    if min_level is None or daily_limit is None:
                        continue
                except Exception:
                    continue
            normalized_bands.append((min_level, daily_limit))
        self.level_bands = sorted(normalized_bands, key=lambda b: b[0])
        
        # In-memory tracking of daily generation counts
        # Format: {(user_id, guild_id): {'date': date, 'count': int}}
        self._generation_tracking: Dict[Tuple[str, str], Dict] = {}
        
        logger.info(f"[💾] Quota manager initialized")
        logger.info(f"    Global limit: {max_global_storage_mb}MB")
        logger.info(f"    Per-user limit: {max_user_storage_mb}MB")
        logger.info(f"    Daily gen limit: {max_user_daily_gens}/day")
    
    def get_global_usage(self) -> Tuple[float, float, float]:
        """
        Get global storage usage.
        
        Returns:
            Tuple of (used_mb, total_mb, percentage)
        """
        total_size = 0
        for root, dirs, files in os.walk(self.storage_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, IOError):
                    pass
        
        used_mb = total_size / (1024 * 1024)
        percentage = (used_mb / self.max_global_storage_mb) * 100
        
        return used_mb, float(self.max_global_storage_mb), percentage
    
    def get_user_usage(self, user_id: str) -> Tuple[float, float, float]:
        """
        Get per-user storage usage.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Tuple of (used_mb, limit_mb, percentage)
        """
        user_dir = self.storage_dir / "users" / user_id
        
        if not user_dir.exists():
            return 0.0, float(self.max_user_storage_mb), 0.0
        
        total_size = 0
        for root, dirs, files in os.walk(user_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, IOError):
                    pass
        
        used_mb = total_size / (1024 * 1024)
        percentage = (used_mb / self.max_user_storage_mb) * 100
        
        return used_mb, float(self.max_user_storage_mb), percentage

    def _hours_until_reset(self) -> float:
        """Hours until the next UTC day reset."""
        now = datetime.utcnow()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = tomorrow - now
        return round(delta.total_seconds() / 3600, 1)

    def resolve_daily_limit(
        self,
        user_id: str,
        user_roles: Optional[List[str]] = None,
        user_level: Optional[int] = None,
    ) -> int:
        """Compute daily limit with owner, role, and level overrides."""
        limit = self.max_user_daily_gens

        if str(user_id) in self.owner_ids:
            limit = max(limit, self.owner_daily_limit)

        for role_id in user_roles or []:
            role_limit = self.role_daily_limits.get(str(role_id))
            if role_limit:
                limit = max(limit, role_limit)

        if user_level is not None:
            for min_level, band_limit in self.level_bands:
                if user_level >= min_level:
                    limit = max(limit, band_limit)

        return limit
    
    def check_global_quota(self, required_mb: float = 1.0) -> bool:
        """
        Check if global quota allows additional storage.
        
        Args:
            required_mb: Space needed in MB
            
        Returns:
            True if space available, False otherwise
        """
        used_mb, total_mb, _ = self.get_global_usage()
        available = total_mb - used_mb
        return available >= required_mb
    
    def check_user_quota(self, user_id: str, required_mb: float = 1.0) -> bool:
        """
        Check if user quota allows additional storage.
        
        Args:
            user_id: Discord user ID
            required_mb: Space needed in MB
            
        Returns:
            True if space available, False otherwise
        """
        used_mb, limit_mb, _ = self.get_user_usage(user_id)
        available = limit_mb - used_mb
        return available >= required_mb
    
    def check_daily_limit(
        self,
        user_id: str,
        user_roles: Optional[List[str]] = None,
        user_level: Optional[int] = None,
        guild_id: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """
        Check if user has remaining daily generations.
        
        Args:
            user_id: Discord user ID
            user_roles: User's role IDs
            user_level: User's level in the guild
            guild_id: Discord guild ID (for guild-specific tracking)
            
        Returns:
            Tuple of (allowed, remaining_count)
        """
        today = datetime.utcnow().date()
        tracking_key = (user_id, guild_id or "global")
        
        # Reset if date changed
        if tracking_key in self._generation_tracking:
            tracked_date = self._generation_tracking[tracking_key].get('date')
            if tracked_date != today:
                self._generation_tracking[tracking_key] = {'date': today, 'count': 0}
        else:
            self._generation_tracking[tracking_key] = {'date': today, 'count': 0}
        
        current_count = self._generation_tracking[tracking_key]['count']
        daily_limit = self.resolve_daily_limit(user_id, user_roles=user_roles, user_level=user_level)
        remaining = daily_limit - current_count

        return remaining > 0, max(0, remaining)
    
    def increment_generation_count(self, user_id: str, guild_id: Optional[str] = None) -> int:
        """
        Increment daily generation count for user.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            New count
        """
        today = datetime.utcnow().date()
        tracking_key = (user_id, guild_id or "global")
        
        if tracking_key not in self._generation_tracking:
            self._generation_tracking[tracking_key] = {'date': today, 'count': 0}
        
        tracking = self._generation_tracking[tracking_key]
        if tracking.get('date') != today:
            tracking = {'date': today, 'count': 0}
            self._generation_tracking[tracking_key] = tracking
        
        tracking['count'] += 1
        return tracking['count']
    
    def get_quota_status(
        self,
        user_id: str,
        user_roles: Optional[List[str]] = None,
        user_level: Optional[int] = None,
        guild_id: Optional[str] = None,
    ) -> Dict:
        """
        Get comprehensive quota status for user.
        
        Args:
            user_id: Discord user ID
            user_roles: User's role IDs
            user_level: User's level in the guild
            guild_id: Discord guild ID
            
        Returns:
            Dict with quota information
        """
        global_used, global_total, global_pct = self.get_global_usage()
        user_used, user_limit, user_pct = self.get_user_usage(user_id)
        daily_limit = self.resolve_daily_limit(user_id, user_roles=user_roles, user_level=user_level)
        daily_allowed, daily_remaining = self.check_daily_limit(
            user_id,
            user_roles=user_roles,
            user_level=user_level,
            guild_id=guild_id,
        )
        
        return {
            'global': {
                'used_mb': round(global_used, 2),
                'total_mb': global_total,
                'percentage': round(global_pct, 1),
                'status': 'OK' if global_pct < 80 else 'WARNING' if global_pct < 95 else 'CRITICAL',
            },
            'user': {
                'used_mb': round(user_used, 2),
                'limit_mb': user_limit,
                'percentage': round(user_pct, 1),
                'status': 'OK' if user_pct < 80 else 'WARNING' if user_pct < 95 else 'CRITICAL',
            },
            'daily': {
                'allowed': daily_allowed,
                'remaining': daily_remaining,
                'limit': daily_limit,
                'reset_hours': self._hours_until_reset(),
            }
        }
