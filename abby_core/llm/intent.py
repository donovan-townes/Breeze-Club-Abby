"""Intent classification system for routing and context optimization.

Provides lightweight intent detection to:
- Choose appropriate prompt templates
- Decide memory injection necessity
- Route between LLM vs no-LLM paths
- Enable context-aware response strategies

Start with rule-based classification; extend with LLM if needed.

NOTE: This module is platform-agnostic. It uses the abby_core.llm.interfaces
abstractions instead of importing discord types, enabling reuse across adapters.
"""

from enum import Enum
from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Core intent categories for conversation routing."""
    
    CASUAL_CHAT = "casual_chat"           # Simple greetings, small talk, casual questions
    CREATIVE_ASSIST = "creative_assist"   # Music, art, writing, creative work
    TASK_REQUEST = "task_request"         # Specific actionable requests
    CONFIG_ADMIN = "config_admin"         # Bot configuration, admin commands
    ANALYSIS_EXTRACTION = "analysis_extraction"  # Data analysis, fact extraction
    META_SYSTEM = "meta_system"           # Self-referential questions about Abby/system changes


# Rule-based intent patterns
INTENT_PATTERNS = {
    Intent.CASUAL_CHAT: [
        r"\b(hi|hello|hey|sup|what'?s up|how are you|good morning|good evening)\b",
        r"\b(thanks|thank you|appreciate it|awesome|cool|nice)\b",
        r"\b(weather|sky|color|simple question)\b",
        r"^.{1,20}$",  # Very short messages are often casual
    ],
    Intent.META_SYSTEM: [
        r"\b(under the hood|how (are|were) you built|how do you work)\b",
        r"\b(what'?s new|what changed|changelog|dev ?log|updates?)\b",
        r"\b(what did you add|what did you improve|recent changes)\b",
        r"\b(about your system|how you were made|how you are made)\b",
    ],
    Intent.CREATIVE_ASSIST: [
        r"\b(music|song|track|mix|production|audio|beat|melody|chord|eq|kick)\b",
        r"\b(art|draw|paint|sketch|design|illustration|creative)\b",
        r"\b(write|story|book|novel|chapter|poem|draft)\b",
        r"\b(code|program|script|function|debug|algorithm)\b",
        r"\b(game|level|character|quest|play)\b",
    ],
    Intent.TASK_REQUEST: [
        r"\b(help me|can you|please|could you|would you)\b",
        r"\b(create|make|generate|build|set up)\b",
        r"\b(find|search|look up|show me)\b",
        r"\b(remind|schedule|plan|organize)\b",
        r"\b(exp|experience|xp|level|rank)\b",
        r"\b(my\s+)?(exp|experience|xp|level)",
    ],
    Intent.CONFIG_ADMIN: [
        r"\b(config|configure|setup|settings|preferences)\b",
        r"\b(admin|manage|moderate|permission)\b",
        r"\b(enable|disable|turn on|turn off)\b",
        r"\b(set|change)\s+(your|my|the|bot)?\s*(status|presence)",
        r"\bstatus\s+(to\s+)?(playing|listening|watching)",
    ],
    Intent.ANALYSIS_EXTRACTION: [
        r"\b(analyze|extract|summarize|pattern|insight)\b",
        r"\b(data|statistics|metrics|trends)\b",
    ],
}

# Priority order for tie-breaking (higher in list wins)
INTENT_PRIORITY = [
    Intent.META_SYSTEM,
    Intent.CONFIG_ADMIN,
    Intent.TASK_REQUEST,
    Intent.CREATIVE_ASSIST,
    Intent.ANALYSIS_EXTRACTION,
    Intent.CASUAL_CHAT,
]


def classify_intent(
    user_message: str,
    chat_history: Optional[list] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Intent:
    """Classify user intent using rule-based patterns.
    
    Args:
        user_message: The user's current message
        chat_history: Optional conversation history for context
        context: Optional additional context (guild info, user role, etc.)
    
    Returns:
        Classified intent enum
    """
    message_lower = user_message.lower().strip()
    
    # Check each intent's patterns
    intent_scores = {intent: 0 for intent in Intent}
    
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                intent_scores[intent] += 1
    
    # Return intent with highest score; break ties by priority order
    max_score = max(intent_scores.values())
    if max_score == 0:
        return Intent.CASUAL_CHAT

    # Collect intents with the max score
    tied_intents = [intent for intent, score in intent_scores.items() if score == max_score]
    for preferred in INTENT_PRIORITY:
        if preferred in tied_intents:
            return preferred

    # Fallback (should not hit)
    return Intent.CASUAL_CHAT


def should_use_llm(intent: Intent) -> bool:
    """Determine if LLM is needed for this intent.
    
    Some intents can be handled without LLM calls (e.g., config lookups).
    
    Args:
        intent: Classified intent
    
    Returns:
        True if LLM should be called
    """
    # For now, all intents use LLM
    # In future, CONFIG_ADMIN might use direct command routing
    return True


def get_prompt_template_key(intent: Intent) -> str:
    """Get the prompt template key for this intent.
    
    Enables intent-specific prompt customization.
    
    Args:
        intent: Classified intent
    
    Returns:
        Template key for prompt building
    """
    # For now, use default template
    # In future, return intent-specific template names
    return "default"


# ============================================================================
# Intent Routing & Action Dispatch (MVP)
# ============================================================================

class IntentAction:
    """Base class for intent action results."""
    
    def __init__(
        self,
        action_type: str,
        use_llm: bool = True,
        text: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            action_type: Type of action (llm, tool, refusal, etc.)
            use_llm: Whether to proceed with LLM call
            text: Optional pre-computed response text
            tool_name: Name of tool to execute (e.g., 'get_guild_info', 'set_bot_status')
            tool_args: Arguments for tool execution
        """
        self.action_type = action_type
        self.use_llm = use_llm
        self.text = text
        self.tool_name = tool_name
        self.tool_args = tool_args or {}


def route_intent_to_action(
    intent: Intent,
    context: Optional[Dict[str, Any]] = None,
) -> IntentAction:
    """Route classified intent to an action handler (MVP).
    
    Currently:
    - casual_chat → LLM
    - creative_assist → LLM
    - task_request → tool (guild info)
    - config_admin → tool (bot status) with permission check
    - analysis_extraction → LLM (restricted)
    
    NOTE: context dict values are platform-specific (e.g., discord.User, discord.Guild).
    Tool args also carry platform objects; actual tool execution is delegated to
    platform-specific tool handlers (see discord/tools/).
    
    Args:
        intent: Classified intent
        context: Conversation context (user_level, is_owner, guild, bot, etc.)
    
    Returns:
        IntentAction describing what to do
    """
    context = context or {}
    
    if intent == Intent.CASUAL_CHAT:
        logger.debug(f"[intent_route] casual_chat → LLM")
        return IntentAction(action_type="llm", use_llm=True)
    
    elif intent == Intent.CREATIVE_ASSIST:
        logger.debug(f"[intent_route] creative_assist → LLM (memory-backed)")
        return IntentAction(action_type="llm", use_llm=True)
    
    elif intent == Intent.TASK_REQUEST:
        # Determine which task tool to use
        user_message = context.get("user_message", "").lower()
        
        # Check for exp/level request
        if re.search(r"\b(exp|experience|xp|level|rank)\b", user_message):
            logger.info(f"[intent_route] task_request → tool (get_user_exp)")
            # Get the user from context (platform-specific user object)
            user = context.get("user")
            if user:
                return IntentAction(
                    action_type="tool",
                    use_llm=False,
                    tool_name="get_user_exp",
                    tool_args={"user": user}
                )
            else:
                return IntentAction(
                    action_type="tool_stub",
                    use_llm=False,
                    text="I need user context to show XP. 🐰"
                )
        
        # Otherwise, default to guild info
        logger.info(f"[intent_route] task_request → tool (get_guild_info)")
        guild = context.get("guild")
        if guild:
            return IntentAction(
                action_type="tool",
                use_llm=False,
                tool_name="get_guild_info",
                tool_args={"guild": guild}
            )
        else:
            # Fallback if guild not available
            return IntentAction(
                action_type="tool_stub",
                use_llm=False,
                text="I can show you server information when available. 🐰"
            )
    
    elif intent == Intent.CONFIG_ADMIN:
        # Check user permissions
        is_owner = context.get("is_owner", False)
        user_level = context.get("user_level", "member")
        
        if not is_owner and user_level != "admin":
            logger.info(f"[intent_route] config_admin → refusal (user_level={user_level})")
            return IntentAction(
                action_type="refusal",
                use_llm=False,
                text="You don't have permission to configure bot settings."
            )
        
        # Wire bot status tool
        logger.info(f"[intent_route] config_admin → tool (set_bot_status)")
        bot = context.get("bot")
        if bot:
            # Extract status intent from user message
            user_message = context.get("user_message", "")
            activity_type = _extract_activity_type(user_message)
            status_message = _extract_status_message(user_message)
            
            return IntentAction(
                action_type="tool",
                use_llm=False,
                tool_name="set_bot_status",
                tool_args={
                    "bot": bot,
                    "activity_type": activity_type,
                    "message": status_message,
                }
            )
        else:
            return IntentAction(
                action_type="config_stub",
                use_llm=False,
                text="Config acknowledged! ✓"
            )
    
    elif intent == Intent.ANALYSIS_EXTRACTION:
        logger.debug(f"[intent_route] analysis_extraction → LLM (restricted)")
        return IntentAction(action_type="llm", use_llm=True)

    elif intent == Intent.META_SYSTEM:
        logger.debug(f"[intent_route] meta_system → LLM")
        return IntentAction(action_type="llm", use_llm=True)
    
    else:
        # Fallback
        logger.debug(f"[intent_route] unknown intent {intent} → LLM")
        return IntentAction(action_type="llm", use_llm=True)


def _extract_activity_type(user_message: str) -> str:
    """Extract activity type (playing, watching, listening, streaming) from message."""
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ["playing", "play"]):
        return "playing"
    elif any(word in message_lower for word in ["watching", "watch"]):
        return "watching"
    elif any(word in message_lower for word in ["listening", "listen"]):
        return "listening"
    elif any(word in message_lower for word in ["streaming", "stream"]):
        return "streaming"
    else:
        return "playing"  # Default


def _extract_status_message(user_message: str) -> str:
    """Extract status message from user input.
    
    Examples:
    - "set my status to playing music" → "music"
    - "watch me code" → "me code"
    - "listening to the radio" → "the radio"
    """
    message_lower = user_message.lower()
    
    # Simple extraction: if "to" is present, take what comes after
    if " to " in message_lower:
        after_to = message_lower.split(" to ", 1)[1].strip()
        return after_to.rstrip("?!.")
    
    # Otherwise, remove common activity verbs and use the rest
    for verb in ["playing", "watching", "listening", "streaming", "watch", "listen", "play"]:
        if message_lower.startswith(verb):
            after_verb = message_lower[len(verb):].strip()
            return after_verb.rstrip("?!.")
    
    # Fallback: use full message minus the intent keywords
    return "available"
