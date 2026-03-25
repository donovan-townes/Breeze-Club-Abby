"""Tests for DLQ Service (Phase 4 Week 1)."""

import pytest
from datetime import datetime, timedelta
from bson import ObjectId

from abby_core.services.dlq_service import (
    DLQService,
    DLQStatus,
    DLQErrorCategory,
    get_dlq_service,
)
from abby_core.services.announcement_dispatcher import (
    AnnouncementStateError,
    AnnouncementValidationError,
)


class TestDLQRouting:
    """Test error routing to DLQ."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DLQ service."""
        self.dlq = get_dlq_service()
        # Clear collection
        self.dlq.collection.delete_many({})
    
    def test_route_state_error(self):
        """Routing a state transition error."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Invalid transition: draft → archived",
            guild_id=123,
            operator_id="system:test",
        )
        
        assert dlq_id
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["error_category"] == DLQErrorCategory.STATE_TRANSITION.value
        assert item["status"] == DLQStatus.PENDING.value
        assert item["retry_count"] == 0
    
    def test_route_validation_error(self):
        """Routing a validation error."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementValidationError,
            error_message="Message too long (2500 chars)",
            guild_id=456,
            operator_id="system:test",
        )
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["error_category"] == DLQErrorCategory.VALIDATION.value
        assert item["status"] == DLQStatus.PENDING.value
    
    def test_route_includes_context(self):
        """Routing includes optional context."""
        context = {"source": "cog:announcements", "attempt": 2}
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="State error",
            guild_id=123,
            context=context,
        )
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["context"] == context


class TestDLQRetry:
    """Test retry logic."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DLQ service."""
        self.dlq = get_dlq_service()
        self.dlq.collection.delete_many({})
    
    def test_retry_increments_count(self):
        """Retry increments retry count."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Test error",
            guild_id=123,
        )
        
        result = self.dlq.retry_announcement(dlq_id)
        assert result is True
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["retry_count"] == 1
        assert item["status"] == DLQStatus.RETRYING.value
    
    def test_retry_with_backoff(self):
        """Retry schedules next retry with exponential backoff."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Test error",
            guild_id=123,
        )
        
        before = datetime.utcnow()
        self.dlq.retry_announcement(dlq_id)
        after = datetime.utcnow()
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        next_retry = item["next_retry_at"]
        
        # First backoff is 60 seconds
        assert next_retry >= before + timedelta(seconds=60)
        assert next_retry <= after + timedelta(seconds=70)
    
    def test_retry_respects_max_retries(self):
        """Retry fails when max retries exceeded."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Test error",
            guild_id=123,
        )
        
        # Exhaust retries
        for i in range(self.dlq.MAX_RETRIES):
            result = self.dlq.retry_announcement(dlq_id)
            assert result is True
        
        # Next retry should fail
        result = self.dlq.retry_announcement(dlq_id)
        assert result is False
    
    def test_retry_exponential_backoff(self):
        """Retry backoff increases exponentially."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Test error",
            guild_id=123,
        )
        
        backoffs = []
        
        for _ in range(3):
            before = datetime.utcnow()
            self.dlq.retry_announcement(dlq_id)
            after = datetime.utcnow()
            
            item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
            next_retry = item["next_retry_at"]
            backoff_seconds = (next_retry - before).total_seconds()
            backoffs.append(backoff_seconds)
        
        # Each backoff should be larger than previous
        assert backoffs[0] < backoffs[1]
        assert backoffs[1] < backoffs[2]


class TestDLQResolution:
    """Test DLQ item resolution."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DLQ service."""
        self.dlq = get_dlq_service()
        self.dlq.collection.delete_many({})
    
    def test_resolve_dlq_item(self):
        """Resolving a DLQ item."""
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementValidationError,
            error_message="Message too long",
            guild_id=123,
        )
        
        result = self.dlq.resolve_dlq_item(
            dlq_id,
            resolution="manual_fix",
            operator_id="user:operator1",
        )
        assert result is True
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["status"] == DLQStatus.RESOLVED.value
        assert item["resolution"] == "manual_fix"
        assert item["resolved_by"] == "user:operator1"
        assert "resolved_at" in item


class TestDLQQueries:
    """Test DLQ querying."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DLQ service."""
        self.dlq = get_dlq_service()
        self.dlq.collection.delete_many({})
    
    def test_get_pending_retries(self):
        """Get announcements due for retry."""
        # Create a pending retry item
        dlq_id = self.dlq.route_error(
            announcement_id=str(ObjectId()),
            error_type=AnnouncementStateError,
            error_message="Test error",
            guild_id=123,
        )
        
        self.dlq.retry_announcement(dlq_id)
        
        # Manually set next_retry to past
        self.dlq.collection.update_one(
            {"_id": ObjectId(dlq_id)},
            {"$set": {"next_retry_at": datetime.utcnow() - timedelta(minutes=1)}}
        )
        
        pending = self.dlq.get_pending_retries()
        assert len(pending) == 1
        assert pending[0]["_id"] == ObjectId(dlq_id)
    
    def test_get_dlq_summary(self):
        """Get DLQ summary by status and category."""
        # Create various error types
        for i in range(2):
            self.dlq.route_error(
                announcement_id=str(ObjectId()),
                error_type=AnnouncementStateError,
                error_message="State error",
                guild_id=123,
            )
        
        for i in range(3):
            self.dlq.route_error(
                announcement_id=str(ObjectId()),
                error_type=AnnouncementValidationError,
                error_message="Validation error",
                guild_id=123,
            )
        
        summary = self.dlq.get_dlq_summary()
        assert summary["total"] == 5
        assert summary["by_status"][DLQStatus.PENDING.value] == 5
        assert summary["by_category"][DLQErrorCategory.STATE_TRANSITION.value] == 2
        assert summary["by_category"][DLQErrorCategory.VALIDATION.value] == 3
    
    def test_get_dlq_summary_by_guild(self):
        """Get DLQ summary filtered by guild."""
        # Create errors for different guilds
        for i in range(2):
            self.dlq.route_error(
                announcement_id=str(ObjectId()),
                error_type=AnnouncementStateError,
                error_message="Error",
                guild_id=100,
            )
        
        for i in range(3):
            self.dlq.route_error(
                announcement_id=str(ObjectId()),
                error_type=AnnouncementStateError,
                error_message="Error",
                guild_id=200,
            )
        
        summary_100 = self.dlq.get_dlq_summary(guild_id=100)
        assert summary_100["total"] == 2
        
        summary_200 = self.dlq.get_dlq_summary(guild_id=200)
        assert summary_200["total"] == 3


class TestDLQIntegration:
    """Integration tests for DLQ workflow."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DLQ service."""
        self.dlq = get_dlq_service()
        self.dlq.collection.delete_many({})
    
    def test_complete_dlq_workflow(self):
        """Complete workflow: route → retry → resolve."""
        ann_id = str(ObjectId())
        
        # 1. Route error
        dlq_id = self.dlq.route_error(
            announcement_id=ann_id,
            error_type=AnnouncementStateError,
            error_message="Invalid state",
            guild_id=123,
        )
        
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["status"] == DLQStatus.PENDING.value
        
        # 2. Retry
        self.dlq.retry_announcement(dlq_id)
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["status"] == DLQStatus.RETRYING.value
        assert item["retry_count"] == 1
        
        # 3. Resolve
        self.dlq.resolve_dlq_item(dlq_id, resolution="manual_fix")
        item = self.dlq.collection.find_one({"_id": ObjectId(dlq_id)})
        assert item["status"] == DLQStatus.RESOLVED.value
