"""Test DLQ integration with AnnouncementDispatcher.

Verifies that errors during state transitions are automatically routed to the DLQ.
"""

import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId

from abby_core.services.announcement_dispatcher import (
    AnnouncementDispatcher,
    AnnouncementStateError,
    AnnouncementValidationError,
)
from abby_core.services.dlq_service import DLQService, DLQErrorCategory


class TestDLQIntegrationWithDispatcher:
    """Test that dispatcher errors are automatically routed to DLQ."""
    
    def test_state_transition_error_routes_to_dlq(self):
        """Test that state transition errors trigger DLQ route_error."""
        with patch('abby_core.services.announcement_dispatcher.get_content_delivery_collection') as mock_coll_fn, \
             patch('abby_core.services.announcement_dispatcher.get_dlq_service') as mock_dlq_fn:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_coll_fn.return_value = mock_db
            
            mock_dlq = MagicMock(spec=DLQService)
            mock_dlq.route_error = MagicMock(return_value=str(ObjectId()))
            mock_dlq_fn.return_value = mock_dlq
            
            item_id = str(ObjectId())
            mock_db.find_one.return_value = {
                "_id": ObjectId(item_id),
                "lifecycle_state": "generated",  # Wrong state for generate_content
                "guild_id": 12345,
            }
            
            dispatcher = AnnouncementDispatcher()
            
            # Attempt to generate content when already generated (invalid state transition)
            with pytest.raises(AnnouncementStateError):
                dispatcher.generate_content(
                    item_id=item_id,
                    generated_message="Test message",
                    operator_id="test:operator"
                )
            
            # Verify DLQ service route_error was called
            assert mock_dlq.route_error.called
            call_kwargs = mock_dlq.route_error.call_args[1]
            assert call_kwargs["error_type"] == AnnouncementStateError
            assert call_kwargs["guild_id"] == 12345
            assert call_kwargs["context"]["operation"] == "generate_content"
    
    def test_validation_error_routes_to_dlq(self):
        """Test that validation errors trigger DLQ route_error."""
        with patch('abby_core.services.announcement_dispatcher.get_content_delivery_collection') as mock_coll_fn, \
             patch('abby_core.services.announcement_dispatcher.get_dlq_service') as mock_dlq_fn:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_coll_fn.return_value = mock_db
            
            mock_dlq = MagicMock(spec=DLQService)
            mock_dlq.route_error = MagicMock(return_value=str(ObjectId()))
            mock_dlq_fn.return_value = mock_dlq
            
            item_id = str(ObjectId())
            mock_db.find_one.return_value = {
                "_id": ObjectId(item_id),
                "lifecycle_state": "generated",
                "guild_id": 12345,
                # Missing generated_message - will cause validation error
            }
            
            dispatcher = AnnouncementDispatcher()
            
            # Attempt to queue without generated message
            with pytest.raises(AnnouncementValidationError):
                dispatcher.queue_for_delivery(
                    item_id=item_id,
                    operator_id="test:operator"
                )
            
            # Verify DLQ route_error was called
            assert mock_dlq.route_error.called
            call_kwargs = mock_dlq.route_error.call_args[1]
            assert call_kwargs["error_type"] == AnnouncementValidationError
            assert "message not generated" in call_kwargs["error_message"]
            assert call_kwargs["context"]["operation"] == "queue_for_delivery"
    
    def test_deliver_validation_error_routes_to_dlq(self):
        """Test that deliver validation errors trigger DLQ route_error."""
        with patch('abby_core.services.announcement_dispatcher.get_content_delivery_collection') as mock_coll_fn, \
             patch('abby_core.services.announcement_dispatcher.get_dlq_service') as mock_dlq_fn:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_coll_fn.return_value = mock_db
            
            mock_dlq = MagicMock(spec=DLQService)
            mock_dlq.route_error = MagicMock(return_value=str(ObjectId()))
            mock_dlq_fn.return_value = mock_dlq
            
            item_id = str(ObjectId())
            mock_db.find_one.return_value = {
                "_id": ObjectId(item_id),
                "lifecycle_state": "queued",
                "guild_id": 12345,
                "generated_message": "Test message",
                # Missing delivery_channel_id
            }
            
            dispatcher = AnnouncementDispatcher()
            
            # Attempt to deliver without channel configured
            with pytest.raises(AnnouncementValidationError):
                dispatcher.deliver(
                    item_id=item_id,
                    message_id=987654321,
                    channel_id=123456789,
                    operator_id="test:operator"
                )
            
            # Verify DLQ route_error was called with correct operation context
            assert mock_dlq.route_error.called
            call_kwargs = mock_dlq.route_error.call_args[1]
            assert call_kwargs["context"]["operation"] == "deliver"
            assert call_kwargs["context"]["message_id"] == 987654321
    
    def test_dlq_context_includes_operation_details(self):
        """Test that DLQ context includes operation-specific details."""
        with patch('abby_core.services.announcement_dispatcher.get_content_delivery_collection') as mock_coll_fn, \
             patch('abby_core.services.announcement_dispatcher.get_dlq_service') as mock_dlq_fn:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_coll_fn.return_value = mock_db
            
            mock_dlq = MagicMock(spec=DLQService)
            mock_dlq.route_error = MagicMock(return_value=str(ObjectId()))
            mock_dlq_fn.return_value = mock_dlq
            
            item_id = str(ObjectId())
            mock_db.find_one.return_value = {
                "_id": ObjectId(item_id),
                "lifecycle_state": "generated",
                "guild_id": 12345,
                "generated_message": "x" * 2001,  # Too long
                "delivery_channel_id": 987654321,
            }
            
            dispatcher = AnnouncementDispatcher()
            
            # Attempt to queue with message too long
            with pytest.raises(AnnouncementValidationError):
                dispatcher.queue_for_delivery(
                    item_id=item_id,
                    operator_id="test:operator"
                )
            
            # Verify DLQ context includes operation details
            assert mock_dlq.route_error.called
            call_kwargs = mock_dlq.route_error.call_args[1]
            assert call_kwargs["context"]["operation"] == "queue_for_delivery"
            assert call_kwargs["context"]["channel_id"] == 987654321
            assert call_kwargs["operator_id"] == "test:operator"

