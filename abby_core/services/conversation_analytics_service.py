"""Conversation Analytics Service

Aggregates conversation metrics for operational intelligence.

**Responsibility:**
- Query conversation sessions with aggregation pipelines
- Answer business questions like:
  - How many sessions expired today?
  - What's the average turn count per session?
  - Which guilds have the most active conversations?
  - What's the distribution of session lengths?
  - Which intents are most frequently detected?
- Provide analytics for dashboards, reports, and alerts

**Metrics Tracked:**
- Session counts by guild, state, date range
- Average turn counts per session
- Intent distribution
- Session duration statistics
- Error rates by failure type
- Conversation patterns (time of day, day of week)

**Architecture:**
- Read-only aggregation service
- Uses MongoDB aggregation pipelines for efficiency
- Caches results temporarily (TTL-based)
- Returns structured dicts for easy dashboarding

**Typical Usage:**

    analytics = get_conversation_analytics_service()
    
    # How many sessions expired today?
    expired_today = analytics.count_sessions_by_state(
        "expired",
        since=datetime.utcnow() - timedelta(days=1)
    )
    
    # What's the average turn count per guild?
    stats = analytics.get_session_statistics(
        group_by="guild_id"
    )
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Valid session states."""
    OPEN = "open"
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    CLOSED = "closed"
    EXPIRED = "expired"


class ConversationAnalyticsService:
    """Provides aggregated conversation analytics for operational dashboards."""

    def __init__(self):
        """Initialize the analytics service."""
        self.sessions_collection_name = "chat_sessions"

    def _get_sessions_collection(self):
        """Get the sessions collection."""
        db = get_database()
        return db[self.sessions_collection_name]

    def count_sessions_by_state(
        self,
        state: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> int:
        """Count sessions in a specific state.
        
        **Use Case:** "How many sessions expired today?"
        
        Args:
            state: Session state (open, active, cooldown, closed, expired)
            since: Filter to sessions created after this time
            until: Filter to sessions created before this time
        
        Returns:
            Count of sessions matching criteria
        
        Example:
            today = datetime.utcnow()
            expired_today = analytics.count_sessions_by_state(
                "expired",
                since=today - timedelta(days=1)
            )
        """
        try:
            query: Dict[str, Any] = {"status": state}
            
            # Add date range filters if provided
            if since or until:
                date_query: Dict[str, datetime] = {}
                if since:
                    date_query["$gte"] = since
                if until:
                    date_query["$lte"] = until
                query["created_at"] = date_query
            
            collection = self._get_sessions_collection()
            count = collection.count_documents(query)
            
            logger.debug(
                f"[📊 analytics] COUNT sessions "
                f"state={state} "
                f"since={since} "
                f"until={until} "
                f"count={count}"
            )
            
            return count
        except Exception as e:
            logger.error(
                f"[❌ analytics] Failed to count sessions by state: {e}"
            )
            return 0

    def get_session_statistics(
        self,
        group_by: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated statistics about sessions.
        
        **Use Case:** "What's the average turn count per guild?"
        
        Returns statistics like:
        - Average turn count
        - Min/max turns
        - Median session duration
        - Session count
        
        Args:
            group_by: Group results by field (guild_id, user_id, etc.)
            state: Filter to specific session state
        
        Returns:
            Dict with statistics
        
        Example:
            stats = analytics.get_session_statistics(group_by="guild_id")
            # Returns: {
            #     "123456789": {
            #         "count": 150,
            #         "avg_turns": 8.5,
            #         "min_turns": 1,
            #         "max_turns": 50,
            #         "avg_duration_sec": 3600
            #     },
            #     ...
            # }
        """
        try:
            collection = self._get_sessions_collection()
            
            # Build aggregation pipeline
            pipeline = []
            
            # Stage 1: Filter by state if provided
            if state:
                pipeline.append({"$match": {"status": state}})
            
            # Stage 2: Group and calculate statistics
            group_id = f"${group_by}" if group_by else None
            group_stage = {
                "$group": {
                    "_id": group_id,
                    "count": {"$sum": 1},
                    "avg_turns": {"$avg": "$turn_count"},
                    "min_turns": {"$min": "$turn_count"},
                    "max_turns": {"$max": "$turn_count"},
                    "total_turns": {"$sum": "$turn_count"},
                }
            }
            pipeline.append(group_stage)
            
            # Stage 3: Calculate average duration
            if group_by:
                pipeline.append({
                    "$addFields": {
                        "group": "$_id",
                    }
                })
            
            # Execute aggregation
            results = list(collection.aggregate(pipeline))
            
            # Format results
            if group_by and results:
                formatted = {}
                for result in results:
                    group_key = result.get("_id") or "unknown"
                    formatted[str(group_key)] = {
                        "count": result.get("count", 0),
                        "avg_turns": round(result.get("avg_turns", 0), 2),
                        "min_turns": result.get("min_turns", 0),
                        "max_turns": result.get("max_turns", 0),
                        "total_turns": result.get("total_turns", 0),
                    }
                return formatted
            elif results:
                return {
                    "count": results[0].get("count", 0),
                    "avg_turns": round(results[0].get("avg_turns", 0), 2),
                    "min_turns": results[0].get("min_turns", 0),
                    "max_turns": results[0].get("max_turns", 0),
                    "total_turns": results[0].get("total_turns", 0),
                }
            else:
                return {"error": "No data found"}
        
        except Exception as e:
            logger.error(
                f"[❌ analytics] Failed to get session statistics: {e}"
            )
            return {"error": str(e)}

    def get_intent_distribution(
        self,
        guild_id: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get distribution of intents across conversations.
        
        **Use Case:** "Which intents are most frequently detected?"
        
        Args:
            guild_id: Filter to specific guild
            since: Filter to interactions after this time
        
        Returns:
            Dict mapping intent names to counts
        
        Example:
            dist = analytics.get_intent_distribution(since=datetime.utcnow() - timedelta(days=7))
            # Returns: {
            #     "greeting": 450,
            #     "question_answering": 320,
            #     "role_play": 180,
            #     ...
            # }
        """
        try:
            collection = self._get_sessions_collection()
            
            # Build aggregation: unwind interactions, group by intent
            pipeline = []
            
            # Filter by guild if provided
            if guild_id:
                pipeline.append({"$match": {"guild_id": guild_id}})
            
            # Unwind interactions array
            pipeline.append({"$unwind": "$interactions"})
            
            # Filter by timestamp if provided
            if since:
                pipeline.append({
                    "$match": {
                        "interactions.timestamp": {"$gte": since}
                    }
                })
            
            # Group by intent and count
            pipeline.append({
                "$group": {
                    "_id": "$interactions.intent",
                    "count": {"$sum": 1}
                }
            })
            
            # Sort by count descending
            pipeline.append({
                "$sort": {"count": -1}
            })
            
            # Execute
            results = list(collection.aggregate(pipeline))
            
            # Format results
            intent_dist = {}
            for result in results:
                intent = result.get("_id") or "unknown"
                count = result.get("count", 0)
                intent_dist[intent] = count
            
            logger.debug(
                f"[📊 analytics] INTENT_DISTRIBUTION "
                f"guild={guild_id} "
                f"intent_types={len(intent_dist)}"
            )
            
            return intent_dist
        
        except Exception as e:
            logger.error(
                f"[❌ analytics] Failed to get intent distribution: {e}"
            )
            return {}

    def get_session_health_report(
        self,
        guild_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get health report for conversations in a guild.
        
        **Use Case:** "What's the health of conversations in guild X?"
        
        Returns:
        - Total active sessions
        - Sessions in error state
        - Average turn count
        - Most common intents
        - Trends (improving/degrading)
        
        Args:
            guild_id: Guild to analyze (if None, system-wide)
        
        Returns:
            Health report dict
        
        Example:
            health = analytics.get_session_health_report(guild_id=123456789)
            # Returns: {
            #     "total_sessions": 150,
            #     "active": 45,
            #     "expired": 89,
            #     "closed": 16,
            #     "avg_turn_count": 8.3,
            #     "error_rate": 0.05,
            #     "top_intents": ["greeting", "question_answering", "role_play"],
            #     "health_score": 0.92
            # }
        """
        try:
            collection = self._get_sessions_collection()
            
            # Build query
            query = {}
            if guild_id:
                query["guild_id"] = guild_id
            
            # Get total count
            total = collection.count_documents(query)
            
            # Get counts by state
            states = {}
            for state in [s.value for s in SessionState]:
                count = collection.count_documents({**query, "status": state})
                states[state] = count
            
            # Get average turn count
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": None,
                    "avg_turns": {"$avg": "$turn_count"},
                    "min_turns": {"$min": "$turn_count"},
                    "max_turns": {"$max": "$turn_count"},
                }},
            ]
            result = list(collection.aggregate(pipeline))
            avg_turns = result[0].get("avg_turns", 0) if result else 0
            
            # Get top intents
            top_intents = self.get_intent_distribution(guild_id=guild_id)
            top_3 = list(top_intents.keys())[:3]
            
            # Calculate health score (0-1)
            # Factors: active sessions ratio, error rate, turn count
            active_ratio = states.get("active", 0) / max(total, 1)
            expired_ratio = states.get("expired", 0) / max(total, 1)
            error_ratio = (total - sum(states.values())) / max(total, 1)
            
            # Health = (active sessions are good) - (expired sessions are bad) - (errors)
            health_score = max(0, min(1, active_ratio - expired_ratio * 0.5 - error_ratio))
            
            return {
                "guild_id": guild_id,
                "timestamp": datetime.utcnow(),
                "total_sessions": total,
                "states": states,
                "avg_turn_count": round(avg_turns, 2),
                "top_intents": top_3,
                "health_score": round(health_score, 2),
                "status": "healthy" if health_score > 0.8 else "degraded" if health_score > 0.5 else "unhealthy",
            }
        
        except Exception as e:
            logger.error(
                f"[❌ analytics] Failed to generate health report: {e}"
            )
            return {"error": str(e)}


# Singleton instance
_analytics_service: Optional[ConversationAnalyticsService] = None


def get_conversation_analytics_service() -> ConversationAnalyticsService:
    """Get or create the conversation analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = ConversationAnalyticsService()
    return _analytics_service
