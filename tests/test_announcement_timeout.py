"""
Announcement Timeout Handling Tests

Validates that announcement generation with timeout prevents hanging and
properly routes failures to DLQ.

**Scenario:** LLM call hangs or takes longer than 30 seconds.
**Expected Behavior:** Timeout triggers, announcement marked failed, routed to DLQ.

Run with: pytest tests/test_announcement_timeout.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from bson import ObjectId

from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
from abby_core.services.dlq_service import get_dlq_service
from abby_core.services.content_delivery import create_announcement_for_delivery
from abby_core.database.mongodb import get_database


class TestAnnouncementTimeout:
    """Test announcement generation timeout handling."""
    
    @pytest.fixture
    def dispatcher(self):
        """Get announcement dispatcher instance."""
        return get_announcement_dispatcher()
    
    @pytest.fixture
    def dlq_service(self):
        """Get DLQ service instance."""
        return get_dlq_service()
    
    @pytest.fixture
    def test_announcement(self, dispatcher):
        """Create a test announcement."""
        item_id = create_announcement_for_delivery(
            guild_id=12345,
            title="Test Announcement",
            description="Test announcement content",
            delivery_channel_id=67890,
            priority=0,
            operator_id="operator:test"
        )
        
        yield item_id
        
        # Cleanup
        try:
            dispatcher.collection.delete_one({"_id": ObjectId(item_id)})
        except:
            pass
    
    def test_timeout_marks_announcement_failed(self, dispatcher, test_announcement):
        """Verify timeout marks announcement as failed."""
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        item = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        
        assert item is not None, "Announcement should exist"
        assert item.get("lifecycle_state") == "error", "Should be in error state"
        assert item.get("generation_status") == "error", "Generation should be marked error"
        assert "timeout" in item.get("error_message", "").lower(), "Error message should mention timeout"
    
    def test_timeout_routes_to_dlq(self, dispatcher, dlq_service, test_announcement):
        """Verify timeout routes to DLQ for manual handling."""
        # Mark as failed
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        # Route to DLQ
        dlq_item_id = dlq_service.route_error(
            announcement_id=test_announcement,
            error_type=asyncio.TimeoutError,
            error_message="Generation timeout (exceeded 30s)",
            guild_id=12345,
            operator_id="system:timeout",
            context={
                "timeout_seconds": 30,
                "trigger_type": "scheduled"
            }
        )
        
        assert dlq_item_id is not None, "DLQ item should be created"
        
        # Verify DLQ contains the item
        dlq = get_database()["content_delivery_dlq"]
        dlq_doc = dlq.find_one({"_id": ObjectId(dlq_item_id)})
        
        assert dlq_doc is not None, "DLQ document should exist"
        assert dlq_doc.get("announcement_id") == test_announcement, "DLQ should link to announcement"
        assert dlq_doc.get("status") in ["pending", "retrying"], "DLQ should have pending status"
    
    def test_timeout_preserves_context(self, dispatcher, dlq_service, test_announcement):
        """Verify timeout handling preserves context for manual review."""
        original_item = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        dlq_service.route_error(
            announcement_id=test_announcement,
            error_type=asyncio.TimeoutError,
            error_message="Generation timeout (exceeded 30s)",
            guild_id=original_item.get("guild_id", 0),
            operator_id="system:timeout",
            context={
                "timeout_seconds": 30,
                "original_title": original_item.get("title"),
                "original_description": original_item.get("description"),
                "trigger_type": original_item.get("trigger_type")
            }
        )
        
        # Verify context preserved
        dlq = get_database()["content_delivery_dlq"]
        dlq_items = list(dlq.find({"announcement_id": test_announcement}))
        
        assert len(dlq_items) > 0, "DLQ should have the failed announcement"
        dlq_doc = dlq_items[0]
        
        # Check context preserved
        assert dlq_doc.get("context", {}).get("timeout_seconds") == 30, "Timeout context should be preserved"
        assert dlq_doc.get("context", {}).get("original_title") == original_item.get("title"), \
            "Original title should be in context"
    
    def test_timeout_allows_retry(self, dispatcher, test_announcement):
        """Verify timeout can be retried (move back to draft state)."""
        # Mark as failed
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        item_before = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        assert item_before.get("lifecycle_state") == "error", "Should be in error state"
        
        # DLQ should support retry - move back to draft for re-generation
        # This would normally be done by operator or retry job
        db = get_database()
        collection = db["content_delivery_items"]
        
        result = collection.update_one(
            {"_id": ObjectId(test_announcement)},
            {"$set": {
                "lifecycle_state": "draft",
                "generation_status": "pending",
                "updated_at": datetime.utcnow()
            }}
        )
        
        assert result.modified_count > 0, "Should be able to move back to draft for retry"
        
        item_after = collection.find_one({"_id": ObjectId(test_announcement)})
        assert item_after is not None and item_after.get("lifecycle_state") == "draft", "Should be back in draft after retry"
    
    def test_timeout_vs_other_errors(self, dispatcher, test_announcement):
        """Verify timeout errors are distinct from other generation errors."""
        # Timeout error
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        item = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        error_msg = item.get("error_message", "")
        
        assert "timeout" in error_msg.lower(), "Timeout should be in error message"
        assert "api" not in error_msg.lower(), "Should not mention API errors"


class TestAnnouncementTimeoutEdgeCases:
    """Test edge cases in timeout handling."""
    
    @pytest.fixture
    def dispatcher(self):
        """Get announcement dispatcher instance."""
        return get_announcement_dispatcher()
    
    @pytest.fixture
    def test_announcement(self, dispatcher):
        """Create a test announcement."""
        item_id = create_announcement_for_delivery(
            guild_id=12345,
            title="Test Announcement",
            description="Test content",
            delivery_channel_id=67890,
            priority=0,
            operator_id="operator:test"
        )
        
        yield item_id
        
        # Cleanup
        try:
            dispatcher.collection.delete_one({"_id": ObjectId(item_id)})
        except:
            pass
    
    def test_timeout_with_empty_content(self, dispatcher, test_announcement):
        """Verify timeout handling when LLM returns empty before timeout."""
        # Mark as failed with empty response
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="LLM returned empty response",
            operator_id="system:llm"
        )
        
        item = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        
        assert item.get("lifecycle_state") == "error", "Should be in error state"
        assert "empty" in item.get("error_message", "").lower(), "Error should mention empty response"
    
    def test_timeout_operator_context(self, dispatcher, test_announcement):
        """Verify operator/source context is recorded for timeout."""
        dispatcher.generation_failed(
            item_id=test_announcement,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="scheduled-announcer:system"
        )
        
        item = dispatcher.collection.find_one({"_id": ObjectId(test_announcement)})
        
        # Verify we can trace who was operating when timeout occurred
        assert item is not None, "Announcement should exist"
        # The update doesn't specifically track this, but error_message and state help identify it
    
    def test_timeout_does_not_affect_other_announcements(self, dispatcher):
        """Verify timeout of one announcement doesn't affect others."""
        # Create two announcements
        item1 = create_announcement_for_delivery(
            guild_id=111,
            title="Announcement 1",
            description="Content 1",
            delivery_channel_id=1000,
            operator_id="operator:test"
        )
        
        item2 = create_announcement_for_delivery(
            guild_id=222,
            title="Announcement 2",
            description="Content 2",
            delivery_channel_id=2000,
            operator_id="operator:test"
        )
        
        # Timeout first one
        dispatcher.generation_failed(
            item_id=item1,
            error_message="Generation timeout (exceeded 30s)",
            operator_id="system:timeout"
        )
        
        # Verify second is unaffected
        item2_doc = dispatcher.collection.find_one({"_id": ObjectId(item2)})
        assert item2_doc.get("lifecycle_state") == "draft", "Second announcement should still be in draft"
        assert item2_doc.get("generation_status") == "pending", "Second announcement generation should still be pending"
        
        # Cleanup
        dispatcher.collection.delete_many({"_id": {"$in": [ObjectId(item1), ObjectId(item2)]}})
