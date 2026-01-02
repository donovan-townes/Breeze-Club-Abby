"""
Centralized Storage Management

Handles file operations, path management, and quota enforcement for:
- Image generation (temp and persistent)
- User-specific storage
- Automatic cleanup policies
"""

import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from datetime import datetime, timedelta
from abby_core.observability.logging import setup_logging, logging
from .quota_manager import QuotaManager

setup_logging()
logger = logging.getLogger(__name__)


class StorageManager:
    """Centralized file storage management with quotas and cleanup."""
    
    def __init__(
        self,
        storage_root: Optional[Path] = None,
        max_global_storage_mb: int = 5000,
        max_user_storage_mb: int = 500,
        max_user_daily_gens: int = 5,
        cleanup_days: int = 7,
        owner_user_ids: Optional[List[str]] = None,
        owner_daily_limit: Optional[int] = None,
        role_daily_limits: Optional[Dict[str, int]] = None,
        level_bands: Optional[List[Tuple[int, int]]] = None,
    ):
        """
        Initialize storage manager.
        
        Args:
            storage_root: Root storage directory (default: project_root/shared)
            max_global_storage_mb: Maximum total storage in MB
            max_user_storage_mb: Maximum per-user storage in MB
            max_user_daily_gens: Maximum image generations per user per day
            cleanup_days: Delete temp files older than this many days
        """
        # Set storage root
        if storage_root is None:
            # Default to project root/shared
            project_root = Path(__file__).parent.parent.parent
            storage_root = project_root / "shared"
        
        self.storage_root = Path(storage_root)
        self.cleanup_days = cleanup_days
        
        # Create subdirectories
        self.images_dir = self.storage_root / "images"
        self.temp_dir = self.storage_root / "temp"
        self.users_dir = self.images_dir / "users"
        
        # Create directories if they don't exist
        self._ensure_directories()
        
        # Initialize quota manager
        self.quota_manager = QuotaManager(
            self.images_dir,
            max_global_storage_mb=max_global_storage_mb,
            max_user_storage_mb=max_user_storage_mb,
            max_user_daily_gens=max_user_daily_gens,
            owner_ids=owner_user_ids,
            owner_daily_limit=owner_daily_limit,
            role_daily_limits=role_daily_limits,
            level_bands=level_bands,
        )
        
        logger.info(f"[💾] Storage manager initialized")
        logger.info(f"    Root: {self.storage_root}")
        logger.info(f"    Images: {self.images_dir}")
        logger.info(f"    Temp: {self.temp_dir}")
        logger.info(f"    Cleanup: {cleanup_days} days")
    
    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        for directory in [self.storage_root, self.images_dir, self.temp_dir, self.users_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save_image(
        self,
        image_data: bytes,
        user_id: str,
        image_name: str = "image.png",
        is_temp: bool = False,
        user_roles: Optional[List[str]] = None,
        user_level: Optional[int] = None,
        guild_id: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Save an image file with quota checks.
        
        Args:
            image_data: Binary image data
            user_id: Discord user ID
            image_name: Filename for the image
            is_temp: If True, save to temp directory instead of user storage
            user_roles: User's role IDs
            user_level: User's level in the guild
            guild_id: Discord guild ID
            
        Returns:
            Tuple of (success, message, file_path)
        """
        try:
            # Check quotas
            size_mb = len(image_data) / (1024 * 1024)
            
            if not self.quota_manager.check_global_quota(size_mb):
                return False, "Server storage is full. Please try again later.", None
            
            if not is_temp and not self.quota_manager.check_user_quota(user_id, size_mb):
                return False, "Your storage quota is full. Please delete some images.", None
            
            # Check daily limit
            if not is_temp:
                allowed, remaining = self.quota_manager.check_daily_limit(
                    user_id,
                    user_roles=user_roles,
                    user_level=user_level,
                    guild_id=guild_id,
                )
                if not allowed:
                    return False, f"Daily generation limit reached. Try again tomorrow.", None
                self.quota_manager.increment_generation_count(user_id, guild_id=guild_id)
            
            # Determine save path
            if is_temp:
                save_dir = self.temp_dir
            else:
                save_dir = self.users_dir / user_id
                save_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = save_dir / image_name
            with open(file_path, "wb") as f:
                f.write(image_data)
            
            logger.info(f"[📸] Image saved: {file_path} ({size_mb:.2f}MB)")
            
            return True, f"Image saved successfully ({size_mb:.2f}MB)", file_path
        
        except Exception as e:
            logger.error(f"[❌] Error saving image: {str(e)}")
            return False, f"Error saving image: {str(e)}", None
    
    def get_image_path(
        self,
        user_id: str,
        image_name: str = "image.png",
    ) -> Optional[Path]:
        """
        Get path to user's image.
        
        Args:
            user_id: Discord user ID
            image_name: Filename
            
        Returns:
            Path if exists, None otherwise
        """
        file_path = self.users_dir / user_id / image_name
        
        if file_path.exists():
            return file_path
        
        return None
    
    def delete_image(
        self,
        user_id: str,
        image_name: str = "image.png",
    ) -> Tuple[bool, str]:
        """
        Delete a user's image.
        
        Args:
            user_id: Discord user ID
            image_name: Filename
            
        Returns:
            Tuple of (success, message)
        """
        try:
            file_path = self.users_dir / user_id / image_name
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"[🗑️] Image deleted: {file_path}")
                return True, f"Image '{image_name}' deleted."
            
            return False, f"Image '{image_name}' not found."
        
        except Exception as e:
            logger.error(f"[❌] Error deleting image: {str(e)}")
            return False, f"Error deleting image: {str(e)}"
    
    def cleanup_old_files(self, directory: Optional[Path] = None) -> Tuple[int, float]:
        """
        Delete files older than cleanup_days.
        
        Args:
            directory: Directory to clean (default: temp_dir)
            
        Returns:
            Tuple of (files_deleted, space_freed_mb)
        """
        if directory is None:
            directory = self.temp_dir
        
        if not directory.exists():
            return 0, 0.0
        
        cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
        files_deleted = 0
        space_freed = 0.0
        
        try:
            for file in directory.glob("**/*"):
                if file.is_file():
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    
                    if mtime < cutoff_time:
                        space_freed += file.stat().st_size / (1024 * 1024)
                        file.unlink()
                        files_deleted += 1
        
        except Exception as e:
            logger.error(f"[❌] Error during cleanup: {str(e)}")
        
        if files_deleted > 0:
            logger.info(f"[🧹] Cleanup: Deleted {files_deleted} files, freed {space_freed:.2f}MB")
        
        return files_deleted, space_freed
    
    def get_quota_status(
        self,
        user_id: str,
        user_roles: Optional[List[str]] = None,
        user_level: Optional[int] = None,
        guild_id: Optional[str] = None,
    ) -> dict:
        """
        Get quota status for user.
        
        Args:
            user_id: Discord user ID
            user_roles: User's role IDs
            user_level: User's level in the guild
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with quota information
        """
        return self.quota_manager.get_quota_status(
            user_id,
            user_roles=user_roles,
            user_level=user_level,
            guild_id=guild_id,
        )
    
    def get_user_images(self, user_id: str) -> list:
        """
        List all images for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            List of image filenames
        """
        user_dir = self.users_dir / user_id
        
        if not user_dir.exists():
            return []
        
        images = []
        for file in user_dir.glob("*.png"):
            images.append(file.name)
        for file in user_dir.glob("*.jpg"):
            images.append(file.name)
        for file in user_dir.glob("*.jpeg"):
            images.append(file.name)
        
        return sorted(images)
