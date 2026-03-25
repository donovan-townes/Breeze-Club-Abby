"""Abby Core Adapters - Bridge between Discord platform and TDOS intelligence.

This package provides Abby-specific wrappers around TDOS intelligence:
- OrchestratorAdapter: Adds personality, guild context, economy integration
- RAGAdapter: Adds guild isolation, storage quotas, premium features

These adapters maintain the separation:
- TDOS (tdos_intelligence) = Pure, reusable intelligence
- Abby Adapters (abby_core.adapters) = Personality + platform-specific logic
- Discord Cogs (abby_adapters.discord) = Discord API integration

Usage in Discord cogs:
    from abby_core.adapters import get_orchestrator_adapter, get_rag_adapter
    
    orchestrator = get_orchestrator_adapter()
    rag = get_rag_adapter()
"""

from abby_core.adapters.orchestrator_adapter import (
    OrchestratorAdapter,
    AbbyContext,
    get_orchestrator_adapter
)
from abby_core.adapters.rag_adapter import (
    RAGAdapter,
    RAGContext,
    get_rag_adapter
)

__all__ = [
    # Orchestrator
    "OrchestratorAdapter",
    "AbbyContext",
    "get_orchestrator_adapter",
    
    # RAG
    "RAGAdapter",
    "RAGContext",
    "get_rag_adapter",
]
