"""LLM abstraction package.

This module provides the core conversation and context management for Abby.

Current Architecture (Phase 3 - UNIFIED):
- ConversationService: Unified API for session + generation operations
- conversation.py: Internal LLM generation logic (wrapped by ConversationService)
- context.py: ConversationContext with Memory/RAG separation

**RECOMMENDED USAGE:**
    from abby_core.services.conversation_service import get_conversation_service
    conversation = get_conversation_service()
    response, error = await conversation.generate_response(message, context)

For persona/personality management, use:
    from abby_core.personality.manager import get_personality_manager

For intelligence orchestration (intent, RAG, etc.), use:
    from tdos_intelligence import Orchestrator, classify_intent
"""

# Unified conversation service (RECOMMENDED)
from abby_core.services.conversation_service import get_conversation_service

# Core conversation functions (INTERNAL - prefer ConversationService)
from abby_core.llm.conversation import (
    respond,
    summarize,
    analyze,
    get_llm_client,
)

# Context data structures
from abby_core.llm.context import (
    ConversationContext,
    PersonaConfig,
    PersonalityConfig,
    UserProfile,
)

# For backwards compatibility with code that imports LLMClient from here
from tdos_intelligence.llm import LLMClient

__all__ = [
    # Unified service (RECOMMENDED)
    "get_conversation_service",
    # Conversation functions (internal - prefer ConversationService)
    "respond",
    "summarize",
    "analyze",
    "get_llm_client",
    # Context structures
    "ConversationContext",
    "PersonaConfig",
    "PersonalityConfig",
    "UserProfile",
    # LLM Client (backwards compat)
    "LLMClient",
]
