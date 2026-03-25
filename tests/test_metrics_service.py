"""Tests for Metrics Service (Phase 4 Week 1)."""

import pytest
from datetime import datetime, timedelta
from bson import ObjectId

from abby_core.services.metrics_service import (
    MetricsService,
    MetricType,
    get_metrics_service,
)


class TestMetricsTransitions:
    """Test state transition recording."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset metrics service."""
        self.metrics = get_metrics_service()
        self.metrics.collection.delete_many({})
    
    def test_record_transition(self):
        """Record a state transition."""
        ann_id = str(ObjectId())
        metric_id = self.metrics.record_transition(
            announcement_id=ann_id,
            from_state="draft",
            to_state="generated",
            guild_id=123,
        )
        
        assert metric_id
        item = self.metrics.collection.find_one({"_id": ObjectId(metric_id)})
        assert item["from_state"] == "draft"
        assert item["to_state"] == "generated"
        assert item["transition"] == "draft→generated"
        assert item["guild_id"] == 123
    
    def test_transition_with_metadata(self):
        """Record transition with metadata."""
        ann_id = str(ObjectId())
        metadata = {"message_length": 150, "channel_id": 456}
        
        self.metrics.record_transition(
            announcement_id=ann_id,
            from_state="generated",
            to_state="queued",
            guild_id=123,
            metadata=metadata,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metadata"] == metadata


class TestMetricsTiming:
    """Test timing metric recording."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset metrics service."""
        self.metrics = get_metrics_service()
        self.metrics.collection.delete_many({})
    
    def test_record_generation_time(self):
        """Record generation time (fast)."""
        ann_id = str(ObjectId())
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="generation_time",
            duration_seconds=10.5,
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metric_type"] == "generation_time"
        assert item["duration_seconds"] == 10.5
        assert item["speed_category"] == "fast"
    
    def test_record_queue_wait_time(self):
        """Record queue wait time (normal)."""
        ann_id = str(ObjectId())
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="queue_wait_time",
            duration_seconds=10.0,
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["speed_category"] == "normal"
    
    def test_record_delivery_time(self):
        """Record delivery time (slow)."""
        ann_id = str(ObjectId())
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="delivery_time",
            duration_seconds=45.0,
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["speed_category"] == "slow"
    
    def test_record_total_cycle_time(self):
        """Record total cycle time."""
        ann_id = str(ObjectId())
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="total_cycle_time",
            duration_seconds=120.0,
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metric_type"] == "total_cycle_time"
        assert item["duration_seconds"] == 120.0
    
    def test_timing_with_metadata(self):
        """Record timing with metadata."""
        ann_id = str(ObjectId())
        metadata = {"retry_count": 2, "llm_model": "gpt-3.5"}
        
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="generation_time",
            duration_seconds=25.0,
            guild_id=123,
            metadata=metadata,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metadata"] == metadata


class TestMetricsErrors:
    """Test error recording."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset metrics service."""
        self.metrics = get_metrics_service()
        self.metrics.collection.delete_many({})
    
    def test_record_state_error(self):
        """Record a state transition error."""
        ann_id = str(ObjectId())
        self.metrics.record_error(
            announcement_id=ann_id,
            error_category="state_transition",
            error_type="AnnouncementStateError",
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metric_type"] == "error"
        assert item["error_category"] == "state_transition"
        assert item["error_type"] == "AnnouncementStateError"
    
    def test_record_validation_error(self):
        """Record a validation error."""
        ann_id = str(ObjectId())
        self.metrics.record_error(
            announcement_id=ann_id,
            error_category="validation",
            error_type="AnnouncementValidationError",
            guild_id=123,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["error_category"] == "validation"
    
    def test_error_with_metadata(self):
        """Record error with metadata."""
        ann_id = str(ObjectId())
        metadata = {"field": "message_length", "constraint": "< 2000"}
        
        self.metrics.record_error(
            announcement_id=ann_id,
            error_category="validation",
            error_type="AnnouncementValidationError",
            guild_id=123,
            metadata=metadata,
        )
        
        item = self.metrics.collection.find_one({"guild_id": 123})
        assert item["metadata"] == metadata


class TestMetricsQueries:
    """Test metrics querying and aggregation."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset metrics service."""
        self.metrics = get_metrics_service()
        self.metrics.collection.delete_many({})
    
    def test_get_performance_stats(self):
        """Get performance statistics."""
        # Record various timings
        for i in range(3):
            self.metrics.record_timing(
                announcement_id=str(ObjectId()),
                metric_type="generation_time",
                duration_seconds=10.0 + i,
                guild_id=123,
            )
        
        stats = self.metrics.get_performance_stats()
        
        assert "generation_time" in stats["timing"]
        timing = stats["timing"]["generation_time"]
        assert timing["count"] == 3
        assert timing["avg_seconds"] == pytest.approx(11.0)
        assert timing["min_seconds"] == 10.0
        assert timing["max_seconds"] == 12.0
    
    def test_performance_stats_by_guild(self):
        """Filter performance stats by guild."""
        # Record for different guilds
        for i in range(2):
            self.metrics.record_timing(
                announcement_id=str(ObjectId()),
                metric_type="generation_time",
                duration_seconds=10.0,
                guild_id=100,
            )
        
        for i in range(3):
            self.metrics.record_timing(
                announcement_id=str(ObjectId()),
                metric_type="generation_time",
                duration_seconds=15.0,
                guild_id=200,
            )
        
        stats_100 = self.metrics.get_performance_stats(guild_id=100)
        assert stats_100["timing"]["generation_time"]["count"] == 2
        
        stats_200 = self.metrics.get_performance_stats(guild_id=200)
        assert stats_200["timing"]["generation_time"]["count"] == 3
    
    def test_error_statistics(self):
        """Get error statistics in performance stats."""
        self.metrics.record_error(
            announcement_id=str(ObjectId()),
            error_category="state_transition",
            error_type="AnnouncementStateError",
            guild_id=123,
        )
        
        for i in range(2):
            self.metrics.record_error(
                announcement_id=str(ObjectId()),
                error_category="validation",
                error_type="AnnouncementValidationError",
                guild_id=123,
            )
        
        stats = self.metrics.get_performance_stats()
        
        assert stats["errors"]["state_transition"] == 1
        assert stats["errors"]["validation"] == 2
    
    def test_get_slowest_announcements(self):
        """Get slowest announcements."""
        # Record various timings
        timings = [120.0, 45.0, 200.0, 30.0, 90.0]
        for duration in timings:
            self.metrics.record_timing(
                announcement_id=str(ObjectId()),
                metric_type="total_cycle_time",
                duration_seconds=duration,
                guild_id=123,
            )
        
        slowest = self.metrics.get_slowest_announcements(
            metric_type="total_cycle_time",
            limit=3
        )
        
        assert len(slowest) == 3
        assert slowest[0]["duration_seconds"] == 200.0
        assert slowest[1]["duration_seconds"] == 120.0
        assert slowest[2]["duration_seconds"] == 90.0
    
    def test_get_error_trend(self):
        """Get error trend over time."""
        now = datetime.utcnow()
        
        # Create errors at different times
        for hour in range(3):
            timestamp = now - timedelta(hours=hour)
            self.metrics.collection.insert_one({
                "announcement_id": ObjectId(),
                "guild_id": 123,
                "metric_type": "error",
                "error_category": "state_transition",
                "error_type": "AnnouncementStateError",
                "timestamp": timestamp,
            })
        
        trend = self.metrics.get_error_trend(guild_id=123, hours=24)
        
        assert trend["period_hours"] == 24
        assert "by_hour" in trend
        assert len(trend["by_hour"]) > 0


class TestMetricsIntegration:
    """Integration tests for metrics workflow."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset metrics service."""
        self.metrics = get_metrics_service()
        self.metrics.collection.delete_many({})
    
    def test_complete_announcement_lifecycle_metrics(self):
        """Track metrics through complete announcement lifecycle."""
        ann_id = str(ObjectId())
        guild_id = 123
        
        # 1. Create → Generate
        self.metrics.record_transition(
            announcement_id=ann_id,
            from_state="draft",
            to_state="generated",
            guild_id=guild_id,
        )
        
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="generation_time",
            duration_seconds=15.0,
            guild_id=guild_id,
            metadata={"llm_model": "gpt-3.5", "tokens": 150}
        )
        
        # 2. Generate → Queue
        self.metrics.record_transition(
            announcement_id=ann_id,
            from_state="generated",
            to_state="queued",
            guild_id=guild_id,
            metadata={"queue_position": 5}
        )
        
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="queue_wait_time",
            duration_seconds=3.0,
            guild_id=guild_id,
        )
        
        # 3. Queue → Delivered
        self.metrics.record_transition(
            announcement_id=ann_id,
            from_state="queued",
            to_state="delivered",
            guild_id=guild_id,
        )
        
        self.metrics.record_timing(
            announcement_id=ann_id,
            metric_type="delivery_time",
            duration_seconds=2.0,
            guild_id=guild_id,
            metadata={"message_id": 999, "channel_id": 888}
        )
        
        # 4. Verify all metrics recorded
        all_metrics = list(self.metrics.collection.find(
            {"announcement_id": ObjectId(ann_id)}
        ))
        
        transitions = [m for m in all_metrics if "transition" in m]
        timings = [m for m in all_metrics if "metric_type" in m and m.get("duration_seconds")]
        
        assert len(transitions) == 3  # Three transitions
        assert len(timings) == 3  # Three timing measurements
