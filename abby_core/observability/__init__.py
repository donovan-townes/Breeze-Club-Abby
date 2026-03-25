"""
Observability Module
====================
Logging, telemetry, and monitoring infrastructure.

Exports:
    - logging: Structured logging setup and configuration
    - telemetry: TDOS event emission for observability
    - conversation_metrics: FSM conversation metrics and analysis
"""

from abby_core.observability.logging import (
    setup_logging,
    logging,
)

from abby_core.observability.telemetry import (
    emit_event,
    emit_heartbeat,
    emit_error,
    emit_llm_inference,
)

from abby_core.observability.conversation_metrics import (
    ConversationMetrics,
    get_conversation_metrics,
    record_conversation_turn,
    get_metrics_summary,
    reset_metrics,
)

# Lazy import to avoid circular dependencies
def __getattr__(name):
    """Lazy load scheduler heartbeat on demand to avoid circular imports."""
    if name == "SchedulerHeartbeatService":
        from abby_core.services.scheduler_heartbeat import SchedulerHeartbeatService
        return SchedulerHeartbeatService
    elif name == "SchedulerHealth":
        from abby_core.services.scheduler_heartbeat import SchedulerHealth
        return SchedulerHealth
    elif name == "SchedulerHeartbeat":
        from abby_core.services.scheduler_heartbeat import SchedulerHeartbeat
        return SchedulerHeartbeat
    elif name == "get_scheduler_heartbeat":
        from abby_core.services.scheduler_heartbeat import get_scheduler_heartbeat
        return get_scheduler_heartbeat
    elif name == "reset_heartbeat_service":
        from abby_core.services.scheduler_heartbeat import reset_heartbeat_service
        return reset_heartbeat_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "setup_logging",
    "logging",
    "emit_event",
    "emit_heartbeat",
    "emit_error",
    "emit_llm_inference",
    "ConversationMetrics",
    "get_conversation_metrics",
    "record_conversation_turn",
    "get_metrics_summary",
    "reset_metrics",
    "SchedulerHeartbeatService",
    "SchedulerHealth",
    "SchedulerHeartbeat",
    "get_scheduler_heartbeat",
    "reset_heartbeat_service",
]
