"""
Regression tests for ISSUE-006: guild_id=0 spurious entries in content delivery.

Tests verify that:
1. When guild config is empty, no content is created for guild_id=0
2. Content delivery does not attempt to process guild_id=0
3. Scheduler does not enqueue jobs for guild_id=0
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime


class TestGuildIdZeroNotCreated(unittest.TestCase):
    """Test that guild_id=0 is never created in content delivery."""

    @patch("abby_core.database.collections.guild_configuration.get_all_guild_configs")
    async def test_empty_guild_list_does_not_create_guild_zero_content(self, mock_get_configs):
        """
        REQUIREMENT: When get_all_guild_configs() returns empty list,
        events_lifecycle should NOT create content with guild_id=0 as fallback.
        
        Root cause: events_lifecycle._create_content_items_for_all_guilds() does:
            if not guild_ids: guild_ids = [0]  ← FALLBACK CREATES SPURIOUS GUILD 0
        
        Fix: Remove fallback; if no guilds, do not create content.
        """
        mock_get_configs.return_value = []  # Empty guild list
        
        from abby_core.services.events_lifecycle import _create_content_items_for_all_guilds
        from abby_core.database.collections.content_delivery import create_content_delivery_item
        
        # Mock content delivery to track what guild_ids are used
        created_guild_ids = []
        
        async def mock_create_content(**kwargs):
            created_guild_ids.append(kwargs.get("guild_id"))
            return {"inserted_id": "test_id"}
        
        with patch(
            "abby_core.database.collections.content_delivery.create_content_delivery_item",
            side_effect=mock_create_content
        ):
            # Simulate event trigger (e.g., daily announcement)
            await _create_content_items_for_all_guilds(
                content_type="daily_announcement",
                content_body="Test announcement",
                created_by="system"
            )
        
        # ASSERTION: guild_id=0 should NOT appear in created items
        self.assertNotIn(
            0, created_guild_ids,
            f"Spurious guild_id=0 was created when guild list was empty. "
            f"Created guild_ids: {created_guild_ids}. "
            f"Fix: Remove the fallback 'guild_ids = [0]' when no real guilds exist."
        )

    @patch("abby_core.database.collections.guild_configuration.get_all_guild_configs")
    async def test_empty_guild_list_prevents_content_creation_entirely(self, mock_get_configs):
        """
        REQUIREMENT: When no guild configs exist, no content items should be
        created at all (not even for guild_id=0).
        """
        mock_get_configs.return_value = []
        
        from abby_core.services.events_lifecycle import _create_content_items_for_all_guilds
        
        creation_count = 0
        
        async def mock_create_content(**kwargs):
            nonlocal creation_count
            creation_count += 1
            return {"inserted_id": "test_id"}
        
        with patch(
            "abby_core.database.collections.content_delivery.create_content_delivery_item",
            side_effect=mock_create_content
        ):
            await _create_content_items_for_all_guilds(
                content_type="daily_announcement",
                content_body="Test announcement",
                created_by="system"
            )
        
        # ASSERTION: No content should be created when guild list is empty
        self.assertEqual(
            creation_count, 0,
            f"Expected 0 content items created when guild list is empty, "
            f"but {creation_count} were created. This indicates fallback guild_id=0 is active."
        )

    def test_scheduler_filters_guild_id_zero_completely(self):
        """
        SANITY CHECK: Verify that scheduler's guild_id filtering is in place
        (even though it works, we should not rely on it; root cause is in events_lifecycle).
        """
        from abby_core.services.scheduler import SchedulerService
        
        service = SchedulerService()
        
        # Test: _normalize_guild_id should return None for guild_id <= 0
        result = service._normalize_guild_id(0)
        
        # ASSERTION: guild_id=0 should normalize to None (filtered out)
        self.assertIsNone(
            result,
            "Scheduler filtering for guild_id <= 0 is present and working, "
            "but the root issue is that guild_id=0 is being created in events_lifecycle."
        )
        
        # Also test negative and positive for completeness
        self.assertIsNone(service._normalize_guild_id(-1), "Negative guild_id should be filtered")
        self.assertEqual(service._normalize_guild_id(123), 123, "Positive guild_id should pass through")

    @patch("abby_core.database.collections.guild_configuration.get_all_guild_configs")
    async def test_valid_guild_list_creates_content_normally(self, mock_get_configs):
        """
        POSITIVE TEST: Verify that when real guilds exist, content is created
        for those guilds (not guild_id=0).
        """
        # Mock valid guild list
        mock_get_configs.return_value = [
            {"guild_id": 111111111, "name": "Guild A"},
            {"guild_id": 222222222, "name": "Guild B"},
        ]
        
        from abby_core.services.events_lifecycle import _create_content_items_for_all_guilds
        
        created_guild_ids = []
        
        async def mock_create_content(**kwargs):
            created_guild_ids.append(kwargs.get("guild_id"))
            return {"inserted_id": "test_id"}
        
        with patch(
            "abby_core.database.collections.content_delivery.create_content_delivery_item",
            side_effect=mock_create_content
        ):
            await _create_content_items_for_all_guilds(
                content_type="daily_announcement",
                content_body="Test announcement",
                created_by="system"
            )
        
        # ASSERTION: Only real guilds should be in created items
        self.assertIn(111111111, created_guild_ids, "Guild A should be created")
        self.assertIn(222222222, created_guild_ids, "Guild B should be created")
        self.assertNotIn(0, created_guild_ids, "guild_id=0 should never be created")
        self.assertEqual(len(created_guild_ids), 2, "Should create exactly 2 items for 2 guilds")


if __name__ == "__main__":
    unittest.main()
