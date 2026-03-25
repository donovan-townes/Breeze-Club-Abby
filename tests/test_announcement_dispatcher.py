"""Test suite for AnnouncementDispatcher service (Phase 1).

Tests:
- State transition validation
- Operator audit trail in all operations
- Error handling for invalid transitions
- Concurrent safety (MongoDB updates)
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from bson import ObjectId

from abby_core.services.announcement_dispatcher import (
    AnnouncementDispatcher,
    AnnouncementStateError,
    AnnouncementValidationError,
    get_announcement_dispatcher,
)
from abby_core.services.content_delivery import create_announcement_for_delivery


@pytest.fixture
def dispatcher():
    """Create a fresh dispatcher for testing."""
    return AnnouncementDispatcher()


@pytest.fixture
def mock_db():
    """Mock MongoDB collection for testing."""
    with patch('abby_core.services.announcement_dispatcher.get_content_delivery_collection') as mock:
        yield mock.return_value


class TestAnnouncementDispatcherCreation:
    """Test announcement creation with operator tracking."""
    
    def test_create_announcement_with_operator_id(self, dispatcher, mock_db):
        """Test creating announcement with operator audit trail."""
        # Setup: Use canonical create_announcement_for_delivery() instead of deprecated dispatcher method
        # Note: This tests dispatcher's role in processing, not creation
        # Actual creation is tested via create_announcement_for_delivery in integration tests
        
        item_id = create_announcement_for_delivery(
            guild_id=12345,
            title="Test Announcement",
            description="Test description",
            delivery_channel_id=67890,
            operator_id="user:test_operator"
        )
        
        assert item_id
        # Verify the document was created with operator tracking
        created_item = dispatcher.collection.find_one({"_id": ObjectId(item_id)})
        assert created_item is not None
        assert created_item.get("payload", {}).get("created_by") == "user:test_operator"
    
    def test_create_announcement_defaults_operator_id(self, dispatcher, mock_db):
        """Test that operator_id defaults to 'system' if not provided."""
        # Setup: Use canonical create_announcement_for_delivery() instead of deprecated dispatcher method
        item_id = create_announcement_for_delivery(
            guild_id=12345,
            title="Test",
            description="Test",
            delivery_channel_id=67890,
            # operator_id not provided - should default to 'system'
        )
        
        assert item_id
        # Verify the document was created with default operator tracking
        created_item = dispatcher.collection.find_one({"_id": ObjectId(item_id)})
        assert created_item is not None
        assert created_item.get("payload", {}).get("created_by") == "system"


class TestStateTransitionValidation:
    """Test that invalid state transitions are rejected."""
    
    def test_mark_generated_from_draft_succeeds(self, dispatcher):
        """Test valid transition: draft -> generated."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "draft",
            "generation_status": "pending",
            "guild_id": 12345,
            "title": "Test",
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                result = dispatcher.generate_content(
                    item_id=str(mock_item["_id"]),
                    generated_message="Generated content",
                    operator_id="system:llm"
                )
                assert result is True
    
    def test_mark_generated_from_wrong_state_fails(self, dispatcher):
        """Test that generating from non-draft state raises error."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",  # Already generated!
            "generation_status": "ready",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementStateError) as exc_info:
                dispatcher.generate_content(
                    item_id=str(mock_item["_id"]),
                    generated_message="New message",
                    operator_id="system:llm"
                )
            
            assert "generated" in str(exc_info.value).lower()
            assert "draft" in str(exc_info.value).lower()
    
    def test_mark_delivered_from_queued_succeeds(self, dispatcher):
        """Test valid transition: queued -> delivered."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "delivery_status": "pending",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                result = dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=999,
                    channel_id=777,
                    operator_id="system:discord"
                )
                assert result is True
    
    def test_mark_delivered_from_draft_fails(self, dispatcher):
        """Test that delivering from draft state raises error."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "draft",  # Must be queued first!
            "generation_status": "pending",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementStateError) as exc_info:
                dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=999,
                    channel_id=777,
                    operator_id="system:discord"
                )
            
            assert "queued" in str(exc_info.value).lower()
    
    def test_queue_from_generated_succeeds(self, dispatcher):
        """Test valid transition: generated -> queued."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generation_status": "ready",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                result = dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
                assert result is True


class TestOperatorAuditTrail:
    """Test that operator_id is logged for all operations."""
    
    def test_generation_logs_operator(self, dispatcher, caplog):
        """Test that generate_content logs operator_id."""
        import logging
        
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "draft",
            "generation_status": "pending",
            "guild_id": 12345,
            "title": "Test",
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                with caplog.at_level(logging.INFO):
                    dispatcher.generate_content(
                        item_id=str(mock_item["_id"]),
                        generated_message="Generated",
                        operator_id="user:alice"
                    )
        
        # Should log with operator ID
        logs = [rec.message for rec in caplog.records if "content_generated" in rec.message]
        assert any("user:alice" in log for log in logs), "operator_id should be in logs"
    
    def test_delivery_logs_operator(self, dispatcher, caplog):
        """Test that deliver logs operator_id."""
        import logging
        
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "delivery_status": "pending",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                with caplog.at_level(logging.INFO):
                    dispatcher.deliver(
                        item_id=str(mock_item["_id"]),
                        message_id=999,
                        channel_id=777,
                        operator_id="system:discord"
                    )
        
        logs = [rec.message for rec in caplog.records if "content_delivered" in rec.message]
        assert any("system:discord" in log for log in logs)
    
    def test_failure_logs_operator(self, dispatcher, caplog):
        """Test that generation_failed logs operator_id."""
        import logging
        
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "draft",
            "generation_status": "pending",
            "guild_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                with caplog.at_level(logging.WARNING):
                    dispatcher.generation_failed(
                        item_id=str(mock_item["_id"]),
                        error_message="LLM timeout",
                        operator_id="system:llm"
                    )
        
        logs = [rec.message for rec in caplog.records if "generation_failed" in rec.message.lower()]
        assert any("system:llm" in log for log in logs)


class TestSingletonBehavior:
    """Test dispatcher singleton."""
    
    def test_get_dispatcher_returns_singleton(self):
        """Test that get_announcement_dispatcher returns same instance."""
        disp1 = get_announcement_dispatcher()
        disp2 = get_announcement_dispatcher()
        
        assert disp1 is disp2


class TestErrorHandling:
    """Test error handling for edge cases."""
    
    def test_not_found_item_raises_error(self, dispatcher):
        """Test that querying non-existent item raises error."""
        with patch.object(dispatcher.collection, 'find_one', return_value=None):
            with pytest.raises(AnnouncementStateError) as exc_info:
                dispatcher.generate_content(
                    item_id=str(ObjectId()),
                    generated_message="test",
                    operator_id="test"
                )
            assert "not found" in str(exc_info.value).lower()
    
    def test_invalid_object_id_raises_error(self, dispatcher):
        """Test that invalid ObjectId strings raise error."""
        with pytest.raises(Exception):  # Will fail during ObjectId conversion
            dispatcher.generate_content(
                item_id="not-a-valid-id",
                generated_message="test",
                operator_id="test"
            )


class TestValidTransitions:
    """Test the valid transition matrix."""
    
    def test_draft_to_generated_valid(self, dispatcher):
        """Test VALID_TRANSITIONS includes draft -> generated."""
        assert "generated" in dispatcher.VALID_TRANSITIONS["draft"]
    
    def test_draft_to_delivered_invalid(self, dispatcher):
        """Test VALID_TRANSITIONS does NOT allow draft -> delivered."""
        assert "delivered" not in dispatcher.VALID_TRANSITIONS["draft"]
    
    def test_generated_to_queued_valid(self, dispatcher):
        """Test VALID_TRANSITIONS includes generated -> queued."""
        assert "queued" in dispatcher.VALID_TRANSITIONS["generated"]
    
    def test_queued_to_delivered_valid(self, dispatcher):
        """Test VALID_TRANSITIONS includes queued -> delivered."""
        assert "delivered" in dispatcher.VALID_TRANSITIONS["queued"]
    
    def test_archived_is_terminal(self, dispatcher):
        """Test that archived state has no valid transitions."""
        assert len(dispatcher.VALID_TRANSITIONS["archived"]) == 0


class TestQueueValidation:
    """Test pre-condition validation for queue_for_delivery."""
    
    def test_queue_fails_without_generated_message(self, dispatcher):
        """Test queue_for_delivery fails if message not generated."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": None,  # Missing!
            "delivery_channel_id": 12345,
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
            assert "message not generated" in str(exc_info.value)
    
    def test_queue_fails_without_channel_id(self, dispatcher):
        """Test queue_for_delivery fails if channel not set."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": "Hello world",
            "delivery_channel_id": None,  # Missing!
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
            assert "delivery_channel_id" in str(exc_info.value)
    
    def test_queue_fails_without_guild_id(self, dispatcher):
        """Test queue_for_delivery fails if guild not set."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": "Hello world",
            "delivery_channel_id": 12345,
            "guild_id": None,  # Missing!
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
            assert "guild_id" in str(exc_info.value)
    
    def test_queue_fails_with_empty_message(self, dispatcher):
        """Test queue_for_delivery fails if message is empty/whitespace."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": "   ",  # Whitespace only!
            "delivery_channel_id": 12345,
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
            assert "empty" in str(exc_info.value)
    
    def test_queue_fails_with_message_too_long(self, dispatcher):
        """Test queue_for_delivery fails if message exceeds Discord limit."""
        long_msg = "x" * 2001  # Exceeds Discord 2000 char limit
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": long_msg,
            "delivery_channel_id": 12345,
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
            assert "too long" in str(exc_info.value)
            assert "2000" in str(exc_info.value)
    
    def test_queue_succeeds_with_valid_message(self, dispatcher):
        """Test queue_for_delivery succeeds with all conditions met."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "generated",
            "generated_message": "Valid message content",
            "delivery_channel_id": 12345,
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                result = dispatcher.queue_for_delivery(
                    item_id=str(mock_item["_id"]),
                    operator_id="system:scheduler"
                )
                assert result is True


class TestDeliveryValidation:
    """Test pre-condition validation for deliver."""
    
    def test_deliver_fails_with_invalid_message_id(self, dispatcher):
        """Test deliver fails if message_id is invalid."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "generated_message": "Hello world",
            "delivery_channel_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=0,  # Invalid!
                    channel_id=999,
                    operator_id="system:discord"
                )
            assert "message_id" in str(exc_info.value)
    
    def test_deliver_fails_with_invalid_channel_id(self, dispatcher):
        """Test deliver fails if channel_id is invalid."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "generated_message": "Hello world",
            "delivery_channel_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=555,
                    channel_id=-1,  # Invalid!
                    operator_id="system:discord"
                )
            assert "channel_id" in str(exc_info.value)
    
    def test_deliver_fails_without_configured_channel(self, dispatcher):
        """Test deliver fails if item has no delivery_channel_id."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "generated_message": "Hello world",
            "delivery_channel_id": None,  # Not configured!
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=555,
                    channel_id=999,
                    operator_id="system:discord"
                )
            assert "delivery_channel_id" in str(exc_info.value)
    
    def test_deliver_fails_without_message_content(self, dispatcher):
        """Test deliver fails if message was deleted."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "generated_message": None,  # Was deleted!
            "delivery_channel_id": 12345,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with pytest.raises(AnnouncementValidationError) as exc_info:
                dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=555,
                    channel_id=999,
                    operator_id="system:discord"
                )
            assert "generated_message" in str(exc_info.value)
    
    def test_deliver_succeeds_with_valid_ids(self, dispatcher):
        """Test deliver succeeds with all conditions met."""
        mock_item = {
            "_id": ObjectId(),
            "lifecycle_state": "queued",
            "generated_message": "Hello world",
            "delivery_channel_id": 12345,
            "guild_id": 999,
        }
        
        with patch.object(dispatcher.collection, 'find_one', return_value=mock_item):
            with patch.object(dispatcher.collection, 'update_one', return_value=MagicMock(modified_count=1)):
                result = dispatcher.deliver(
                    item_id=str(mock_item["_id"]),
                    message_id=555,
                    channel_id=999,
                    operator_id="system:discord"
                )
                assert result is True

