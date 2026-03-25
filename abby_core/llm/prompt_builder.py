"""Prompt Builder - System Prompt Assembly

Extracted from personality/manager.py (Phase 2: Architecture Refactoring).

**Responsibility:**
- Assemble complete system prompts from components
- Apply static + dynamic context sections
- Inject memory, RAG, platform state, devlog
- Add turn state metadata
- Handle final turn closure instructions

**Does NOT:**
- Load persona definitions (delegated to personality/manager)
- Validate persona schemas (delegated to personality/schema)
- Fetch RAG/memory context (delegated to context_factory)

Architecture Benefits:
- Reduces manager.py from 1100+ → ~700 lines
- Isolates prompt assembly from persona management
- Testable prompt construction logic
- Clear separation of concerns
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
import logging

from abby_core.personality.schema import PersonaSchema

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Assembles system prompts from persona + context components.
    
    Takes a validated persona schema and combines it with dynamic context
    (guild, memory, RAG, platform state, turn metadata) to produce a complete
    system prompt for LLM invocation.
    """
    
    def __init__(self):
        """Initialize prompt builder."""
        pass
    
    def build_system_prompt(
        self,
        persona: PersonaSchema,
        static_prompt: str,
        guild_name: Optional[str] = None,
        turn_number: int = 1,
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None,
        system_state: Optional[Dict[str, Any]] = None,
        devlog_context: Optional[str] = None,
        is_final_turn: bool = False,
        turn_phase: Optional[str] = None,
        user_role: str = "member",
        is_bot_creator: bool = False,
    ) -> str:
        """Build complete system prompt from components.
        
        Args:
            persona: Validated persona schema
            static_prompt: Pre-built static portion (persona core + boundaries)
            guild_name: Discord guild name (injected on turn 1 only)
            turn_number: Current turn (1-indexed)
            memory_context: TDOS Memory facts (user-specific)
            rag_context: RAG retrieval context (documents, devlogs)
            system_state: Platform state dict (seasons, events, effects)
            devlog_context: Changelog summary (meta_system intent only)
            is_final_turn: Whether this is the last allowed turn
            turn_phase: Turn phase hint (greeting|question|answer|followup|closure)
            user_role: User permission level
            is_bot_creator: Whether user is bot creator
        
        Returns:
            Complete system prompt string
        """
        # Start with static base
        system_prompt = static_prompt
        
        # Inject guild context only on first turn (not cached in static)
        if turn_number == 1 and guild_name:
            system_prompt += f"\\n\\n## Guild Context\\nYou are in {guild_name}.\\n"
        
        # Apply memory budget to prevent context bloat (300 tokens ≈ 1200 chars)
        if memory_context:
            memory_context = self._apply_memory_budget(memory_context, max_chars=1200)
            system_prompt += ("\\n\\n## TDOS Memory (recent, informal)\\n" + memory_context)
        
        # Append RAG context if available
        if rag_context:
            system_prompt += ("\\n\\n## RAG Context (reference)\\n" + rag_context)
        
        # Inject current platform/system state (seasons, events, modes)
        if system_state:
            try:
                from abby_core.llm.system_state_resolver import summarize_state_for_prompt
                summary = summarize_state_for_prompt(system_state)
            except Exception as exc:
                logger.warning(f"[PromptBuilder] Unable to summarize system state: {exc}")
                summary = None
            
            if summary:
                system_prompt += ("\\n\\n## Platform State\\n" + summary)
        
        # Inject devlog context ONLY when provided (meta_system intent only)
        if devlog_context:
            system_prompt += ("\\n\\n## Development Log\\n" + devlog_context)
        
        # Add turn state metadata
        system_prompt += self._build_turn_state_section(
            turn_number=turn_number,
            is_final_turn=is_final_turn,
            turn_phase=turn_phase,
            persona_name=persona.name,
            user_role=user_role,
            is_bot_creator=is_bot_creator
        )
        
        return system_prompt
    
    def _build_turn_state_section(
        self,
        turn_number: int,
        is_final_turn: bool,
        turn_phase: Optional[str],
        persona_name: str,
        user_role: str,
        is_bot_creator: bool
    ) -> str:
        """Build turn state metadata section.
        
        Args:
            turn_number: Current turn number
            is_final_turn: Whether this is the final turn
            turn_phase: Optional phase hint
            persona_name: Persona name (for farewell generation)
            user_role: User role level
            is_bot_creator: Whether user is bot creator
        
        Returns:
            Turn state section string
        """
        # Force phase to "closure" on final turn
        if is_final_turn:
            resolved_phase = "closure"
        else:
            resolved_phase = turn_phase or "followup"
        
        expected_behavior = self._map_expected_behavior(resolved_phase, is_final_turn)
        
        # Build phase-specific flags
        flags: List[str] = []
        if not is_final_turn:
            if resolved_phase == "answer":
                flags.append("must_acknowledge_user_fact=true")
            elif resolved_phase == "question":
                flags.append("must_wait_for_answer=true")
        
        # Base turn state
        section = (
            "\\n\\n[TURN_STATE]\\n"
            f"turn_number={turn_number}\\n"
            f"final_turn={'true' if is_final_turn else 'false'}\\n"
            f"turn_phase={resolved_phase}\\n"
            f"expected_behavior={expected_behavior}"
        )
        
        if flags:
            section += "\\n" + "\\n".join(flags)
        
        # Add final turn closure instructions
        if is_final_turn:
            # Import here to avoid circular dependency
            from abby_core.personality.manager import get_personality_manager
            farewell = get_personality_manager().get_farewell_for_persona(
                persona_name=persona_name,
                user_role=user_role,
                is_bot_creator=is_bot_creator
            )
            section += (
                "\\n\\n[CONVERSATION_STATE]\\n"
                "final_turn=true\\n"
                "expected_behavior=graceful_closure\\n"
                f"suggested_farewell={farewell}\\n"
                "Do NOT ask follow-up questions. End naturally."
            )
        
        return section
    
    @staticmethod
    def _map_expected_behavior(turn_phase: str, is_final_turn: bool) -> str:
        """Map turn phase to expected behavior hint.
        
        Args:
            turn_phase: Phase of conversation
            is_final_turn: Whether this is the final turn
        
        Returns:
            Behavior hint string
        """
        if is_final_turn:
            return "graceful_closure"
        
        phase_map = {
            "greeting": "warm_welcome",
            "question": "active_listening",
            "answer": "acknowledge_fact",
            "followup": "natural_continuation",
            "closure": "graceful_closure"
        }
        
        return phase_map.get(turn_phase, "natural_continuation")
    
    @staticmethod
    def _apply_memory_budget(memory_text: str, max_chars: int = 1200) -> str:
        """Truncate memory context to budget limit.
        
        Applies budget from end (most recent facts preserved).
        
        Args:
            memory_text: Memory context text
            max_chars: Maximum character count
        
        Returns:
            Truncated memory text
        """
        if len(memory_text) <= max_chars:
            return memory_text
        
        # Truncate from beginning, preserve recent context
        truncated = "..." + memory_text[-(max_chars - 3):]
        logger.debug(
            f"[PromptBuilder] Memory budget applied: "
            f"{len(memory_text)} chars → {len(truncated)} chars"
        )
        return truncated


# Singleton instance
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get singleton prompt builder instance.
    
    Returns:
        PromptBuilder instance
    """
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
