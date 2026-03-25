"""Generation Audit Service

LLM call logging and cost tracking for observability and scaling.
Part of Phase 2 architectural improvements.

**Responsibility:**
- Log all LLM calls with full input/output
- Track token usage and costs
- Measure latency and throughput
- Provider-agnostic tracking (OpenAI, Ollama, etc.)
- Cost projection for 50-year scaling

**Benefits:**
- Operator visibility into generation pipeline
- Cost tracking and budgeting
- Performance monitoring
- Debugging assistance (full request/response logs)
- Capacity planning for long-term scaling
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import logging

from abby_core.database.mongodb import get_database

logger = logging.getLogger(__name__)


# Token cost estimates (USD per 1K tokens, approximate as of 2026)
TOKEN_COSTS = {
    "openai:gpt-4": {"input": 0.03, "output": 0.06},
    "openai:gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "openai:gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "ollama": {"input": 0.0, "output": 0.0},  # Local inference, no cost
    "anthropic:claude-3": {"input": 0.015, "output": 0.075},
}


@dataclass
class GenerationAuditRecord:
    """Audit record for a single LLM generation call.
    
    Tracks all relevant metadata for cost analysis, debugging,
    and performance monitoring.
    """
    
    # Identifiers
    audit_id: str
    session_id: Optional[str]
    user_id: Optional[str]
    guild_id: Optional[str]
    
    # Timing
    timestamp: datetime
    latency_ms: float
    
    # Provider info
    provider: str  # "openai", "ollama", "anthropic"
    model: str  # "gpt-4", "mistral", "claude-3-opus"
    
    # Usage
    input_tokens: int
    output_tokens: int
    total_tokens: int
    
    # Cost (USD)
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    
    # Context
    intent: Optional[str] = None
    turn_number: Optional[int] = None
    
    # Input/output (truncated for storage)
    system_prompt_preview: Optional[str] = None  # First 500 chars
    user_message_preview: Optional[str] = None  # First 500 chars
    response_preview: Optional[str] = None  # First 500 chars
    
    # Metadata
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for MongoDB storage."""
        return asdict(self)


class GenerationAuditService:
    """Tracks LLM generation calls for cost analysis and observability.
    
    Logs all LLM invocations with full context, token usage, and costs.
    Provides aggregation queries for cost projection and capacity planning.
    """
    
    def __init__(self):
        """Initialize generation audit service."""
        self.collection_name = "generation_audit"
    
    def _get_collection(self):
        """Get MongoDB collection for audit records."""
        db = get_database()
        return db[self.collection_name]
    
    def _estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> tuple[float, float, float]:
        """Estimate cost for LLM call.
        
        Args:
            provider: Provider name (openai, ollama, anthropic)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            (input_cost_usd, output_cost_usd, total_cost_usd)
        """
        provider_key = f"{provider}:{model}"
        
        # Use specific model costs if available, else fall back to provider default
        costs = TOKEN_COSTS.get(provider_key)
        if not costs:
            # Try provider-level default
            costs = TOKEN_COSTS.get(provider, {"input": 0.01, "output": 0.03})
        
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        total_cost = input_cost + output_cost
        
        return (input_cost, output_cost, total_cost)
    
    def log_generation(
        self,
        audit_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        guild_id: Optional[str] = None,
        intent: Optional[str] = None,
        turn_number: Optional[int] = None,
        system_prompt: Optional[str] = None,
        user_message: Optional[str] = None,
        response: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> GenerationAuditRecord:
        """Log a completed LLM generation call.
        
        Args:
            audit_id: Unique ID for this generation
            provider: Provider name (openai, ollama, etc.)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Generation latency in milliseconds
            session_id: Chat session ID (if applicable)
            user_id: User ID who triggered generation
            guild_id: Guild ID where generation occurred
            intent: Classified intent (casual_chat, creative_assist, etc.)
            turn_number: Turn number in conversation
            system_prompt: System prompt text (will be truncated)
            user_message: User message text (will be truncated)
            response: LLM response text (will be truncated)
            success: Whether generation succeeded
            error_message: Error message if failed
        
        Returns:
            GenerationAuditRecord that was logged
        """
        # Calculate costs
        input_cost, output_cost, total_cost = self._estimate_cost(
            provider, model, input_tokens, output_tokens
        )
        
        # Create audit record
        record = GenerationAuditRecord(
            audit_id=audit_id,
            session_id=session_id,
            user_id=user_id,
            guild_id=guild_id,
            timestamp=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            intent=intent,
            turn_number=turn_number,
            system_prompt_preview=system_prompt[:500] if system_prompt else None,
            user_message_preview=user_message[:500] if user_message else None,
            response_preview=response[:500] if response else None,
            success=success,
            error_message=error_message,
        )
        
        # Store in MongoDB
        try:
            collection = self._get_collection()
            collection.insert_one(record.to_dict())
            
            logger.info(
                f"[GenerationAudit] Logged generation: "
                f"provider={provider}, model={model}, "
                f"tokens={input_tokens + output_tokens}, "
                f"cost=${total_cost:.4f}, latency={latency_ms:.0f}ms"
            )
        except Exception as exc:
            logger.error(f"[GenerationAudit] Failed to log generation: {exc}")
        
        return record
    
    def get_cost_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        guild_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get cost summary for a time period.
        
        Args:
            start_date: Start of period (default: beginning of time)
            end_date: End of period (default: now)
            guild_id: Filter by guild (optional)
            provider: Filter by provider (optional)
        
        Returns:
            Summary dict with total cost, token counts, call counts
        """
        collection = self._get_collection()
        
        # Build query
        query: Dict[str, Any] = {}
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        if guild_id:
            query["guild_id"] = guild_id
        
        if provider:
            query["provider"] = provider
        
        # Aggregate
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "total_calls": {"$sum": 1},
                    "successful_calls": {
                        "$sum": {"$cond": [{"$eq": ["$success", True]}, 1, 0]}
                    },
                    "total_cost_usd": {"$sum": "$total_cost_usd"},
                    "total_input_tokens": {"$sum": "$input_tokens"},
                    "total_output_tokens": {"$sum": "$output_tokens"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "avg_latency_ms": {"$avg": "$latency_ms"},
                }
            }
        ]
        
        result = list(collection.aggregate(pipeline))
        
        if not result:
            return {
                "total_calls": 0,
                "successful_calls": 0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "avg_latency_ms": 0.0,
            }
        
        summary = result[0]
        summary.pop("_id", None)
        
        logger.info(
            f"[GenerationAudit] Cost summary: "
            f"calls={summary['total_calls']}, "
            f"cost=${summary['total_cost_usd']:.2f}, "
            f"tokens={summary['total_tokens']:,}"
        )
        
        return summary
    
    def get_provider_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get cost breakdown by provider and model.
        
        Args:
            start_date: Start of period (default: beginning of time)
            end_date: End of period (default: now)
        
        Returns:
            List of provider/model breakdowns with costs and usage
        """
        collection = self._get_collection()
        
        # Build query
        query: Dict[str, Any] = {}
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        # Aggregate by provider and model
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": {"provider": "$provider", "model": "$model"},
                    "call_count": {"$sum": 1},
                    "total_cost_usd": {"$sum": "$total_cost_usd"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "avg_latency_ms": {"$avg": "$latency_ms"},
                }
            },
            {"$sort": {"total_cost_usd": -1}}  # Sort by cost descending
        ]
        
        results = list(collection.aggregate(pipeline))
        
        # Format output
        breakdown = []
        for item in results:
            breakdown.append({
                "provider": item["_id"]["provider"],
                "model": item["_id"]["model"],
                "call_count": item["call_count"],
                "total_cost_usd": item["total_cost_usd"],
                "total_tokens": item["total_tokens"],
                "avg_latency_ms": item["avg_latency_ms"],
            })
        
        return breakdown


# Singleton instance
_audit_service: Optional[GenerationAuditService] = None


def get_generation_audit_service() -> GenerationAuditService:
    """Get singleton generation audit service.
    
    Returns:
        GenerationAuditService instance
    """
    global _audit_service
    if _audit_service is None:
        _audit_service = GenerationAuditService()
    return _audit_service
