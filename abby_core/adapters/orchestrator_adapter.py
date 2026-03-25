"""Abby Orchestrator Adapter - Wraps TDOS orchestrator with personality and guild context.

This adapter bridges Discord cogs to TDOS intelligence by injecting:
- Abby personality context
- Guild-specific configuration
- Economy/XP integration
- Discord-specific message handling
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from tdos_intelligence.orchestrator import get_orchestrator
from abby_core.personality.manager import get_personality_manager
from abby_core.database.mongodb import get_database

logger = logging.getLogger(__name__)


@dataclass
class AbbyContext:
    """Extended context for Abby-specific operations.
    
    Attributes:
        guild_id: Discord guild ID
        user_id: Discord user ID
        channel_id: Discord channel ID
        personality: Personality name (e.g., "bunny", "kiki")
        user_balance: User's current economy balance
        user_level: User's XP level
        custom_memory: Guild-specific memory settings
    """
    guild_id: str
    user_id: str
    channel_id: str
    personality: str = "bunny"
    user_balance: Optional[int] = None
    user_level: Optional[int] = None
    custom_memory: Optional[Dict[str, Any]] = None


class OrchestratorAdapter:
    """Abby-specific wrapper around TDOS Orchestrator.
    
    Responsibilities:
    - Load Abby personality from abby_core/personality/
    - Inject guild-specific context
    - Handle Discord message format conversion
    - Integrate economy/XP data
    - Apply guild-level overrides
    """

    def __init__(self):
        """Initialize the orchestrator adapter."""
        self.orchestrator = get_orchestrator()
        self._db = None  # Lazy initialization
        logger.info("[Orchestrator Adapter] Initialized (database connection deferred)")

    @property
    def db(self):
        """Lazy database connection property."""
        if self._db is None:
            from abby_core.database.mongodb import is_mongodb_available
            if is_mongodb_available():
                self._db = get_database()
                logger.debug("[Orchestrator Adapter] Database connection established")
            else:
                logger.warning("[Orchestrator Adapter] MongoDB unavailable - operations will fail")
                raise ConnectionError("MongoDB is not available")
        return self._db

    async def process_message(
        self,
        message: str,
        context: AbbyContext,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Process a Discord message with Abby personality.
        
        Args:
            message: User message text
            context: Abby-specific context (guild, user, personality)
            conversation_history: Optional conversation history
        
        Returns:
            Dict containing:
                - response: Generated response text
                - intent: Detected intent
                - confidence: Intent confidence score
                - rag_used: Whether RAG was invoked
                - persona_applied: Personality name used
        """
        manager = get_personality_manager()
        persona_schema = manager.get_persona(context.personality) or manager.get_persona(manager.get_default_persona())
        if not persona_schema:
            raise RuntimeError("No persona available for orchestrator processing")

        personality_dict: Dict[str, Any] = {
            "name": persona_schema.display_name,
            "response_patterns": persona_schema.response_patterns.model_dump() if persona_schema.response_patterns else {},
            "traits": {
                "description": persona_schema.description,
                "tone": persona_schema.personality_boundaries.personality_tone if persona_schema.personality_boundaries else "friendly",
            },
        }
        
        persona_context = await self._build_persona_context(context, personality_dict)
        
        # 3. Sanitize custom_memory against injection attacks (if present)
        # custom_memory is guild-admin supplied and must be sanitized before LLM injection
        sanitized_custom_memory = context.custom_memory
        if context.custom_memory:
            from abby_core.interfaces.prompt_security import StandardPromptSecurityGate
            security_gate = StandardPromptSecurityGate(strict_mode=False)
            
            # Sanitize custom_memory fields
            is_safe, sanitized = security_gate.sanitize_context(
                context.custom_memory if isinstance(context.custom_memory, dict) else {"content": str(context.custom_memory)},
                protected_fields=list(context.custom_memory.keys()) if isinstance(context.custom_memory, dict) else ["content"],
                operator_id=f"user:{context.user_id}",
                intent="rag_injection"
            )
            
            if not is_safe:
                logger.warning(
                    f"[🚫 security] Custom memory injection BLOCKED due to detected payload "
                    f"guild={context.guild_id} user={context.user_id}"
                )
                sanitized_custom_memory = None  # Block injection if sanitization failed
            else:
                sanitized_custom_memory = sanitized
        
        # 4. Enhance conversation history with guild context (intent-gated for safety)
        # Only inject memory/RAG context for queries that legitimately need it
        # This prevents information leakage during casual conversation
        # Heuristic: Inject memory if message contains question mark or knowledge-seeking keywords
        enhanced_history = conversation_history or []
        should_inject_memory = sanitized_custom_memory and (
            "?" in message.lower() or  # Contains question mark
            any(word in message.lower() for word in [
                "help", "know", "tell", "show", "what", "how", "where", 
                "when", "why", "rule", "information", "detail", "explain",
                "describe", "find", "look", "search"
            ])
        )
        
        if should_inject_memory:
            # Prepend guild-specific memory/context (now sanitized)
            memory_content = str(sanitized_custom_memory)
            enhanced_history = [
                {"role": "system", "content": f"Guild context: {memory_content}"}
            ] + enhanced_history
            logger.debug(
                f"[🔐 memory_injection] ALLOWED "
                f"guild={context.guild_id} "
                f"user={context.user_id} "
                f"reason={'question_mark' if '?' in message.lower() else 'knowledge_keyword'} "
                f"[SANITIZED]"
            )
        else:
            logger.debug(
                f"[🔐 memory_injection] BLOCKED "
                f"guild={context.guild_id} "
                f"user={context.user_id} "
                f"reason={'no_context' if not sanitized_custom_memory else 'not_query_intent'}"
            )
        
        # 4. Call TDOS orchestrator (pure intelligence)
        tdos_result = await self.orchestrator.process_message(
            message=message,
            guild_id=context.guild_id,
            user_id=context.user_id,
            context={
                "conversation_history": enhanced_history,
                "persona": persona_context
            }
        )
        
        # 5. Post-process response with Abby personality patterns
        abby_response = await self._apply_personality_patterns(
            tdos_result.response if hasattr(tdos_result, 'response') else str(tdos_result),
            personality_dict
        )
        
        # 6. Return enhanced result
        return {
            "response": abby_response,
            "intent": tdos_result.intent if hasattr(tdos_result, 'intent') else "unknown",
            "confidence": tdos_result.intent_confidence if hasattr(tdos_result, 'intent_confidence') else "low",
            "rag_used": tdos_result.used_rag if hasattr(tdos_result, 'used_rag') else False,
            "persona_applied": context.personality,
            "guild_id": context.guild_id,
            "user_level": context.user_level,
            "user_balance": context.user_balance
        }

    async def _build_persona_context(
        self,
        context: AbbyContext,
        personality_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build persona context with Abby-specific traits.
        
        Args:
            context: Abby context
            personality_config: Personality configuration
        
        Returns:
            Persona context dict for TDOS
        """
        # Load base personality from abby_core/personality/
        base_traits = personality_config.get("traits", {})
        response_patterns = personality_config.get("response_patterns", {})
        
        # Inject economy context if available
        economy_context = ""
        if context.user_balance is not None:
            economy_context += f"User has {context.user_balance} coins. "
        if context.user_level is not None:
            economy_context += f"User is level {context.user_level}. "
        
        return {
            "name": personality_config.get("name", "Abby"),
            "traits": base_traits,
            "response_style": response_patterns,
            "economy_context": economy_context,
            "guild_id": context.guild_id
        }

    async def _apply_personality_patterns(
        self,
        response: str,
        personality_config: Dict[str, Any]
    ) -> str:
        """Apply Abby personality patterns to TDOS response.
        
        Args:
            response: Raw TDOS response
            personality_config: Personality configuration
        
        Returns:
            Response with personality patterns applied
        """
        # Apply emoji patterns, response templates, etc.
        # This is where Abby-specific quirks get added
        patterns = personality_config.get("response_patterns", {})
        
        # Example: Add personality-specific emojis or phrasing
        if patterns.get("add_emoji", False):
            # Add personality-specific emoji logic here
            pass
        
        # For now, return as-is (can enhance later)
        return response

    async def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        """Get guild-specific orchestrator settings.
        
        Args:
            guild_id: Discord guild ID
        
        Returns:
            Guild settings (personality, memory, features)
        """
        # Query MongoDB for guild-specific settings
        settings = self.db.guilds.find_one({"guild_id": guild_id})
        return settings or {"personality": "bunny", "features": []}


# Singleton pattern
_orchestrator_adapter_instance: Optional[OrchestratorAdapter] = None


def get_orchestrator_adapter() -> OrchestratorAdapter:
    """Get singleton orchestrator adapter instance.
    
    Returns:
        OrchestratorAdapter instance
    """
    global _orchestrator_adapter_instance
    if _orchestrator_adapter_instance is None:
        _orchestrator_adapter_instance = OrchestratorAdapter()
    return _orchestrator_adapter_instance
