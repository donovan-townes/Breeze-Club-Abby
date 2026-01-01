"""
Abby Personality Configuration System
Manages trigger words, response patterns, and persona behaviors.
"""

import json
import os
import random
from typing import List, Dict, Any, Optional
from pathlib import Path
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

# Default configuration directory
PERSONALITY_DIR = Path(__file__).parent


class PersonalityConfig:
    """Centralized personality configuration manager with multi-persona support."""
    
    def __init__(self, persona: str = "bunny", config_dir: Optional[Path] = None):
        """
        Initialize personality configuration.
        
        Args:
            persona: Persona name (e.g., 'bunny', 'kiki'). Defaults to 'bunny'
            config_dir: Optional custom directory for config files. If not provided,
                       uses PERSONALITY_DIR / persona
        """
        self.persona_name = persona
        
        # Set config directory based on persona
        if config_dir is None:
            self.config_dir = PERSONALITY_DIR / persona
        else:
            self.config_dir = config_dir
        
        self._summon_words: Optional[List[str]] = None
        self._dismiss_words: Optional[List[str]] = None
        self._response_patterns: Optional[Dict[str, Any]] = None
        self._emojis: Optional[Dict[str, str]] = None
        
        logger.info(f"[🎭] Personality config initialized for '{persona}' from {self.config_dir}")
    
    @property
    def summon_words(self) -> List[str]:
        """Get list of words/phrases that summon Abby."""
        if self._summon_words is None:
            self._summon_words = self._load_json_file("summon.json", "summon_words", [])
        return self._summon_words
    
    @property
    def dismiss_words(self) -> List[str]:
        """Get list of words/phrases that dismiss Abby."""
        if self._dismiss_words is None:
            self._dismiss_words = self._load_json_file("dismiss.json", "dismiss_words", [])
        return self._dismiss_words
    
    @property
    def response_patterns(self) -> Dict[str, Any]:
        """Get response patterns configuration."""
        if self._response_patterns is None:
            self._response_patterns = self._load_json_file("response_patterns.json", default={
                "bunny_actions": [
                    "*hops around*",
                    "*munches on carrot*",
                    "*exploring the outdoors*",
                    "*happily hops off*",
                    "*hops back happily*"
                ],
                "greetings": [
                    "Hey there!",
                    "Greetings!",
                    "Hello!",
                    "Hi there!"
                ],
                "farewells": [
                    "So happy to help!",
                    "Take care!",
                    "See you soon!",
                    "Happy to assist!"
                ]
            })
        return self._response_patterns
    
    @property
    def emojis(self) -> Dict[str, str]:
        """Get custom emoji configuration."""
        if self._emojis is None:
            emoji_data = self._load_json_file("emoji.json", default={})
            # Flatten nested emoji structure for easier access
            self._emojis = {}
            if "emojis" in emoji_data:
                self._emojis.update(emoji_data["emojis"])
            if "discord_animated" in emoji_data:
                self._emojis.update(emoji_data["discord_animated"])
        return self._emojis
    
    def get_emoji(self, key: str, default: str = "") -> str:
        """
        Get a specific emoji by key.
        
        Args:
            key: Emoji identifier (e.g., 'abby_run', 'abby_idle')
            default: Default value if emoji not found
            
        Returns:
            Emoji string or default
        """
        return self.emojis.get(key, default)
    
    def get_random_bunny_action(self) -> str:
        """Get a random bunny action phrase."""
        actions = self.response_patterns.get("bunny_actions", ["*hops around*"])
        return random.choice(actions)
    
    def get_random_processing_message(self, emoji: str = "") -> str:
        """
        Get a random processing message.
        
        Args:
            emoji: Optional emoji to prepend
            
        Returns:
            Processing message string
        """
        messages = self.response_patterns.get("processing_messages", ["Working on it..."])
        message = random.choice(messages)
        return f"{emoji} {message}" if emoji else message
    
    def get_random_greeting(self, user_name: str, emoji: str = "", include_action: bool = True) -> str:
        """
        Get a random greeting message.
        
        Args:
            user_name: User's display name or mention
            emoji: Optional emoji to prepend
            include_action: Whether to include bunny action
            
        Returns:
            Formatted greeting string
        """
        templates = self.response_patterns.get("greetings", {}).get("full_templates", [
            "Hey {name}! {action}",
            "Hello {name}! {action}"
        ])
        template = random.choice(templates)
        
        # Get random action if requested
        action = self.get_random_bunny_action() if include_action else ""
        
        # Format greeting
        greeting = template.format(name=user_name, action=action)
        
        return f"{emoji} {greeting}" if emoji else greeting
    
    def _load_json_file(self, filename: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Load a JSON configuration file.
        
        Args:
            filename: Name of JSON file in config directory
            key: Optional key to extract from JSON object
            default: Default value if file not found or key missing
            
        Returns:
            Loaded configuration data
        """
        file_path = self.config_dir / filename
        
        try:
            if not file_path.exists():
                logger.warning(f"[⚠️] Config file not found: {file_path}, using defaults")
                return default
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract specific key if provided
            if key:
                return data.get(key, default)
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"[❌] Failed to parse {filename}: {e}")
            return default
        except Exception as e:
            logger.error(f"[❌] Error loading {filename}: {e}")
            return default
    
    def check_summon_trigger(self, message: str) -> bool:
        """
        Check if message contains summon trigger word.
        
        Args:
            message: User message text (lowercased)
            
        Returns:
            True if summon word detected
        """
        message_lower = message.lower().strip()
        return any(word in message_lower for word in self.summon_words)
    
    def check_dismiss_trigger(self, message: str) -> bool:
        """
        Check if message contains dismiss trigger word.
        
        Args:
            message: User message text (lowercased)
            
        Returns:
            True if dismiss word detected
        """
        message_lower = message.lower().strip()
        return any(word == message_lower for word in self.dismiss_words)
    
    def reload(self):
        """Reload all configuration files from disk."""
        self._summon_words = None
        self._dismiss_words = None
        self._response_patterns = None
        self._emojis = None
        logger.info(f"[🔄] Persona '{self.persona_name}' configuration reloaded")


# Singleton instances - one per persona
_personality_configs: Dict[str, PersonalityConfig] = {}


def get_personality_config(persona: str = "bunny") -> PersonalityConfig:
    """
    Get the personality configuration instance for a specific persona.
    
    Args:
        persona: Persona name (e.g., 'bunny', 'kiki'). Defaults to 'bunny'
        
    Returns:
        PersonalityConfig instance for the specified persona
    """
    global _personality_configs
    if persona not in _personality_configs:
        _personality_configs[persona] = PersonalityConfig(persona=persona)
    return _personality_configs[persona]


def reload_persona(persona: str):
    """Reload configuration for a specific persona without restarting bot."""
    global _personality_configs
    if persona in _personality_configs:
        _personality_configs[persona].reload()
        logger.info(f"[🔄] Persona '{persona}' configuration reloaded")

