"""Memory relevance scoring and formatting for RAG layer.

Extracted from context_factory.py to properly separate concerns:
- Context factory: Assembles persona, overlay, guild context
- Memory formatter (this module): Scores and formats memory facts for relevance

Architecture Benefit:
- RAG layer owns memory relevance logic
- Context factory focuses on prompt assembly
- Memory scoring reusable across different contexts
"""

from typing import Dict, Optional, List, Any
import logging

logger = logging.getLogger(__name__)


# Domain keywords that suggest memory relevance
# Keywords should be specific to avoid false positives (e.g., "color" too generic)
DOMAIN_KEYWORDS = {
    "music": ["music", "song", "track", "mix", "production", "audio", "beat", "melody"],
    "art": ["art", "draw", "paint", "sketch", "design", "illustration", "artwork"],
    "writing": ["write", "story", "book", "novel", "chapter", "draft", "edit"],
    "coding": ["code", "program", "script", "bug", "function", "api", "debug"],
    "gaming": ["game", "play", "stream", "gaming", "level", "quest", "character"],
}

# Very small stopword list to avoid scoring on filler words.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than",
    "is", "are", "was", "were", "be", "being", "been",
    "on", "in", "at", "to", "of", "for", "with", "by", "about",
    "this", "that", "these", "those", "it", "its", "as", "so", "do",
}


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length.
    
    Uses a conservative 4 chars/token ratio. Can be swapped with tiktoken later.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    import math
    return math.ceil(len(text) / 4)


def _sanitize_rag_fact(fact_text: str) -> str:
    """Sanitize RAG fact content to prevent prompt injection attacks.
    
    Security boundary: RAG facts sourced from external ingestion (Discord messages,
    documents, web scraping) may contain malicious prompt injection attempts.
    This function strips dangerous patterns before insertion into LLM prompts.
    
    Protections:
    - Strip role declarations (system:, user:, assistant:)
    - Strip code blocks (```...```) to prevent execution instructions
    - Strip angle-bracketed directives (<|system|>, <instruction>)
    - Truncate to prevent token overflow attacks
    
    Args:
        fact_text: Raw fact text from RAG ingestion
        
    Returns:
        Sanitized fact text safe for LLM prompt injection
    """
    import re
    
    if not fact_text:
        return ""
    
    # Strip role declarations (system:, user:, assistant:, human:, ai:)
    sanitized = re.sub(
        r'\b(system|user|assistant|human|ai)\s*:\s*',
        '',
        fact_text,
        flags=re.IGNORECASE
    )
    
    # Strip code blocks (both ``` and backtick variants)
    sanitized = re.sub(r'```.*?```', '[code block removed]', sanitized, flags=re.DOTALL)
    sanitized = re.sub(r'`[^`]+`', '[code removed]', sanitized)
    
    # Strip angle-bracketed directives (<|system|>, <instruction>, etc.)
    sanitized = re.sub(r'<\|[^|]+\|>', '', sanitized)
    sanitized = re.sub(r'</?instruction>', '', sanitized, flags=re.IGNORECASE)
    
    # Strip excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Truncate to prevent overflow (500 chars = ~125 tokens max per fact)
    if len(sanitized) > 500:
        sanitized = sanitized[:497] + "..."
    
    return sanitized


def format_memory_for_llm(
    envelope: Dict[str, Any],
    user_message: str,
    max_tokens: int = 300,
    intent: Optional[str] = None,
    min_relevance_score: int = 20,
) -> Optional[str]:
    """Format memory envelope for LLM with token budget and relevance scoring.
    
    Applies deterministic relevance scoring without embeddings:
    - Domain keyword matching
    - Intent-based filtering
    - Recency boosting
    - Token budget constraints
    - Minimum relevance threshold (skips memory if no facts score high enough)
    
    Args:
        envelope: Raw memory envelope from TDOS Memory
        user_message: Current user message for keyword matching
        max_tokens: Token budget for memory (default 300 = ~1200 chars)
        intent: Optional intent classification
        min_relevance_score: Minimum score required for best fact (default 20)
            Scoring: domain match +30, keyword overlap +10/word (max 30), confidence +15
        
    Returns:
        Formatted memory string or None if no relevant facts meet threshold
    """
    if not envelope:
        return None
    
    # Extract facts from envelope
    facts = envelope.get('relational', {}).get('memorable_facts', [])
    if not facts:
        return None
    
    # Normalize user message for keyword matching (stopword-filtered)
    message_lower = user_message.lower()
    message_keywords = {w for w in message_lower.split() if w and w not in STOPWORDS}
    
    # Score each fact for relevance
    scored_facts = []
    for fact in facts:
        score = 0
        fact_text = fact.get('text', '')
        fact_lower = fact_text.lower()
        
        # Domain matching (+30 points)
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in fact_lower for kw in keywords):
                if any(kw in message_lower for kw in keywords):
                    score += 30
                    break
        
        # Keyword overlap (+10 per matching word, max 30) with stopword filtering
        fact_words = {w for w in fact_lower.split() if w and w not in STOPWORDS}
        overlap = len(message_keywords & fact_words)
        score += min(overlap * 10, 30)
        
        # Confidence boost (+5 to +15)
        confidence = fact.get('confidence', 0.5)
        score += int(confidence * 15)
        
        # Recency (newer facts slightly preferred, +0 to +10)
        # TODO: Add timestamp-based recency when available
        
        scored_facts.append((score, fact))
    
    # Sort by score descending
    scored_facts.sort(key=lambda x: x[0], reverse=True)
    
    # Check if best fact meets minimum relevance threshold
    if not scored_facts or scored_facts[0][0] < min_relevance_score:
        logger.info(
            f"[memory_format] No relevant facts found "
            f"(best_score={scored_facts[0][0] if scored_facts else 0}, "
            f"threshold={min_relevance_score})"
        )
        return None

    # Log top scores for observability
    top_samples = [
        {
            "score": score,
            "preview": fact.get("text", "")[:80],
            "confidence": fact.get("confidence", 0.0),
        }
        for score, fact in scored_facts[:5]
    ]
    above_threshold = sum(1 for score, _ in scored_facts if score >= min_relevance_score)
    logger.info(
        f"[memory_format] Scored facts top5={top_samples} "
        f"above_threshold={above_threshold}/{len(scored_facts)} "
        f"threshold={min_relevance_score}"
    )
    
    # Build memory string within token budget
    max_chars = max_tokens * 4  # Conservative estimate
    
    # Start with identity and preferences
    memory_lines = []
    user_name = envelope.get('identity', {}).get('username', 'user')
    domains = envelope.get('identity', {}).get('domains', [])
    preferences = envelope.get('identity', {}).get('preferences', {})
    
    header = f"User: {user_name}"
    if domains:
        header += f"\nDomains: {', '.join(domains)}"
    if preferences:
        prefs_str = ', '.join([f"{k}: {v}" for k, v in preferences.items()])
        header += f"\nPreferences: {prefs_str}"
    
    memory_lines.append(header)
    current_chars = len(header)
    
    # Add scored facts until budget exhausted
    memory_lines.append("Known facts:")
    current_chars += 12
    
    facts_added = 0
    for score, fact in scored_facts:
        # Skip facts below relevance threshold
        if score < min_relevance_score:
            logger.debug(
                f"[memory_format] Skipping fact score={score} (below threshold={min_relevance_score})"
            )
            continue
        
        # SECURITY: Sanitize fact text to prevent RAG injection attacks
        raw_fact_text = fact.get('text', '')
        sanitized_text = _sanitize_rag_fact(raw_fact_text)
        
        fact_text = f"  ? {sanitized_text} (confidence: {int(fact.get('confidence', 0.5) * 100)}%)"
        fact_chars = len(fact_text) + 1  # +1 for newline
        
        if current_chars + fact_chars > max_chars:
            break
        
        memory_lines.append(fact_text)
        current_chars += fact_chars
        facts_added += 1

        logger.debug(
            f"[memory_format] Added fact score={score} "
            f"remaining_chars={max_chars - current_chars}"
        )
        
        # Cap at reasonable fact count even if budget allows more
        if facts_added >= 10:
            break
    
    if facts_added == 0:
        # No facts fit the budget or scored high enough
        logger.info(f"[memory_format] No relevant facts within budget (max_tokens={max_tokens})")
        return None
    
    formatted = "\n".join(memory_lines)
    logger.info(f"[memory_format] Formatted {facts_added} facts ({current_chars} chars, ~{_estimate_tokens(formatted)} tokens)")
    
    return formatted
