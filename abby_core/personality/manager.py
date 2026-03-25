"""Personality Manager for Abby
Loads, validates, and manages modular persona definitions.

Architecture:
    PersonalityManager (this file)
         ↓
    Loads: modular personas/*.json + personas.json registry + guild_phrases.json
         ↓
    Validates: against Pydantic PersonaSchema
         ↓
    Caches: loaded persona objects
         ↓
    Provides: persona data, system prompt building, context injection
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import ValidationError

from abby_core.personality.schema import PersonaSchema, PersonaRegistry, GuildPhrasesSchema
from abby_core.observability.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Path to personality data directory
PERSONALITY_DATA_DIR = Path(__file__).parent / "data"
PERSONAS_DIR = PERSONALITY_DATA_DIR / "personas"
PERSONAS_REGISTRY_FILE = PERSONALITY_DATA_DIR / "personas.json"
GUILD_PHRASES_FILE = PERSONALITY_DATA_DIR / "guild_phrases.json"
DISMISS_FILE = PERSONALITY_DATA_DIR / "dismiss.json"
EMOJI_FILE = PERSONALITY_DATA_DIR / "emoji.json"

# Global root persona aliases that should always be considered for canon overlays
# This allows brand-wide canon (e.g., persona.abby.*) to apply to all persona variants
GLOBAL_PERSONA_ROOT_ALIASES: List[str] = ["abby"]



class PersonalityManager:
    """
    Centralized manager for persona definitions.
    Loads modular persona JSON files, validates against PersonaSchema,
    and provides accessors for personality data.
    """
    
    def __init__(self):
        """Initialize the personality manager and load all data."""
        self._personas_cache: Dict[str, PersonaSchema] = {}
        self._effective_persona_cache: Dict[str, PersonaSchema] = {}
        self._personas_registry: Optional[PersonaRegistry] = None
        self._guild_phrases: Optional[GuildPhrasesSchema] = None
        self._loaded = False
        self._dismiss_words: List[str] = []
        
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all persona definitions and registry data."""
        logger.debug("[Personality] 🎭 Initializing PersonalityManager...")
        try:
            self._load_personas_registry()
            self._load_guild_phrases()
            self._load_dismiss_words()
            self._load_active_personas()
            self._loaded = True
            self._effective_persona_cache.clear()
            logger.debug(f"[Personality] PersonalityManager ready: {len(self._personas_cache)} personas, {len(self._dismiss_words)} dismiss words")
        except Exception as e:
            logger.error(f"[Personality] ❌ Failed to load personality data: {e}")
            self._loaded = False
    
    def _load_personas_registry(self) -> None:
        """Load the personas registry file."""
        if not PERSONAS_REGISTRY_FILE.exists():
            logger.warning(f"[Personality] ⚠️ Personas registry not found at {PERSONAS_REGISTRY_FILE}")
            return
        
        try:
            with open(PERSONAS_REGISTRY_FILE, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
            
            # Validate registry against PersonaRegistry schema
            self._personas_registry = PersonaRegistry(**registry_data)
            logger.debug(f"[Personality] ✅ Loaded personas registry: {len(self._personas_registry.available_personas)} personas")
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"[Personality] ❌ Invalid personas registry: {e}")
            self._personas_registry = None
    
    def _load_guild_phrases(self) -> None:
        """Load guild-level phrase templates."""
        if not GUILD_PHRASES_FILE.exists():
            logger.warning(f"[Personality] ⚠️ Guild phrases file not found at {GUILD_PHRASES_FILE}")
            return
        
        try:
            with open(GUILD_PHRASES_FILE, 'r', encoding='utf-8') as f:
                phrases_data = json.load(f)
            
            # Validate against GuildPhrasesSchema
            self._guild_phrases = GuildPhrasesSchema(**phrases_data)
            logger.debug("[Personality] ✅ Loaded guild-level phrase templates")
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"[Personality] ❌ Invalid guild phrases: {e}")
            self._guild_phrases = None

    def _load_dismiss_words(self) -> None:
        """Load dismiss words (legacy config) to detect end-of-chat triggers.

        While summon triggers live in persona schema, dismiss triggers are
        kept as a simple configurable list for now.
        """
        if not DISMISS_FILE.exists():
            self._dismiss_words = [
                "bye abby", "thanks abby", "thank you abby", "you can go",
                "dismiss", "stop now", "that's all", "see you abby",
            ]
            logger.warning(f"[Personality] ⚠️ dismiss.json not found at {DISMISS_FILE}, using defaults ({len(self._dismiss_words)} words)")
            return
        
        try:
            with open(DISMISS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            words = data.get("dismiss_words", [])
            if isinstance(words, list) and len(words) > 0:
                self._dismiss_words = [str(w).lower() for w in words]
                logger.debug(f"[Personality] ✅ Loaded {len(self._dismiss_words)} dismiss words from dismiss.json")
            else:
                self._dismiss_words = []
                logger.warning(f"[Personality] ⚠️ Invalid or empty dismiss_words in {DISMISS_FILE}")
        except json.JSONDecodeError as e:
            self._dismiss_words = []
            logger.error(f"[Personality] ❌ JSON decode error in dismiss.json: {e}")
        except Exception as e:
            self._dismiss_words = []
            logger.error(f"[Personality] ❌ Error loading dismiss words: {e}")
    
    def _load_active_personas(self) -> None:
        """Load all active personas listed in the registry."""
        if not self._personas_registry:
            logger.warning("Cannot load personas - registry not loaded")
            return
        
        for persona_name in self._personas_registry.active_personas:
            try:
                persona = self._load_persona_from_file(persona_name)
                self._personas_cache[persona_name] = persona
                logger.debug(f"✅ Loaded persona: {persona_name} ({persona.display_name})")
            except Exception as e:
                logger.error(f"❌ Failed to load persona '{persona_name}': {e}")
    
    def _load_persona_from_file(self, persona_name: str) -> PersonaSchema:
        """
        Load a single persona from its JSON file and validate.
        
        Args:
            persona_name: Name of the persona (e.g., 'bunny', 'kiki')
        
        Returns:
            Validated PersonaSchema object
        
        Raises:
            FileNotFoundError: If persona file doesn't exist
            ValidationError: If persona data is invalid
        """
        if not self._personas_registry:
            raise RuntimeError("Personas registry not loaded")
        
        if persona_name not in self._personas_registry.available_personas:
            raise ValueError(f"Persona '{persona_name}' not in registry")
        
        persona_info = self._personas_registry.available_personas[persona_name]
        # Support both Pydantic model and plain dict entries
        file_path = (
            getattr(persona_info, "file", None)
            if hasattr(persona_info, "file")
            else (persona_info.get("file") if isinstance(persona_info, dict) else None)
        )
        if not file_path:
            raise ValueError(f"Persona '{persona_name}' missing 'file' in registry")
        persona_file = PERSONAS_DIR / Path(file_path).name
        
        if not persona_file.exists():
            raise FileNotFoundError(f"Persona file not found: {persona_file}")
        
        with open(persona_file, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)
        
        # Validate against PersonaSchema
        persona = PersonaSchema(**persona_data)
        return persona
    
    def is_loaded(self) -> bool:
        """Check if personality data has been loaded successfully."""
        return self._loaded

    # ===== Conversation Context Construction =====
    def _resolve_active_persona_name(self) -> str:
        """Resolve the current active persona name.

        Reads the value from the shared bot_settings collection when available,
        otherwise falls back to the registry default.
        """
        try:
            # Local import to avoid hard dependency if DB is unavailable
            from abby_core.database.mongodb import get_database

            db = get_database()
            collection = db["bot_settings"]
            active_doc = collection.find_one({"_id": "active_persona"})
            if active_doc and isinstance(active_doc.get("persona"), str):
                return active_doc["persona"]
        except Exception:
            pass

        return self.get_default_persona()
    
    def _apply_memory_budget(self, memory_context: str, max_chars: int = 1200, session_domain: Optional[str] = None) -> str:
        """Apply memory budget with deterministic heuristics.
        
        Tier 1 (Deterministic - no LLM cost):
        - Prioritize facts from same session
        - Prioritize facts matching session domain
        - Apply recency weighting
        
        Args:
            memory_context: Full memory context string
            max_chars: Maximum characters allowed (300 tokens ~= 1200 chars)
            session_domain: Optional domain context (e.g., 'music', 'creative')
        
        Returns:
            Budgeted memory context with deterministic selection
        """
        if len(memory_context) <= max_chars:
            return memory_context
        
        # Parse memory envelope (simple line-based heuristic)
        lines = memory_context.split('\n')
        selected_lines = []
        current_chars = 0
        
        # Priority 1: Domain-matching facts (if domain provided)
        if session_domain:
            domain_lines = [l for l in lines if session_domain.lower() in l.lower()]
            for line in domain_lines:
                if current_chars + len(line) <= max_chars - 100:  # Reserve space
                    selected_lines.append(line)
                    current_chars += len(line) + 1
        
        # Priority 2: Recent facts (typically at top of envelope)
        remaining_lines = [l for l in lines if l not in selected_lines]
        for line in remaining_lines[:10]:  # Take up to 10 recent facts
            if current_chars + len(line) <= max_chars - 50:
                selected_lines.append(line)
                current_chars += len(line) + 1
            else:
                break
        
        result = '\n'.join(selected_lines)
        if len(result) < len(memory_context):
            result += "\n\n[...additional context truncated to fit budget]"
        
        logger.debug(f"[Memory Budget] Domain-aware selection: {len(result)} chars from {len(memory_context)} chars")
        return result
    
    def build_analytical_prompt(self, task_description: str) -> str:
        """Build a boring, task-focused prompt for analytical work.
        
        Used for memory extraction, pattern analysis, etc.
        No persona, no style - just clear instructions.
        
        Args:
            task_description: What the LLM should do
        
        Returns:
            Minimal system prompt for analytical tasks (data comes in user message)
        """
        return (
            "You are an analytical assistant. Extract structured information objectively.\n\n"
            f"Task: {task_description}\n\n"
            "Guidelines:\n"
            "- Be precise and factual\n"
            "- Use minimal words\n"
            "- Output valid JSON when requested\n"
            "- No commentary or personality"
        )
    
    def get_persona(self, persona_name: str, intent: Optional[str] = None) -> Optional[PersonaSchema]:
        """Get a persona by name from cache, with canon overlays applied.
        
        Args:
            persona_name: Name of the persona
            intent: Optional intent context for domain-specific overlays
                   (e.g., 'writing', 'music', 'moderation')
        
        Returns:
            PersonaSchema object with canon overlays applied, or None if not found
        
        Note:
            Canon persona overlays are applied at this layer (PersonalityManager),
            never bypassing to ContextFactory or elsewhere. This ensures a single
            point of truth for effective persona configuration.
        """
        logger.debug(f"[Personality] 🎭 get_persona('{persona_name}', intent={intent})")

        cache_key = f"{persona_name.lower()}::{intent or 'none'}"
        cached = self._effective_persona_cache.get(cache_key)
        if cached:
            logger.debug(f"[Personality] 🔁 Returning cached persona for {cache_key}")
            return cached
        
        # Load base persona from JSON cache
        base_persona = self._personas_cache.get(persona_name)
        if not base_persona:
            logger.warning(f"[Personality] ❌ Persona '{persona_name}' not found in cache")
            return None
        
        logger.debug(f"[Personality] ✅ Loaded base persona '{persona_name}' from JSON")
        
        # Apply canon overlays if available
        try:
            from abby_core.personality import canon_service
            
            # Build domain list: always include 'global', add intent if provided
            domains = ["global"]
            if intent:
                domains.append(intent)

            # Build persona alias list for canonical lookup (handles Abby vs bunny)
            aliases: List[str] = []
            try:
                aliases.append(getattr(base_persona, "name", ""))
                aliases.append(getattr(base_persona, "display_name", ""))
                display_name = getattr(base_persona, "display_name", "")
                if display_name:
                    aliases.append(display_name.split(" ")[0])
                    aliases.append(display_name.split("(")[0].strip())
            except Exception:
                pass
            # Always include global root aliases so shared canon (persona.abby.*) applies to all variants
            aliases.extend(GLOBAL_PERSONA_ROOT_ALIASES)
            aliases = [a for a in aliases if a and a != persona_name]
            aliases = list(dict.fromkeys(aliases))  # dedupe while preserving order
            
            logger.info(f"[Personality] 🔄 Attempting to apply canon overlays with domains: {domains}")
            
            # Retrieve approved persona canon overlays
            overlays = canon_service.get_persona_overlays(
                persona=persona_name,
                domains=domains,
                persona_aliases=aliases,
            )
            
            if overlays:
                logger.info(f"[Personality] 🎨 Applying {len(overlays)} canon overlays to base persona...")
                # Apply overlays to base persona
                effective_persona = self._apply_canon_overlays(base_persona, overlays)
                logger.info(f"[Personality] ✅ Canon overlays applied successfully to '{persona_name}'")
                self._effective_persona_cache[cache_key] = effective_persona
                return effective_persona
            else:
                logger.info(f"[Personality] ℹ️ No canon overlays found - using base persona only")
                self._effective_persona_cache[cache_key] = base_persona
                return base_persona
        
        except Exception as e:
            logger.warning(f"[Personality] ⚠️ Failed to apply canon overlays: {e}")
            # Fall through to return base persona
        
        self._effective_persona_cache[cache_key] = base_persona
        return base_persona
    
    def _apply_canon_overlays(self, base: PersonaSchema, overlays: List[Dict]) -> PersonaSchema:
        """Apply canon overlays to base persona schema.
        
        Overlay merge rules (deterministic):
            voice → system_message_base
            values → behavior framing (future: explicit values field)
            boundaries → limits / tone / refusal rules
            worldview → interpretation framing (future: explicit field)
            narration_style → long-form outputs (future: explicit field)
            prohibitions → hard stops (future: explicit field)
        
        Args:
            base: Base PersonaSchema from JSON
            overlays: List of canon overlay documents
        
        Returns:
            New PersonaSchema with overlays applied
        """
        logger.info(f"[Personality] 🔧 _apply_canon_overlays: Processing {len(overlays)} overlays...")
        
        # Create a mutable copy of base persona data
        persona_dict = base.model_dump()
        
        original_system_message_length = len(persona_dict.get("system_message_base", ""))
        logger.debug(f"[Personality] 📏 Original system_message_base length: {original_system_message_length} chars")
        
        for idx, overlay in enumerate(overlays, 1):
            topic = overlay.get("artifact", {}).get("topic")
            domain = overlay.get("artifact", {}).get("domain", "global")
            content = overlay.get("content", "")
            canonical_id = overlay.get("canonical_id", "unknown")
            
            if not topic or not content:
                logger.warning(f"[Personality] ⚠️ Overlay {idx}/{len(overlays)} missing topic or content - skipping")
                continue
            
            logger.info(f"[Personality] 🎨 Overlay {idx}/{len(overlays)}: {canonical_id}")
            logger.info(f"[Personality]   └─ slot='{topic}' domain='{domain}' content_length={len(content)} chars")
            
            # Apply overlay based on topic/slot
            if topic == "voice":
                # Voice modifications affect system_message_base
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\n{content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'voice' overlay to system_message_base")
            
            elif topic == "values":
                # Values can augment system message for now
                # Future: add explicit 'values' field to PersonaSchema
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\nValues: {content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'values' overlay")
            
            elif topic == "boundaries":
                # Boundaries affect system message and tone
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\nBoundaries: {content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'boundaries' overlay")
            
            elif topic == "worldview":
                # Worldview affects interpretation framing
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\nWorldview: {content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'worldview' overlay")
            
            elif topic == "narration_style":
                # Narration style (domain-specific, e.g., 'book')
                # Future: could affect specific generation params
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\nNarration Style: {content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'narration_style' overlay")
            
            elif topic == "prohibitions":
                # Prohibitions are hard stops
                current = persona_dict.get("system_message_base", "")
                persona_dict["system_message_base"] = f"{current}\n\nProhibitions: {content}".strip()
                logger.info(f"[Personality]   ✅ Applied 'prohibitions' overlay")
            else:
                logger.warning(f"[Personality]   ⚠️ Unknown slot type '{topic}' - skipped")
        
        final_system_message_length = len(persona_dict.get("system_message_base", ""))
        delta = final_system_message_length - original_system_message_length
        logger.info(f"[Personality] 📏 Final system_message_base length: {final_system_message_length} chars (+{delta})")
        
        # Validate and return new PersonaSchema
        logger.info(f"[Personality] ✅ Validating merged persona schema...")
        return PersonaSchema(**persona_dict)
    
    def get_active_personas(self) -> List[str]:
        """
        Get list of active persona names.
        
        Returns:
            List of active persona names
        """
        if self._personas_registry:
            return self._personas_registry.active_personas
        return []
    
    def get_available_personas(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available personas from registry.
        
        Returns:
            Dictionary of persona metadata
        """
        if self._personas_registry:
            # Convert Pydantic models to plain dicts for callers
            result: Dict[str, Dict[str, Any]] = {}
            for name, info in self._personas_registry.available_personas.items():
                if hasattr(info, "model_dump"):
                    result[name] = info.model_dump()
                elif isinstance(info, dict):
                    result[name] = info
                else:
                    result[name] = {"file": str(info)}
            return result
        return {}
    
    def get_default_persona(self) -> str:
        """
        Get the default persona name.
        
        Returns:
            Default persona name
        """
        if self._personas_registry and getattr(self._personas_registry, "default_persona", None):
            return self._personas_registry.default_persona  # type: ignore[return-value]
        return "bunny"
    
    def get_guild_phrases(self) -> Optional[GuildPhrasesSchema]:
        """
        Get guild-level phrase templates.
        
        Returns:
            GuildPhrasesSchema object or None if not loaded
        """
        return self._guild_phrases
    
    def get_welcome_phrase(self, is_owner: bool = False) -> str:
        """
        Get a random welcome phrase for a new user.
        
        Args:
            is_owner: Whether the user is the guild owner
        
        Returns:
            Welcome phrase string
        """
        if not self._guild_phrases:
            return "Welcome!"
        
        key = "owner" if is_owner else "default"
        if key in self._guild_phrases.welcome_templates:
            import random
            phrases = self._guild_phrases.welcome_templates[key]
            return random.choice(phrases)
        
        return "Welcome!"
    
    def get_random_greeting(self) -> str:
        """
        Get a random generic greeting.
        
        Returns:
            Greeting string
        """
        if self._guild_phrases:
            import random
            return random.choice(self._guild_phrases.generic_greetings)
        return "Hello!"

    # ===== Persona UX Helpers =====
    def get_active_persona_name(self) -> str:
        """Public accessor for current active persona name."""
        return self._resolve_active_persona_name()

    def get_processing_message(self, persona_name: Optional[str] = None) -> str:
        """Get a random processing message for the given persona with emojis injected."""
        name = persona_name or self.get_default_persona()
        p = self.get_persona(name)
        if p and p.response_patterns and p.response_patterns.processing_messages:
            import random
            message = random.choice(p.response_patterns.processing_messages)
            # Inject emojis from emoji.json
            return self.inject_emojis(message)
        return "Working on it..."

    def get_greeting_for_persona(self, persona_name: Optional[str] = None, formal: bool = False, user_role: str = "member", is_bot_creator: bool = False) -> str:
        """
        Get a role-specific greeting from persona welcome configuration or response patterns.
        
        Args:
            persona_name: Persona to get greeting from (defaults to active)
            formal: Whether to use formal greetings (legacy response_patterns only)
            user_role: User's role level ("owner", "admin", "moderator", "member")
            is_bot_creator: Whether user is the bot creator/developer
            
        Returns:
            Random greeting appropriate for the user's role
        """
        import random
        
        name = persona_name or self.get_default_persona()
        p = self.get_persona(name)
        
        if not p:
            return self.get_random_greeting()
        
        # Priority 1: Bot creator gets special treatment
        if is_bot_creator and p.welcome and p.welcome.bot_creator:
            return random.choice(p.welcome.bot_creator)
        
        # Priority 2: Role-based greetings from welcome config
        if p.welcome:
            role_greetings = None
            
            if user_role == "owner" and p.welcome.owner:
                role_greetings = p.welcome.owner
            elif user_role == "admin" and p.welcome.admin:
                role_greetings = p.welcome.admin
            elif user_role == "moderator" and p.welcome.moderator:
                role_greetings = p.welcome.moderator
            elif p.welcome.default:
                role_greetings = p.welcome.default
            
            if role_greetings:
                return random.choice(role_greetings)
        
        # Priority 3: Legacy response_patterns greetings
        key = "formal" if formal else "casual"
        if p.response_patterns and p.response_patterns.greetings.get(key):
            return random.choice(p.response_patterns.greetings[key])
        
        # Fallback to guild generic greetings
        return self.get_random_greeting()

    def get_farewell_for_persona(self, persona_name: Optional[str] = None, user_role: str = "member", is_bot_creator: bool = False) -> str:
        """
        Get a role-specific farewell from persona farewell configuration.
        
        Args:
            persona_name: Persona to get farewell from (defaults to active)
            user_role: User's role level ("owner", "admin", "moderator", "member")
            is_bot_creator: Whether user is the bot creator/developer
            
        Returns:
            Random farewell appropriate for the user's role
        """
        import random
        
        name = persona_name or self.get_default_persona()
        p = self.get_persona(name)
        
        if not p:
            # Fallback farewell
            return "See you later!"
        
        # Priority 1: Bot creator gets special treatment
        if is_bot_creator and p.farewell and p.farewell.bot_creator:
            return random.choice(p.farewell.bot_creator)
        
        # Priority 2: Role-based farewells from farewell config
        if p.farewell:
            role_farewells = None
            
            if user_role == "owner" and p.farewell.owner:
                role_farewells = p.farewell.owner
            elif user_role == "admin" and p.farewell.admin:
                role_farewells = p.farewell.admin
            elif user_role == "moderator" and p.farewell.moderator:
                role_farewells = p.farewell.moderator
            elif p.farewell.default:
                role_farewells = p.farewell.default
            
            if role_farewells:
                return random.choice(role_farewells)
        
        # Fallback farewell
        return "See you later!"

    def check_summon_trigger(self, text: str, persona_name: Optional[str] = None) -> bool:
        """Check if the message text contains a summon trigger for persona."""
        name = persona_name or self.get_active_persona_name()
        p = self.get_persona(name)
        if not p or not p.summon or not p.summon.triggers:
            return False
        lowered = text.lower()
        return any(trig.lower() in lowered for trig in p.summon.triggers)

    def check_dismiss_trigger(self, text: str) -> bool:
        """
        Check if message signals a polite dismissal/end of chat.
        Uses word boundary matching to avoid false positives.
        """
        import re
        
        if not self._dismiss_words:
            logger.warning("[Personality] No dismiss words loaded - cannot detect dismissals")
            return False
        
        lowered = text.lower().strip()
        matched_words = []
        
        for dismiss_word in self._dismiss_words:
            # Use word boundaries to avoid substring matches
            # e.g., "is" should not match in "what is the sky"
            # but should match exact word "is" or at start/end of message
            pattern = r'\b' + re.escape(dismiss_word) + r'\b'
            if re.search(pattern, lowered):
                matched_words.append(dismiss_word)
        
        result = len(matched_words) > 0
        
        logger.debug(
            "[Personality] Dismiss check",
            extra={"text": text, "dismiss_triggered": result, "matched_words": matched_words if matched_words else "none"}
        )
        return result
    
    def get_random_farewell(self) -> str:
        """
        Get a random farewell message.
        
        Returns:
            Farewell string
        """
        if self._guild_phrases:
            import random
            return random.choice(self._guild_phrases.farewell_messages)
        return "Goodbye!"
    
    def get_usage_gate_message(self, reason: str) -> str:
        """
        Get a persona-specific usage gate message based on the reason.
        Emoji placeholders are automatically injected from emoji.json.
        
        Args:
            reason: Gate reason ('turn_limit_reached', 'session_expired', 'cooldown_active', 'burst_limit_hit')
            
        Returns:
            Persona-themed message with emojis injected for the gate
        """
        import random
        
        # Get active persona
        persona = self.get_persona(self.get_active_persona_name())
        if not persona or not persona.response_patterns:
            # Fallback messages
            fallbacks = {
                "turn_limit_reached": "Let's pause here for now! {emoji:bunny_smile}",
                "session_expired": "Our conversation has drifted a bit. Ready for something new? {emoji:leaf}",
                "cooldown_active": "Give me a moment to catch my breath... {emoji:leaf}",
                "burst_limit_hit": "Whoa there! Let's slow down a bit... {emoji:bunny_smile}",
            }
            message = fallbacks.get(reason, "Hold on a second!")
            return self.inject_emojis(message)
        
        # Map reason to response pattern field
        field_map = {
            "turn_limit_reached": "turn_limit_messages",
            "session_expired": "session_expired_messages",
            "cooldown_active": "cooldown_messages",
            "burst_limit_hit": "burst_limit_messages",
        }
        
        field_name = field_map.get(reason)
        if field_name and hasattr(persona.response_patterns, field_name):
            messages = getattr(persona.response_patterns, field_name)
            if messages:
                message = random.choice(messages)
                # Inject emojis from emoji.json into the message
                return self.inject_emojis(message)
        
        # Fallback
        return "Hold on a second!"
    
    def build_static_prompt(
        self,
        persona: PersonaSchema,
        guild_name: str = "Breeze Club",
        user_level: str = "member",
        is_owner: bool = False,
        user_mention: str = "@user",
        max_response_length: int = 500,
        user_role: str = "member"
    ) -> str:
        """Build static portion of system prompt (cached per session).
        
        Static parts include:
        - Persona core
        - Guild context
        - Behavioral boundaries
        - User context (role, ownership)
        
        Args:
            persona: PersonaSchema object
            guild_name: Name of the Discord guild
            user_level: User's level (e.g., "member", "gold", "diamond")
            is_owner: Whether user is guild owner
            user_mention: User mention string
            max_response_length: Max characters for response
            user_role: User's role level ("owner", "admin", "moderator", "member")
        
        Returns:
            Static system prompt string (no memory/RAG/dynamic content)
        """
        if not persona.system_prompt_template:
            return persona.system_message_base
        
        template = persona.system_prompt_template
        boundaries = persona.personality_boundaries
        
        # Build static context only
        context = {
            "persona_display_name": persona.display_name,
            "description": persona.description,
            "system_message_base": persona.system_message_base,
            "style_hints": persona.style_hints or "Be natural and helpful.",
            "user_level": user_level,
            "is_owner": "yes" if is_owner else "no",
            "user_mention": user_mention,
            "max_response_length": max_response_length,
            "personality_tone": (boundaries.personality_tone if boundaries else "friendly"),
            "restricted_topics": ", ".join(boundaries.restricted_topics if boundaries else [])
        }
        
        try:
            static_prompt = template.format(**context)
        except KeyError as e:
            logger.warning(f"⚠️  Missing context variable in template: {e}. Using base message.")
            static_prompt = persona.system_message_base
        
        return static_prompt
    
    def build_system_prompt(
        self,
        persona: PersonaSchema,
        guild_name: str = "Breeze Club",
        user_level: str = "member",
        is_owner: bool = False,
        user_mention: str = "@user",
        available_tools: Optional[List[str]] = None,
        chat_history: str = "",
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None,
        max_response_length: int = 500,
        is_final_turn: bool = False,
        user_role: str = "member",
        is_bot_creator: bool = False,
        static_prompt: Optional[str] = None,
        turn_number: int = 1,
        turn_phase: Optional[str] = None,
        system_state: Optional[Dict[str, Any]] = None,
        devlog_context: Optional[str] = None,
    ) -> str:
        """
        Build a complete system prompt for LLM by combining static + dynamic parts.
        
        **Phase 2 Refactor:** Delegates to llm/prompt_builder.py for assembly logic.
        This keeps personality/ focused on persona loading, while llm/ handles prompt construction.
        
        Args:
            persona: PersonaSchema object
            guild_name: Name of the Discord guild
            user_level: User's level (e.g., "member", "gold", "diamond")
            is_owner: Whether user is guild owner
            user_mention: User mention string
            available_tools: List of available tools
            chat_history: Recent chat history for context (deprecated, kept for compat)
            max_response_length: Max characters for response
            is_final_turn: Whether this is the final allowed turn in the conversation
            user_role: User's role level ("owner", "admin", "moderator", "member")
            is_bot_creator: Whether user is the bot creator/developer
            static_prompt: Pre-built static prompt (if cached), otherwise builds fresh
            turn_number: Current turn number in the session (1-indexed)
            turn_phase: Optional turn phase hint (greeting|question|answer|followup|closure)
            system_state: Optional system state dict with active states and merged effects
            devlog_context: Optional formatted changelog summary (injected only for meta questions)
        
        Returns:
            Complete system prompt string
        """
        # Build or use cached static prompt
        if static_prompt is None:
            static_prompt = self.build_static_prompt(
                persona=persona,
                guild_name=guild_name,
                user_level=user_level,
                is_owner=is_owner,
                user_mention=user_mention,
                max_response_length=max_response_length,
                user_role=user_role
            )
        
        # Delegate to prompt_builder for assembly (Phase 2 architectural improvement)
        from abby_core.llm.prompt_builder import get_prompt_builder
        
        prompt_builder = get_prompt_builder()
        return prompt_builder.build_system_prompt(
            persona=persona,
            static_prompt=static_prompt,
            guild_name=guild_name,
            turn_number=turn_number,
            memory_context=memory_context,
            rag_context=rag_context,
            system_state=system_state,
            devlog_context=devlog_context,
            is_final_turn=is_final_turn,
            turn_phase=turn_phase,
            user_role=user_role,
            is_bot_creator=is_bot_creator,
        )

    @staticmethod
    def _map_expected_behavior(turn_phase: str, is_final_turn: bool) -> str:
        """Map turn phase to a simple expected behavior hint for the model."""
        if is_final_turn:
            return "graceful_closure"
        behavior_map = {
            "greeting": "greet_and_invite_context",
            "question": "answer_and_invite_followup",
            "answer": "acknowledge_and_continue",
            "closure": "acknowledge_and_close",
        }
        return behavior_map.get(turn_phase, "continue_conversation")
    
    def get_persona_actions(self, persona_name: str) -> List[str]:
        """
        Get list of action messages for a persona (e.g., '*hops around*').
        
        Args:
            persona_name: Name of the persona
        
        Returns:
            List of action strings
        """
        persona = self.get_persona(persona_name)
        if persona and persona.response_patterns:
            return persona.response_patterns.actions or []
        return []
    
    def get_persona_processing_messages(self, persona_name: str) -> List[str]:
        """
        Get list of processing messages for a persona with emojis injected.
        
        Args:
            persona_name: Name of the persona
        
        Returns:
            List of processing message strings with emojis injected
        """
        persona = self.get_persona(persona_name)
        if persona and persona.response_patterns:
            messages = persona.response_patterns.processing_messages or []
            # Inject emojis into each message
            return [self.inject_emojis(msg) for msg in messages]
        return []
    
    def inject_emojis(self, text: str, persona_name: Optional[str] = None) -> str:
        """
        Replace emoji placeholders in text with actual emoji values from emoji.json.
        
        Supports two placeholder formats:
        - {emoji:animations.idle}    → Full path lookup
        - {emoji:wave}               → Quick lookup (searches all categories)
        
        Args:
            text: Text containing {emoji:key} placeholders
            persona_name: Optional persona name (for context, not used yet)
        
        Returns:
            Text with placeholders replaced by actual emoji values
        
        Example:
            "My bunny brain is full! {emoji:wave}" → "My bunny brain is full! <a:leafwave:...>"
            "Give me a moment {emoji:unicode.leaf}" → "Give me a moment 🌿"
        """
        if not text:
            return text
        
        import re
        
        # Load emoji data
        emoji_data = {}
        if EMOJI_FILE.exists():
            try:
                with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
                    emoji_data = json.load(f)
                    logger.debug(f"[Personality] Loaded emoji.json with categories: {list(emoji_data.keys())}")
            except Exception as e:
                logger.warning(f"[Personality] Could not load emoji.json: {e}")
                return text
        else:
            logger.warning(f"[Personality] emoji.json not found at {EMOJI_FILE}")
            return text
        
        # Pattern: {emoji:key} or {emoji:category.key}
        pattern = r'\{emoji:([^}]+)\}'
        
        def replace_emoji(match):
            key = match.group(1)
            logger.debug(f"[Personality] Looking up emoji: {key}")
            
            # Try full path first (e.g., "animations.idle")
            if '.' in key:
                parts = key.split('.', 1)
                category, subkey = parts[0], parts[1]
                if category in emoji_data and isinstance(emoji_data[category], dict):
                    result = emoji_data[category].get(subkey)
                    if result:
                        logger.debug(f"[Personality] Found {key} -> {result}")
                        return result
            
            # Try quick lookup (search all categories)
            for category in emoji_data:
                if isinstance(emoji_data[category], dict) and key in emoji_data[category]:
                    result = emoji_data[category][key]
                    logger.debug(f"[Personality] Found {key} in {category} -> {result}")
                    return result
            
            # Not found, return placeholder unchanged
            logger.debug(f"[Personality] Emoji not found: {key}")
            return match.group(0)
        
        result = re.sub(pattern, replace_emoji, text)
        return result
    
    def reload(self) -> bool:
        """
        Reload all personality data (for hot-reload capability).
        
        Returns:
            True if reload successful, False otherwise
        """
        logger.info("🔄 Reloading personality data...")
        self._personas_cache.clear()
        self._effective_persona_cache.clear()
        self._personas_registry = None
        self._guild_phrases = None
        self._dismiss_words = []
        self._load_all()
        return self._loaded


# Global instance
_instance: Optional[PersonalityManager] = None


def get_personality_manager() -> PersonalityManager:
    """
    Get or create the global PersonalityManager instance.
    
    Returns:
        PersonalityManager instance
    """
    global _instance
    if _instance is None:
        _instance = PersonalityManager()
    return _instance


__all__ = [
    "PersonalityManager",
    "get_personality_manager",
]
