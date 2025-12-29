# abby-core package initialization
"""
Abby Core - Domain Logic Layer

This package contains all domain logic with zero Discord/UI dependencies.
Designed for reuse across multiple adapters (Discord, web, TDOS CLI).

Subpackages:
- llm: LLM abstraction (Ollama + OpenAI providers)
- rag: RAG handler (Chroma/Qdrant vector store)
- economy: XP and economy logic
- moderation: Content moderation decision logic
- utils: TDOS events, encryption, MongoDB, logging
"""
