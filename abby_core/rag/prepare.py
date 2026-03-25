"""
RAG Text Preparation Module

Converts arbitrary input text into canonical RAG format:
- Strips markdown and formatting
- Removes emojis and non-semantic noise
- Normalizes whitespace
- Enforces structure (title, scope, content)

This module is TDOS-core — agent-agnostic and reusable.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def strip_markdown(text: str) -> str:
    """Remove markdown formatting while preserving content."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    
    # Remove headers (but keep the text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    
    # Remove bold, italic, strikethrough
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    
    # Remove links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    
    # Remove images ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", text)
    
    # Remove horizontal rules
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*{3,}$", "", text, flags=re.MULTILINE)
    
    # Remove blockquotes
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    
    return text


def remove_emojis(text: str) -> str:
    """Remove emoji and custom Discord emoji patterns."""
    # Discord custom emojis <:name:id> or <a:name:id>
    text = re.sub(r"<a?:\w+:\d+>", "", text)
    
    # Unicode emoji ranges (comprehensive)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # extended symbols
        "]+", 
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)
    
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace and normalize line breaks."""
    # Replace multiple spaces with single space
    text = re.sub(r" +", " ", text)
    
    # Replace multiple newlines with max two (preserve paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove trailing/leading whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    
    # Final strip
    return text.strip()


def convert_bullets_to_sentences(text: str) -> str:
    """Convert bullet points to complete sentences for better embedding."""
    lines = text.split("\n")
    processed = []
    
    for line in lines:
        # Match bullet patterns: -, *, •, 1., etc.
        match = re.match(r"^[\-\*\•\d]+[\.\)]\s*(.+)$", line.strip())
        if match:
            content = match.group(1).strip()
            # Ensure it ends with punctuation
            if content and content[-1] not in ".!?":
                content += "."
            processed.append(content)
        else:
            processed.append(line)
    
    return "\n".join(processed)


def enforce_canonical_structure(
    text: str, 
    title: Optional[str] = None, 
    scope: Optional[str] = None
) -> str:
    """
    Enforce canonical RAG format with headers.
    
    Structure:
        TITLE: {title}
        SCOPE: {scope}
        
        CONTENT:
        {cleaned text}
    
    Args:
        text: Cleaned body text
        title: Document title (optional, extracted if present)
        scope: Document scope/category (optional)
    
    Returns:
        Structured document string
    """
    parts = []
    
    # Add title if provided
    if title:
        parts.append(f"TITLE: {title.strip()}")
    
    # Add scope if provided
    if scope:
        parts.append(f"SCOPE: {scope.strip()}")
    
    # Add separator if we have headers
    if parts:
        parts.append("")
        parts.append("CONTENT:")
    
    # Add cleaned content
    parts.append(text)
    
    return "\n".join(parts)


def prepare_rag_text(
    text: str,
    title: Optional[str] = None,
    scope: Optional[str] = None,
    preserve_bullets: bool = False
) -> str:
    """
    Master function: convert any input to canonical RAG format.
    
    Pipeline:
        1. Strip markdown
        2. Remove emojis
        3. Normalize whitespace
        4. Convert bullets (optional)
        5. Enforce structure
    
    Args:
        text: Raw input text (can be markdown, chat logs, etc.)
        title: Document title
        scope: Document category/scope
        preserve_bullets: If True, keep bullet structure; else convert to sentences
    
    Returns:
        Clean, canonical RAG text ready for chunking
    
    Example:
        >>> raw = "# Rules\\n- Be nice\\n- No spam 🚫"
        >>> clean = prepare_rag_text(raw, title="Community Rules", scope="guidelines")
        >>> print(clean)
        TITLE: Community Rules
        SCOPE: guidelines
        
        CONTENT:
        Rules
        Be nice.
        No spam.
    """
    if not text or not text.strip():
        logger.warning("[RAG Prepare] Empty text provided")
        return ""
    
    # Pipeline
    text = strip_markdown(text)
    text = remove_emojis(text)
    text = normalize_whitespace(text)
    
    if not preserve_bullets:
        text = convert_bullets_to_sentences(text)
    
    text = enforce_canonical_structure(text, title=title, scope=scope)
    
    logger.debug("[RAG Prepare] Prepared %d chars -> %d chars", len(text), len(text))
    
    return text


def validate_prepared_text(text: str, max_chunk_words: int = 200) -> dict:
    """
    Validate prepared text for RAG ingestion.
    
    Returns:
        {
            "valid": bool,
            "word_count": int,
            "estimated_chunks": int,
            "warnings": List[str]
        }
    """
    warnings = []
    
    if not text.strip():
        warnings.append("Empty text")
        return {
            "valid": False,
            "word_count": 0,
            "estimated_chunks": 0,
            "warnings": warnings
        }
    
    words = text.split()
    word_count = len(words)
    estimated_chunks = max(1, (word_count + max_chunk_words - 1) // max_chunk_words)
    
    # Quality checks
    if word_count < 10:
        warnings.append("Text very short (< 10 words)")
    
    if not any(c.isalpha() for c in text):
        warnings.append("No alphabetic characters found")
    
    # Check for leftover markdown or emojis
    if re.search(r"```|`[^`]+`", text):
        warnings.append("Markdown code blocks still present")
    
    if re.search(r"<a?:\w+:\d+>", text):
        warnings.append("Discord emojis still present")
    
    return {
        "valid": len(warnings) == 0 or word_count >= 10,  # Allow if we have content
        "word_count": word_count,
        "estimated_chunks": estimated_chunks,
        "warnings": warnings
    }


# TDOS-ready: CLI shim for future extraction
def cli_prepare(input_file: str, output_file: str, **kwargs):
    """
    CLI entrypoint for text preparation.
    Shim: will be moved to TDOS CLI package.
    
    Usage:
        tdos rag prepare ./input.md ./output.txt --title "Rules" --scope "guild"
    """
    # Placeholder for future CLI implementation
    raise NotImplementedError("CLI preparation will be implemented in TDOS package")
