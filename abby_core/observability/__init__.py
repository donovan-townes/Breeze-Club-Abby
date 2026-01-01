"""
Observability Module
====================
Logging, telemetry, and monitoring infrastructure.

Exports:
    - logging: Structured logging setup and configuration
    - telemetry: TDOS event emission for observability
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

__all__ = [
    "setup_logging",
    "logging",
    "emit_event",
    "emit_heartbeat",
    "emit_error",
    "emit_llm_inference",
]
