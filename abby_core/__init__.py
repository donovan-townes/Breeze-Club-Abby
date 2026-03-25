# abby_core package initialization
"""
Abby Core - Domain Logic Layer

This package contains all domain logic with zero Discord/UI dependencies.
Designed for reuse across multiple adapters (Discord, web, TDOS CLI).

Subpackages:
- database: MongoDB operations and schemas
- llm: LLM abstraction (Ollama + OpenAI providers)
- rag: RAG handler (Chroma/Qdrant vector store)
- economy: XP and currency systems
- personality: Persona configuration
- security: Encryption utilities
- observability: Logging and telemetry
"""

# Export submodules for convenient imports
from abby_core import database, llm, rag, economy, personality, security, observability

__all__ = [
    "database",
    "llm",
    "rag",
    "economy",
    "personality",
    "security",
    "observability",
]
