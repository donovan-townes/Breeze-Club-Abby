"""Conversation context - encapsulates all data injected into respond function.

This module defines the ConversationContext dataclass which bundles:
- User profile (creative profile, preferences, etc.)
- Persona configuration (name, system message, behaviors)
- Personality settings (temperature, response patterns)
- Conversation history
- Optional memory/RAG context

Instead of the respond() function retrieving these from the database,
they are injected as a single context object. This enables:
- Clean separation of concerns
- Easier testing and mocking
- Proper dependency injection
- Preparation for intent gating (add intent/function info here)
- Clear data flow

Usage:
    from abby_core.llm.context import ConversationContext
    from abby_core.services.conversation_service import get_conversation_service
    
    context = ConversationContext(
        user_id="12345",
        user_profile={"name": "Alice", "genres": ["rock", "indie"]},
        persona=PersonaConfig(name="bunny", system_message="I'm Abby..."),
        personality=PersonalityConfig(persona="bunny"),
        temperature=0.7,
        chat_history=[...],
    )
    
    conversation = get_conversation_service()
    response, error = await conversation.generate_response("Hello!", context)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class PersonaConfig:
    """Persona configuration - who Abby is right now."""
    name: str
    system_message: str
    persona_number: float = 0.7  # Temperature/personality intensity


@dataclass
class PersonalityConfig:
    """Personality behaviors - how Abby acts."""
    persona_name: str
    response_patterns: Dict[str, List[str]] = field(default_factory=dict)
    summon_words: List[str] = field(default_factory=list)
    dismiss_words: List[str] = field(default_factory=list)
    emojis: Dict[str, str] = field(default_factory=dict)


@dataclass
class UserProfile:
    """User profile - context about who we're talking to."""
    user_id: str
    name: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    influences: List[str] = field(default_factory=list)
    description: Optional[str] = None
    
    # Raw profile dict for extensibility
    raw_profile: Dict[str, Any] = field(default_factory=dict)
    
    def to_user_context_string(self) -> str:
        """Format user profile as context string for system prompt.
        
        Returns:
            Formatted string describing the user, or generic fallback if no profile.
        
        Example:
            "User named Alice who likes rock and indie. Influences: Pink Floyd, Arctic Monkeys"
        """
        if not self.name:
            return "This user has not created a profile yet."
        
        parts = [f"User named {self.name}"]
        
        if self.genres:
            genres_str = ", ".join(self.genres)
            parts.append(f"who likes {genres_str}")
        
        if self.description:
            parts.append(f"More about them: {self.description}")
        
        if self.influences:
            influences_str = ", ".join(self.influences)
            parts.append(f"Music influences: {influences_str}")
        
        return ". ".join(parts) + "."


@dataclass
class ConversationContext:
    """
    Complete context for a conversation turn.
    
    All data needed for respond() is packaged here, eliminating the need
    for the function to retrieve data from databases.
    
    Attributes:
        user_id: Discord user ID
        user_profile: User profile data (or empty if not yet created)
        persona: Active persona configuration
        personality: Personality behaviors
        temperature: LLM temperature (controlled by personality)
        chat_history: Previous messages in conversation
        memory_context: Optional informal facts/context from TDOS Memory system
                       (non-permanent, decays over time, user-specific insights)
        rag_context: Optional formal unchanging info from RAG system
                    (persistent, structured, knowledge base)
        intent_info: Optional intent classification and available functions (future)
        session_policy: Business logic for rate limiting, paid tiers, cooldowns
                       (max_turns, cooldown_seconds, tier: "owner"|"default"|"paid")
    """
    
    user_id: str
    user_profile: UserProfile
    persona: PersonaConfig
    personality: PersonalityConfig
    temperature: float = 0.7
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    memory_context: Optional[str] = None  # From TDOS Memory (facts, decays)
    rag_context: Optional[str] = None     # From RAG system (formal, permanent)
    intent_info: Optional[Dict[str, Any]] = None
    # Session tracking for audit and observability
    session_id: Optional[str] = None
    # Platform/system state overlays (season, events, modes)
    system_state: Optional[Dict[str, Any]] = None
    # Guild context
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    # Guild-derived flags that can influence prompt style
    user_level: str = "member"
    is_owner: bool = False
    # Session policy for business logic (paid tiers, rate limiting, etc.)
    session_policy: Optional[Dict[str, Any]] = field(default_factory=lambda: {
        "max_turns": 50,
        "cooldown_seconds": 0,
        "tier": "default"
    })
    
    def get_system_messages(self) -> List[Dict[str, str]]:
        """
        Build the system messages for this conversation context.
        
        Distinguishes between:
        - Memory: informal, decaying facts from TDOS Memory system (user insights)
        - RAG: formal, permanent knowledge from RAG system (knowledge base)
        
        Returns:
            List of system message dicts with 'role' and 'content' keys
            
        Structure:
            1. Persona system message (defines who Abby is)
            2. User context message (describes who we're talking to)
            3. Optional memory context (informal user-specific facts that decay)
            4. Optional RAG context (formal permanent knowledge base)
            5. Optional intent context (function availability, future)
        """
        messages = []
        
        # 1. Persona
        messages.append({
            "role": "system",
            "content": self.persona.system_message
        })
        
        # 2. User context
        messages.append({
            "role": "system",
            "content": f"User context: {self.user_profile.to_user_context_string()}"
        })
        
        # 3. Memory context (informal, decaying user-specific facts)
        if self.memory_context:
            messages.append({
                "role": "system",
                "content": f"Recent memory (user-specific context):\n{self.memory_context}"
            })
        
        # 4. RAG context (formal, permanent knowledge base)
        if self.rag_context:
            messages.append({
                "role": "system",
                "content": f"Reference information (knowledge base):\n{self.rag_context}"
            })
        
        # 5. Intent/function context (placeholder for future)
        if self.intent_info:
            functions_str = self.intent_info.get("available_functions_summary", "")
            if functions_str:
                messages.append({
                    "role": "system",
                    "content": f"Available actions: {functions_str}"
                })
        
        return messages


__all__ = [
    "ConversationContext",
    "PersonaConfig",
    "PersonalityConfig",
    "UserProfile",
]
