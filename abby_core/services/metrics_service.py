"""Metrics Service for announcement lifecycle tracking.

Captures timing data and state transitions for performance analysis.
Enables dashboards, alerts, and bottleneck identification.

**Metrics Tracked:**
- Generation time: from creation to draft→generated
- Queue wait time: from generated to queued
- Delivery time: from queued to delivered
- Total cycle time: creation to archive
- Error rates by category
- Retry rates
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from enum import Enum
import logging

from abby_core.database.mongodb import get_database

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics we track."""
    GENERATION_TIME = "generation_time"
    QUEUE_WAIT_TIME = "queue_wait_time"
    DELIVERY_TIME = "delivery_time"
    TOTAL_CYCLE_TIME = "total_cycle_time"
    ERROR_RATE = "error_rate"
    RETRY_RATE = "retry_rate"


def get_metrics_collection():
    """Return the MongoDB collection for metrics."""
    db = get_database()
    collection = db["content_delivery_metrics"]
    
    # Indexes for efficient querying
    try:
        collection.create_index([("guild_id", 1), ("timestamp", -1)])
        collection.create_index([("metric_type", 1), ("timestamp", -1)])
        collection.create_index([("announcement_id", 1)])
        collection.create_index([("timestamp", -1)])
        # TTL index: auto-delete metrics older than 90 days
        collection.create_index([("timestamp", 1)], expireAfterSeconds=7776000)
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[metrics_service] index creation skipped: {exc}")
    
    return collection


class MetricsService:
    """Tracks announcement lifecycle metrics for performance monitoring."""
    
    def __init__(self):
        self.collection = get_metrics_collection()
    
    def record_transition(
        self,
        announcement_id: str,
        from_state: str,
        to_state: str,
        guild_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a state transition.
        
        Args:
            announcement_id: Announcement ID
            from_state: Previous state
            to_state: New state
            guild_id: Guild ID
            metadata: Additional data (message length, etc.)
        
        Returns:
            Metric ID
        """
        metadata = metadata or {}
        now = datetime.utcnow()
        
        metric = {
            "announcement_id": ObjectId(announcement_id) if isinstance(announcement_id, str) else announcement_id,
            "guild_id": guild_id,
            "transition": f"{from_state}→{to_state}",
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": now,
            "metadata": metadata,
        }
        
        result = self.collection.insert_one(metric)
        metric_id = str(result.inserted_id)
        
        logger.debug(
            f"[📊 metrics] TRANSITION "
            f"announcement_id={announcement_id[:8]}... "
            f"transition={from_state}→{to_state} "
            f"guild={guild_id}"
        )
        
        return metric_id
    
    def record_timing(
        self,
        announcement_id: str,
        metric_type: str,
        duration_seconds: float,
        guild_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record timing for a lifecycle phase.
        
        Args:
            announcement_id: Announcement ID
            metric_type: Type of timing (generation_time, queue_wait_time, etc.)
            duration_seconds: Duration in seconds
            guild_id: Guild ID
            metadata: Additional context
        
        Returns:
            Metric ID
        """
        metadata = metadata or {}
        now = datetime.utcnow()
        
        # Categorize as slow/normal/fast
        speed = _categorize_speed(metric_type, duration_seconds)
        
        metric = {
            "announcement_id": ObjectId(announcement_id) if isinstance(announcement_id, str) else announcement_id,
            "guild_id": guild_id,
            "metric_type": metric_type,
            "duration_seconds": duration_seconds,
            "speed_category": speed,
            "timestamp": now,
            "metadata": metadata,
        }
        
        result = self.collection.insert_one(metric)
        metric_id = str(result.inserted_id)
        
        logger.debug(
            f"[⏱️ metrics] TIMING "
            f"announcement_id={announcement_id[:8]}... "
            f"metric={metric_type} "
            f"duration={duration_seconds:.2f}s "
            f"speed={speed}"
        )
        
        return metric_id
    
    def record_error(
        self,
        announcement_id: str,
        error_category: str,
        error_type: str,
        guild_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an error occurrence.
        
        Args:
            announcement_id: Announcement ID
            error_category: Category (state_transition, validation, etc.)
            error_type: Exception type
            guild_id: Guild ID
            metadata: Additional context
        
        Returns:
            Metric ID
        """
        metadata = metadata or {}
        now = datetime.utcnow()
        
        metric = {
            "announcement_id": ObjectId(announcement_id) if isinstance(announcement_id, str) else announcement_id,
            "guild_id": guild_id,
            "metric_type": "error",
            "error_category": error_category,
            "error_type": error_type,
            "timestamp": now,
            "metadata": metadata,
        }
        
        result = self.collection.insert_one(metric)
        metric_id = str(result.inserted_id)
        
        logger.debug(
            f"[📊 metrics] ERROR "
            f"announcement_id={announcement_id[:8]}... "
            f"category={error_category} "
            f"type={error_type}"
        )
        
        return metric_id
    
    def get_performance_stats(
        self,
        guild_id: Optional[int] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get performance statistics for a time window.
        
        Args:
            guild_id: Optional guild filter
            hours: Hours back to analyze
        
        Returns:
            Performance statistics
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        match: Dict[str, Any] = {"timestamp": {"$gte": since}}
        
        if guild_id:
            match["guild_id"] = guild_id
        
        # Timing metrics
        timing_pipeline = [
            {"$match": {**match, "metric_type": {"$in": [
                "generation_time", "queue_wait_time", "delivery_time", "total_cycle_time"
            ]}}},
            {"$group": {
                "_id": "$metric_type",
                "avg_duration": {"$avg": "$duration_seconds"},
                "min_duration": {"$min": "$duration_seconds"},
                "max_duration": {"$max": "$duration_seconds"},
                "count": {"$sum": 1}
            }}
        ]
        
        timing_results = list(self.collection.aggregate(timing_pipeline))
        
        # Error rates
        error_pipeline = [
            {"$match": {**match, "metric_type": "error"}},
            {"$group": {
                "_id": "$error_category",
                "count": {"$sum": 1}
            }}
        ]
        
        error_results = list(self.collection.aggregate(error_pipeline))
        
        # Build timing stats with explicit type casting
        timing_stats: Dict[str, Any] = {}
        for r in timing_results:
            timing_stats[r["_id"]] = {
                "avg_seconds": r["avg_duration"],
                "min_seconds": r["min_duration"],
                "max_seconds": r["max_duration"],
                "count": int(r["count"])
            }
        
        # Build error stats with explicit type casting
        error_stats: Dict[str, int] = {}
        for r in error_results:
            error_stats[r["_id"]] = int(r["count"])
        
        stats: Dict[str, Any] = {
            "period_hours": hours,
            "timing": timing_stats,
            "errors": error_stats,
        }
        
        return stats
    
    def get_slowest_announcements(
        self,
        guild_id: Optional[int] = None,
        metric_type: str = "total_cycle_time",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get slowest announcements by a metric.
        
        Args:
            guild_id: Optional guild filter
            metric_type: Which timing metric to use
            limit: Maximum results
        
        Returns:
            List of slow announcements
        """
        match: Dict[str, Any] = {"metric_type": metric_type}
        if guild_id:
            match["guild_id"] = guild_id
        
        return list(self.collection.find(match)
                   .sort("duration_seconds", -1)
                   .limit(limit))
    
    def get_error_trend(
        self,
        guild_id: Optional[int] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get error trend over time.
        
        Args:
            guild_id: Optional guild filter
            hours: Hours back to analyze
        
        Returns:
            Error trend data
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        match = {"timestamp": {"$gte": since}, "metric_type": "error"}
        
        if guild_id:
            match["guild_id"] = guild_id
        
        # Group by error category and hour
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": {
                    "category": "$error_category",
                    "hour": {
                        "$dateToString": {
                            "format": "%Y-%m-%dT%H:00:00Z",
                            "date": "$timestamp"
                        }
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.hour": 1}}
        ]
        
        results = list(self.collection.aggregate(pipeline))
        
        trend: Dict[str, Any] = {
            "period_hours": hours,
            "by_hour": {}
        }
        
        for result in results:
            hour = result["_id"]["hour"]
            category = result["_id"]["category"]
            count = int(result["count"])
            
            if hour not in trend["by_hour"]:
                trend["by_hour"][hour] = {}
            
            trend["by_hour"][hour][category] = count
        
        return trend


def _categorize_speed(metric_type: str, duration_seconds: float) -> str:
    """Categorize timing as slow/normal/fast."""
    # Thresholds (in seconds)
    thresholds = {
        "generation_time": {"normal": 30, "slow": 60},
        "queue_wait_time": {"normal": 5, "slow": 30},
        "delivery_time": {"normal": 5, "slow": 30},
        "total_cycle_time": {"normal": 60, "slow": 300},
    }
    
    if metric_type not in thresholds:
        return "unknown"
    
    t = thresholds[metric_type]
    if duration_seconds <= t["normal"]:
        return "fast"
    elif duration_seconds <= t["slow"]:
        return "normal"
    else:
        return "slow"


# Singleton instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """Get or create the metrics service."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


def get_unified_announcement_metrics(announcement_id: str) -> Dict[str, Any]:
    """Get all metrics for an announcement across all services (unified query).
    
    **Responsibility:** Aggregate metrics from both content delivery and LLM generation.
    
    Provides a single query interface to fetch:
    - Delivery lifecycle metrics (times, transitions, errors)
    - Generation metrics (token usage, costs, latency)
    
    **Use Case:** Operators need quick visibility into announcement performance.
    Instead of querying two services separately, this provides unified results.
    
    **Returns:**
    ```python
    {
        "announcement_id": "507f1f77bcf86cd799439011",
        "delivery": {
            "transitions": [
                {"from": "draft", "to": "generated", "timestamp": "2026-01-15T10:30:00Z"},
                ...
            ],
            "timings": {
                "generation_time_sec": 2.5,
                "queue_wait_time_sec": 1.2,
                "delivery_time_sec": 0.8,
                "total_cycle_time_sec": 4.5,
            },
            "errors": None,
        },
        "generation": {
            "provider": "openai",
            "model": "gpt-4-turbo",
            "tokens": {"input": 150, "output": 80, "total": 230},
            "cost_usd": 0.0035,
            "latency_ms": 2500,
            "success": True,
        }
    }
    ```
    
    Args:
        announcement_id: ObjectId of announcement to query
    
    Returns:
        Dict with 'delivery' and 'generation' sub-keys containing all metrics
    """
    from bson import ObjectId
    from abby_core.services.generation_audit_service import get_generation_audit_service
    
    # Coerce to ObjectId if needed
    try:
        if isinstance(announcement_id, str):
            obj_id = ObjectId(announcement_id)
        else:
            obj_id = announcement_id
    except Exception:
        return {
            "announcement_id": announcement_id,
            "error": "Invalid announcement_id format",
            "delivery": {},
            "generation": {},
        }
    
    # ===== Delivery Metrics =====
    delivery_metrics = {}
    try:
        metrics_service = get_metrics_service()
        collection = metrics_service.collection
        
        # Get all metrics for this announcement
        metrics_docs = list(collection.find({"announcement_id": obj_id}))
        
        # Extract transitions (state changes)
        transitions = [
            {
                "from": m.get("from_state"),
                "to": m.get("to_state"),
                "timestamp": m.get("timestamp"),
            }
            for m in metrics_docs
            if m.get("transition")
        ]
        
        # Extract timings
        timings = {}
        for m in metrics_docs:
            metric_type = m.get("metric_type")
            if metric_type:
                timings[f"{metric_type}_sec"] = m.get("duration_seconds", 0)
        
        # Calculate total cycle time if not explicitly recorded
        if transitions:
            first_transition = transitions[0]
            last_transition = transitions[-1]
            if first_transition.get("timestamp") and last_transition.get("timestamp"):
                cycle_time = (
                    last_transition.get("timestamp") - first_transition.get("timestamp")
                ).total_seconds()
                timings["total_cycle_time_sec"] = cycle_time
        
        # Check for errors
        errors = [
            {
                "metric_type": m.get("metric_type"),
                "error": m.get("metadata", {}).get("error"),
                "timestamp": m.get("timestamp"),
            }
            for m in metrics_docs
            if m.get("metadata", {}).get("error")
        ]
        
        delivery_metrics = {
            "transitions": transitions,
            "timings": timings,
            "errors": errors if errors else None,
            "metric_count": len(metrics_docs),
        }
    except Exception as e:
        logger.warning(
            f"[⚠️] Failed to fetch delivery metrics for {announcement_id}: {e}"
        )
        delivery_metrics = {"error": str(e)}
    
    # ===== Generation Metrics =====
    generation_metrics = {}
    try:
        generation_service = get_generation_audit_service()
        collection = generation_service._get_collection()
        
        # Find generation records for this announcement (if tracked)
        # Assuming generation audit stores announcement_id or session_id
        gen_docs = list(
            collection.find({"announcement_id": announcement_id}).limit(10)
        )
        
        if gen_docs:
            # Aggregate across all generation calls for this announcement
            total_input_tokens = sum(d.get("input_tokens", 0) for d in gen_docs)
            total_output_tokens = sum(d.get("output_tokens", 0) for d in gen_docs)
            total_cost = sum(d.get("total_cost_usd", 0) for d in gen_docs)
            avg_latency = sum(d.get("latency_ms", 0) for d in gen_docs) / len(gen_docs)
            
            # Count successes vs failures
            successes = sum(1 for d in gen_docs if d.get("success", True))
            failures = len(gen_docs) - successes
            
            generation_metrics = {
                "call_count": len(gen_docs),
                "provider": gen_docs[0].get("provider", "unknown"),
                "model": gen_docs[0].get("model", "unknown"),
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens,
                },
                "cost_usd": round(total_cost, 6),
                "avg_latency_ms": round(avg_latency, 2),
                "success_rate": round(successes / len(gen_docs) * 100, 1) if gen_docs else 0,
            }
        else:
            generation_metrics = {"call_count": 0, "note": "No generation records found"}
    except Exception as e:
        logger.warning(
            f"[⚠️] Failed to fetch generation metrics for {announcement_id}: {e}"
        )
        generation_metrics = {"error": str(e)}
    
    # ===== Return Unified Result =====
    return {
        "announcement_id": str(obj_id),
        "queried_at": datetime.utcnow(),
        "delivery": delivery_metrics,
        "generation": generation_metrics,
    }
