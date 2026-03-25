"""Persona Schema - Pydantic validation for personality configuration.

Enforces strict typing, prevents prompt injection, and documents the
canonical persona definition structure.

Every persona JSON loaded must validate against this schema.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from datetime import datetime
import re
import uuid


class PersonalityBoundaries(BaseModel):
    """Behavioral and operational boundaries for a persona."""
    
    max_response_length: int = Field(default=500, ge=100, le=2000, description="Maximum characters per response")
    personality_tone: str = Field(default="friendly", description="Tone keywords (e.g., 'cheerful, upbeat, bunny-like')")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="LLM temperature (0=deterministic, 1=creative)")
    can_use_tools: bool = Field(default=True, description="Can invoke Discord actions (roles, channels)")
    can_access_rag: bool = Field(default=True, description="Can query knowledge base")
    can_generate_images: bool = Field(default=True, description="Can generate images via stability API")
    can_create_threads: bool = Field(default=False, description="Can create threads")
    restricted_topics: List[str] = Field(default_factory=list, description="Topics to avoid discussing")


class ResponsePatterns(BaseModel):
    """Action phrases and processing messages for a persona."""
    
    actions: List[str] = Field(default_factory=list, description="In-character action phrases (e.g., *hops around*)")
    processing_messages: List[str] = Field(default_factory=list, description="'thinking' messages while processing")
    greetings: Dict[str, List[str]] = Field(default_factory=dict, description="Casual and formal greetings")
    
    # Usage gate messages - soft gates (cooldown/burst) that don't close session
    cooldown_messages: List[str] = Field(
        default_factory=list, 
        description="Messages when cooldown is active (soft gate - don't close session)"
    )
    burst_limit_messages: List[str] = Field(
        default_factory=list,
        description="Messages when burst rate limit hit (soft gate - don't close session)"
    )
    
    # Hard gates that close the session
    turn_limit_messages: List[str] = Field(
        default_factory=list,
        description="Messages when turn limit reached (hard gate - closes session)"
    )
    session_expired_messages: List[str] = Field(
        default_factory=list,
        description="Messages when session timeout expires (hard gate - closes session)"
    )


class SummonConfiguration(BaseModel):
    """How to trigger/summon this persona."""
    
    triggers: List[str] = Field(default_factory=list, description="Keywords that summon this persona")
    require_mention: bool = Field(default=False, description="Must be @mentioned to respond")
    auto_respond_probability: float = Field(default=0.0, ge=0.0, le=1.0, description="Chance to respond without summon")


class WelcomeConfiguration(BaseModel):
    """Welcome phrases for different user types and privilege levels."""
    
    default: List[str] = Field(default_factory=list, description="Welcome phrases for regular members")
    owner: List[str] = Field(default_factory=list, description="Welcome phrases for server owner")
    moderator: Optional[List[str]] = Field(default=None, description="Optional: Welcome for moderators")
    admin: Optional[List[str]] = Field(default=None, description="Optional: Welcome for admins")
    bot_creator: Optional[List[str]] = Field(default=None, description="Optional: Special welcome for bot creator/developer")


class FarewellConfiguration(BaseModel):
    """Farewell phrases for different user types and privilege levels."""
    
    default: List[str] = Field(default_factory=list, description="Farewell phrases for regular members")
    owner: List[str] = Field(default_factory=list, description="Farewell phrases for server owner")
    moderator: Optional[List[str]] = Field(default=None, description="Optional: Farewell for moderators")
    admin: Optional[List[str]] = Field(default=None, description="Optional: Farewell for admins")
    bot_creator: Optional[List[str]] = Field(default=None, description="Optional: Special farewell for bot creator/developer")


class PersonaMetadata(BaseModel):
    """Audit and versioning metadata."""
    
    version: str = Field(default="1.0", description="Schema version for this persona")
    last_updated: str = Field(default="2026-01-07", description="Last update date (YYYY-MM-DD)")
    created: str = Field(default="2026-01-07", description="Creation date (YYYY-MM-DD)")
    created_by: Optional[str] = Field(default=None, description="Creator name or ID")
    notes: Optional[str] = Field(default=None, description="Internal notes or changelog")


class PersonaSchema(BaseModel):
    """
    Canonical persona definition schema.
    
    All persona JSON files must validate against this schema.
    Pydantic enforces types, ranges, and security patterns.
    """
    
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)
    
    # ========== REQUIRED FIELDS ==========
    
    name: str = Field(
        ...,
        description="Unique persona identifier (alphanumeric + underscore only)",
        min_length=1,
        max_length=50
    )
    
    display_name: str = Field(
        ...,
        description="Human-readable display name (e.g., 'Abby (Bunny)')",
        min_length=1,
        max_length=100
    )
    
    emoji: str = Field(
        ...,
        description="Single emoji representing this persona",
        min_length=1,
        max_length=1
    )
    
    system_message_base: str = Field(
        ...,
        description="Core system message describing the persona",
        min_length=50,
        max_length=2000
    )
    
    description: str = Field(
        ...,
        description="Short description of this persona",
        min_length=10,
        max_length=500
    )
    
    style_hints: Optional[str] = Field(
        default=None,
        description="Optional style guidance (tone, mannerisms, expressions)"
    )
    
    # ========== OPTIONAL FIELDS ==========
    
    system_prompt_template: Optional[str] = Field(
        default=None,
        description="Full LLM system prompt template with injections"
    )
    
    welcome: Optional[WelcomeConfiguration] = Field(
        default=None,
        description="Welcome phrases for different user types"
    )
    
    farewell: Optional[FarewellConfiguration] = Field(
        default=None,
        description="Farewell phrases for different user types"
    )
    
    summon: Optional[SummonConfiguration] = Field(
        default=None,
        description="How to trigger/summon this persona"
    )
    
    response_patterns: Optional[ResponsePatterns] = Field(
        default=None,
        description="Action phrases and processing messages"
    )
    
    personality_boundaries: Optional[PersonalityBoundaries] = Field(
        default=None,
        description="Behavioral and operational boundaries"
    )
    
    metadata: Optional[PersonaMetadata] = Field(
        default=None,
        description="Audit trail and versioning information"
    )
    
    # ========== VALIDATORS ==========
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is safe identifier (no prompt injection risk)."""
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError("Name must be lowercase alphanumeric + underscore only")
        return v
    
    @field_validator('emoji')
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        """Ensure it's a single emoji."""
        # Basic check: emoji are typically outside ASCII range
        if len(v) > 1:
            raise ValueError("Emoji must be a single character")
        if ord(v) < 128:
            raise ValueError("Emoji must be a Unicode emoji, not ASCII")
        return v
    
    @field_validator('system_message_base')
    @classmethod
    def validate_system_message_no_injection(cls, v: str) -> str:
        """
        Prevent common prompt injection patterns in system messages.
        
        This is a defense-in-depth measure. Even if a malicious actor
        edits the JSON, these patterns are rejected.
        """
        forbidden_patterns = [
            r'ignore\s+(previous|instructions|all)',
            r'jailbreak',
            r'bypass',
            r'override\s+rules',
            r'pretend\s+(you|to\s+be)',
        ]
        
        v_lower = v.lower()
        for pattern in forbidden_patterns:
            if re.search(pattern, v_lower):
                raise ValueError(f"System message contains forbidden pattern: {pattern}")
        
        return v
    
    @field_validator('system_prompt_template')
    @classmethod
    def validate_system_prompt_template(cls, v: Optional[str]) -> Optional[str]:
        """Validate template syntax."""
        if v is None:
            return v
        
        # Check for balanced template braces
        open_braces = v.count('{')
        close_braces = v.count('}')
        if open_braces != close_braces:
            raise ValueError("Unbalanced template braces")
        
        return v


class PersonaRegistry(BaseModel):
    """
    Simple registry that lists available personas.
    
    This is the entry point for loading personas.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    metadata: PersonaMetadata = Field(
        default_factory=PersonaMetadata,
        description="Registry metadata"
    )
    
    active_personas: List[str] = Field(
        default_factory=list,
        description="List of persona names that are enabled"
    )
    
    # Detailed info per persona entry
    class PersonaInfo(BaseModel):
        file: str = Field(description="Relative path to persona JSON file")
        display_name: str = Field(description="Human-friendly display name")
        emoji: str = Field(description="Emoji representing the persona")
        description: str = Field(description="Short description of the persona")
        enabled: bool = Field(default=True, description="Whether persona is enabled")
        status: Optional[str] = Field(default=None, description="Optional status e.g. 'pending_migration'")

    available_personas: Dict[str, PersonaInfo] = Field(
        default_factory=dict,
        description="Mapping of persona name to persona info metadata"
    )

    default_persona: Optional[str] = Field(
        default=None,
        description="Default persona name to use when not specified"
    )


class GuildPhrasesSchema(BaseModel):
    """
    Guild-specific templates merged with persona data at request time.
    
    These are generic templates with placeholders for guild/persona injection.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    metadata: PersonaMetadata = Field(
        default_factory=PersonaMetadata,
        description="Registry metadata"
    )
    
    welcome_templates: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Welcome templates by user type (default, owner, moderator)"
    )
    
    generic_greetings: List[str] = Field(
        default_factory=list,
        description="Generic greeting templates with {guild_name} placeholder"
    )
    
    farewell_messages: List[str] = Field(
        default_factory=list,
        description="Goodbye/farewell messages"
    )


__all__ = [
    'PersonaSchema',
    'PersonaRegistry',
    'GuildPhrasesSchema',
    'PersonalityBoundaries',
    'ResponsePatterns',
    'SummonConfiguration',
    'WelcomeConfiguration',
    'PersonaMetadata',
    'CanonType',
    'CanonStatus',
    'CanonOriginType',
    'CanonArtifact',
    'CanonStagingDocument',
    'CanonicalDocument',
    'CanonCommit',
]


# ========== CANON MODELS (STAGING + COMMITS) ==========


class CanonType(str, Enum):
    """Strict enum of canon document types."""

    BOOK = "book"
    LORE = "lore"
    PERSONA = "persona"
    APPENDIX = "appendix"


class CanonStatus(str, Enum):
    """Workflow states for canon staging."""

    STAGED = "staged"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class CanonOriginType(str, Enum):
    """Authoring surface of the submission."""

    DISCORD = "discord"
    CLI = "cli"
    WEB = "web"


class CanonArtifact(BaseModel):
    """Structural metadata for canon documents."""

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    artifact_type: str = Field(description="Type of artifact (book, lore, persona, etc.)")
    name: str = Field(description="Canonical name of the artifact (e.g., 'Book of the Breeze')")
    section: Optional[str] = Field(default=None, description="Section within artifact (front_matter, chapter, appendix)")
    chapter: Optional[str] = Field(default=None, description="Chapter or entry identifier")
    domain: Optional[str] = Field(default=None, description="Domain for lore (e.g., 'world', 'character')")
    topic: Optional[str] = Field(default=None, description="Topic for lore entries")


class CanonStagingDocument(BaseModel):
    """Mutable staging artifact awaiting review/approval."""

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    title: str = Field(min_length=3, max_length=200, description="Human-readable piece name")
    canon_type: CanonType
    artifact: CanonArtifact = Field(description="Structural metadata for this canon document")
    content: str = Field(min_length=1, max_length=12000)
    part_label: Optional[str] = Field(default=None, max_length=50, description="Optional part identifier (e.g., 'Part 1', '1/3') for multi-part submissions")
    status: CanonStatus = Field(default=CanonStatus.STAGED)
    submitted_by: str = Field(description="Discord user ID or auth principal")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_by: Optional[str] = Field(default=None, description="Reviewer/approver user ID")
    reviewed_at: Optional[datetime] = None
    approval_notes: Optional[str] = Field(default=None, max_length=500)
    origin_type: CanonOriginType = Field(default=CanonOriginType.DISCORD)
    source_ref: Optional[Dict[str, Any]] = Field(default=None, description="Source metadata (message/file ids)")
    target_collection: str = Field(description="Canonical collection this will be written to")
    target_id_preview: str = Field(description="Deterministic preview of canonical id")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if len(v) > 12000:
            raise ValueError("Content exceeds 12000 character limit")
        return v


class CanonicalDocument(BaseModel):
    """Immutable canonical record written after approval."""

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    canonical_id: str
    version: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=200, description="Human-readable piece name")
    artifact: CanonArtifact = Field(description="Structural metadata for this canon document")
    content: str = Field(min_length=1, max_length=12000)
    part_label: Optional[str] = Field(default=None, max_length=50, description="Optional part identifier (e.g., 'Part 1', '1/3') for multi-part submissions")
    canon_type: CanonType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: str
    staging_id: str
    checksum: str = Field(description="SHA256 of content")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonCommit(BaseModel):
    """Immutable audit log of a canon write."""

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    commit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    staging_id: str
    canonical_id: str
    canonical_collection: str
    version: int
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: str
