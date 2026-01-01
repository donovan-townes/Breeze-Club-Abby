"""
Abby Personality System
Centralized personality, trigger words, and response patterns.
Multi-persona support for different bot characters (bunny/Abby, kiki/Kiki, etc.)
"""

from .config import PersonalityConfig, get_personality_config, reload_persona

__all__ = ['PersonalityConfig', 'get_personality_config', 'reload_persona']
