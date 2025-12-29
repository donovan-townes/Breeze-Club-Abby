"""
TDOS v1.5 Event Emission Helper

This module enforces the TDOS v1.5 event envelope specification and provides
append-only JSONL event emission for observability and governance signals.

All Abby events MUST flow through emit_event() to ensure:
- Schema version consistency (tdos.event.v1)
- Required field validation
- Deterministic event_id generation
- Immutable append-only writes
- Subject/tenant provenance tracking

CRITICAL: Never write events directly to JSONL. Always use this helper.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Default TDOS configuration (override via environment)
TDOS_TENANT_ID = os.getenv("TDOS_TENANT_ID", "TENANT:BREEZE_CLUB")
TDOS_AGENT_SUBJECT_ID = os.getenv("TDOS_AGENT_SUBJECT_ID", "AGENT:ABBY-DISCORD")
TDOS_MACHINE_SUBJECT_ID = os.getenv("TDOS_MACHINE_SUBJECT_ID", "MACHINE:TSERVER")
TDOS_EVENTS_PATH = os.getenv("TDOS_EVENTS_PATH", "shared/logs/events.jsonl")
TDOS_EVENT_ID_PREFIX = os.getenv("TDOS_EVENT_ID_PREFIX", "EVT-ABBY")

# Schema version (locked to v1.5 envelope)
SCHEMA_VERSION = "tdos.event.v1"

# Valid event types (extend as needed)
VALID_EVENT_TYPES = {
    "HEARTBEAT",
    "JOB.STARTED",
    "JOB.COMPLETED",
    "JOB.FAILED",
    "ERROR",
    "LLM.INFERENCE",
    "RAG.QUERY",
    "DISCORD.COMMAND",
}


def generate_event_id() -> str:
    """
    Generate deterministic event ID: EVT-ABBY-{TIMESTAMP}-{RANDOM}
    
    Format ensures:
    - Uniqueness via random suffix
    - Sortability via timestamp
    - Agent attribution via prefix
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = uuid.uuid4().hex[:8].upper()
    return f"{TDOS_EVENT_ID_PREFIX}-{timestamp}-{random_suffix}"


def emit_event(
    event_type: str,
    payload: Dict[str, Any],
    job_id: Optional[str] = None,
    invoker_subject_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Emit a TDOS v1.5 compliant event to append-only JSONL.
    
    Args:
        event_type: One of VALID_EVENT_TYPES (e.g., "HEARTBEAT", "ERROR", "LLM.INFERENCE")
        payload: Event-specific data (must be JSON-serializable dict)
        job_id: Optional job correlation ID (defaults to "JOB:NONE")
        invoker_subject_id: Optional invoker (defaults to agent subject ID)
    
    Returns:
        Complete event envelope (for testing/logging)
    
    Raises:
        ValueError: If event_type invalid or required fields missing
        IOError: If JSONL write fails
    
    Example:
        emit_event("HEARTBEAT", {
            "uptime_seconds": 3600,
            "active_sessions": 3,
            "ollama_latency_ms": 450
        })
    """
    # Validation
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type '{event_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )
    
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be dict, got {type(payload).__name__}")
    
    # Build envelope with defaults
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": generate_event_id(),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tenant_id": TDOS_TENANT_ID,
        "agent_subject_id": TDOS_AGENT_SUBJECT_ID,
        "machine_subject_id": TDOS_MACHINE_SUBJECT_ID,
        "job_id": job_id or "JOB:NONE",
        "invoker_subject_id": invoker_subject_id or TDOS_AGENT_SUBJECT_ID,
        "payload": payload,
    }
    
    # Validate required fields presence (defensive)
    required = [
        "schema_version", "event_id", "event_type", "timestamp",
        "tenant_id", "agent_subject_id", "machine_subject_id",
        "job_id", "invoker_subject_id", "payload"
    ]
    missing = [field for field in required if field not in event]
    if missing:
        raise ValueError(f"Envelope missing required fields: {missing}")
    
    # Append-only write to JSONL
    try:
        events_path = Path(TDOS_EVENTS_PATH)
        events_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    except Exception as e:
        # DO NOT silently fail; TDOS signals are critical
        raise IOError(f"Failed to write event to {TDOS_EVENTS_PATH}: {e}") from e
    
    return event


def emit_heartbeat(
    uptime_seconds: int,
    active_sessions: int,
    pending_submissions: int,
    ollama_latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper for HEARTBEAT events.
    
    Args:
        uptime_seconds: Bot uptime in seconds
        active_sessions: Count of active chat sessions
        pending_submissions: Count of pending submissions
        ollama_latency_ms: Optional Ollama inference latency
    
    Returns:
        Complete event envelope
    """
    payload = {
        "uptime_seconds": uptime_seconds,
        "active_sessions": active_sessions,
        "pending_submissions": pending_submissions,
    }
    
    if ollama_latency_ms is not None:
        payload["ollama_latency_ms"] = ollama_latency_ms
    
    return emit_event("HEARTBEAT", payload)


def emit_error(
    error_type: str,
    message: str,
    stack_trace: Optional[str] = None,
    recovery_action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper for ERROR events.
    
    Args:
        error_type: Error class name (e.g., "OllamaConnectionError")
        message: Human-readable error description
        stack_trace: Optional full stack trace
        recovery_action: Optional recovery/fallback description
    
    Returns:
        Complete event envelope
    """
    payload = {
        "error_type": error_type,
        "message": message,
    }
    
    if stack_trace:
        payload["stack_trace"] = stack_trace
    
    if recovery_action:
        payload["recovery_action"] = recovery_action
    
    return emit_event("ERROR", payload)


def emit_llm_inference(
    provider: str,
    model: str,
    request_type: str,
    prompt_length: int,
    latency_ms: int,
    token_count: Optional[int] = None,
    success: bool = True,
    job_id: Optional[str] = None,
    invoker_subject_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper for LLM.INFERENCE events.
    
    Args:
        provider: LLM provider (e.g., "ollama", "openai")
        model: Model name (e.g., "llama3", "gpt-3.5-turbo")
        request_type: Request type (e.g., "generate", "summarize")
        prompt_length: Prompt character length
        latency_ms: Inference latency in milliseconds
        token_count: Optional output token count
        success: Whether inference succeeded
        job_id: Optional job correlation ID
        invoker_subject_id: Optional Discord user subject ID
    
    Returns:
        Complete event envelope
    """
    payload = {
        "provider": provider,
        "model": model,
        "request_type": request_type,
        "prompt_length": prompt_length,
        "latency_ms": latency_ms,
        "success": success,
    }
    
    if token_count is not None:
        payload["token_count"] = token_count
    
    return emit_event(
        "LLM.INFERENCE",
        payload,
        job_id=job_id,
        invoker_subject_id=invoker_subject_id,
    )
