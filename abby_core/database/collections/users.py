"""
Users Collection Module

PURPOSE: Universal user profile nexus - integrates all user identities and accounts
across multiple platforms (Discord, Web, etc.)

SCHEMA: Platform-agnostic user profile with multi-platform support
- user_id: Universal unique identifier (primary key)
  * Discord users: Discord ID (numeric string, e.g. "246030816692404234")
  * Web users: UUID v4 (36-char string, e.g. "550e8400-e29b-41d4-a716-446655440000")
- Platform objects: Nested data for each platform user is registered on
  * discord: Discord identity and profile data
  * web: Web app identity and profile data (future)
  * [other platforms]: Extensible for future integrations
- Universal data: Shared across all platforms
  * cooldowns: User-level temporal state (daily bonuses, cooldown tracking)
  * creative_profile: AI memory and learned patterns
  * social_accounts: YouTube, Twitter, Twitch, etc.
  * creative_accounts: Spotify, Apple Music, etc.
  * artist_profile: Creator metadata
  * collaborations: Multi-artist partnerships
  * guilds: Cross-platform communities

COOLDOWNS (User-Level Temporal State):
Stores global per-user cooldowns for features like daily bonuses.
Helper functions:
- check_user_cooldown(user_id, cooldown_name) -> bool
- record_user_cooldown(user_id, cooldown_name) -> bool

EAGER INITIALIZATION POLICY:
- All universal profile fields are initialized at creation time.
- Cooldown entries are pre-created with last_used_at: null.
- This avoids implicit field creation and ensures schema stability.

INDEXES:
- user_id (unique): Primary key, used for all lookups
- discord.discord_id (unique, sparse): Discord-specific lookups
- web.email (unique, sparse): Email-based lookups for web users
- Platform timestamps: For sorting and activity tracking
- Social/Creative account lookups: For discovery and linking
- cooldowns.{cooldown_name}.last_used_at: For finding eligible users for cooldown features

ID GENERATION STRATEGY (Hybrid):
1. Discord user (primary): user_id = Discord ID (numeric)
   Example: "246030816692404234"
   
2. Web user (no Discord): user_id = UUID v4
   Example: "550e8400-e29b-41d4-a716-446655440000"
   
3. Linking flow: Web user connects Discord later
   - Keeps original user_id (UUID)
   - Adds discord object with discord_id
   - Platform-independent user still has all features

PLATFORM OBJECT STRUCTURE:
{
  "discord": {
    "discord_id": "246030816692404234",
    "username": "z8phyr_",
    "display_name": "Z8phyR",
    "discriminator": "0",
    "avatar_url": "https://...",
    "joined_at": "2026-01-30T23:36:12.051Z",
    "last_seen": "2026-01-30T23:36:12.051Z"
  },
  "web": {
    "email": "user@example.com",
    "username": "z8phyr_web",
    "avatar_url": "https://...",
    "joined_at": "2026-02-01T10:00:00.000Z",
    "last_seen": "2026-02-01T10:00:00.000Z"
  }
}

UNIVERSAL PROFILE STRUCTURE:
{
  "user_id": "246030816692404234",
  "discord": {...},                    // Platform-specific
  "web": {...},                        // Platform-specific (future)
  "cooldowns": {                       // User-level temporal state
    "daily_bonus": {
      "last_used_at": "2026-02-03T00:00:00.000Z"
    }
  },
  "guilds": [                          // Cross-platform communities
    {
      "guild_id": "1420807994525876267",
      "guild_name": "Star Lab",
      "joined_at": "...",
      "nickname": null,
      "last_seen": "..."
    }
  ],
  "creative_profile": {                // AI memory (platform-agnostic)
    "domains": [],
    "preferences": {},
    "memorable_facts": [],
    "confidence_score": 0
  },
  "social_accounts": [],               // YouTube, Twitter, Twitch, etc.
  "creative_accounts": [],             // Spotify, Apple Music, etc.
  "artist_profile": {},                // Creator metadata
  "collaborations": [],                // Multi-artist support
  "releases": [                        // Multi-label release tracking
    {
      "title": str,
      "release_date": datetime,
      "source": str,                   // "auto_detected", "user_curated", "distribution"
      "label": str,                    // "cool_breeze", "silk_music", "self_released", "royalty_free", "wip", "other"
      "platforms": [
        {
          "platform": str,             // "spotify", "apple_music", "youtube", "soundcloud", "bandcamp", etc.
          "url": str,
          "platform_id": str
        }
      ],
      "metadata": {
        "genre": str,
        "verified": bool,
        "promotional": bool            // Abby can use for promotion
      },
      "distribution_release_id": Optional[str],  // Links to distribution_releases collection
      "added_date": datetime
    }
  ],
  "created_at": "2026-01-30T23:36:12.051Z",
  "updated_at": "2026-01-30T23:36:12.051Z"
}

MIGRATION NOTES:
- Existing Discord users: user_id = Discord ID (already in use)
- Future web users: user_id = UUID v4
- Both types can coexist without conflicts
- Linking happens by adding platform object to existing user
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get users collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    # Primary storage: users collection (not deprecated discord_profiles)
    return db["users"]


def ensure_indexes():
    """Create indexes for universal user profile collection."""
    try:
        collection = get_collection()

        # Core user identification
        try:
            collection.create_index([("user_id", 1)], unique=True)
        except Exception as e:
            if "already exists" in str(e) or "IndexKeySpecsConflict" in str(e):
                logger.debug("[users] user_id index already exists")
            else:
                raise
        
        # === Platform-specific indexes ===
        # Discord platform indexes
        try:
            collection.create_index([("discord.discord_id", 1)], unique=True, sparse=True)
            logger.debug("[users] Created index: discord.discord_id")
        except Exception as e:
            if "IndexKeySpecsConflict" in str(e):
                try:
                    collection.drop_index("discord_id_1")  # Drop old root-level index if exists
                    collection.create_index([("discord.discord_id", 1)], unique=True, sparse=True)
                    logger.debug("[users] Migrated index to discord.discord_id")
                except Exception as drop_error:
                    logger.debug(f"[users] discord_id migration note: {drop_error}")
            elif "already exists" not in str(e):
                logger.debug(f"[users] discord.discord_id index: {e}")
        
        # Web platform indexes (for future web app integration)
        try:
            collection.create_index([("web.email", 1)], unique=True, sparse=True)
            logger.debug("[users] Created index: web.email")
        except Exception as e:
            if "already exists" not in str(e) and "IndexKeySpecsConflict" not in str(e):
                logger.debug(f"[users] web.email index: {e}")
        
        # Platform activity tracking
        try:
            collection.create_index([("discord.last_seen", -1)])
            collection.create_index([("web.last_seen", -1)])
            logger.debug("[users] Created platform last_seen indexes")
        except Exception as e:
            logger.debug(f"[users] Platform activity indexes: {e}")
        
        # Temporal queries
        collection.create_index([("created_at", -1)])
        collection.create_index([("updated_at", -1)])
        
        # Guild/community membership
        collection.create_index([("guilds.guild_id", 1)])
        
        # Social account lookups
        collection.create_index([("social_accounts.platform", 1)])
        collection.create_index([("social_accounts.handle", 1)])
        collection.create_index([("social_accounts.url", 1)])
        
        # Creative account lookups
        collection.create_index([("creative_accounts.platform", 1)])
        collection.create_index([("creative_accounts.account_id", 1)])
        
        # === Cooldown tracking indexes (user-level temporal state) ===
        # For checking which users are eligible for cooldown-based features today
        try:
            collection.create_index([("cooldowns.daily_bonus.last_used_at", 1)])
            collection.create_index([("cooldowns.daily_login.last_used_at", 1)])
            collection.create_index([("cooldowns.daily_quest.last_used_at", 1)])
            logger.debug("[users] Created indexes: cooldown tracking")
        except Exception as e:
            if "already exists" not in str(e):
                logger.debug(f"[users] cooldown indexes: {e}")
        
        # Artist profile queries
        collection.create_index([("artist_profile.stage_name", 1)])
        collection.create_index([("artist_profile.is_artist", 1)])
        
        # Multi-artist collaboration
        collection.create_index([("collaborations.artist_id", 1)])
        collection.create_index([("collaborations.status", 1)])
        
        # === Release tracking indexes ===
        # Identify release source (auto_detected, user_curated, distribution)
        try:
            collection.create_index([("releases.source", 1)])
            logger.debug("[users] Created index: releases.source")
        except Exception as e:
            if "already exists" not in str(e):
                logger.debug(f"[users] releases.source index: {e}")
        
        # Link to distribution_releases collection
        try:
            collection.create_index([("releases.distribution_release_id", 1)])
            logger.debug("[users] Created index: releases.distribution_release_id")
        except Exception as e:
            if "already exists" not in str(e):
                logger.debug(f"[users] releases.distribution_release_id index: {e}")

        logger.debug("[users] Indexes created for universal profile schema")

    except Exception as e:
        logger.warning(f"[users] Error creating indexes: {e}")


# ═══════════════════════════════════════════════════════════════
# ID GENERATION & VALIDATION
# ═══════════════════════════════════════════════════════════════

def generate_user_id() -> str:
    """
    Generate a universal user ID for web-app users.
    
    Discord users use their Discord ID (numeric string).
    Web-app users get a UUID v4.
    
    Returns:
        UUID v4 string for web users, Discord ID string for Discord users
    
    Example:
        discord_id = "246030816692404234"  # From Discord
        web_id = generate_user_id()  # "550e8400-e29b-41d4-a716-446655440000"
    """
    return str(uuid.uuid4())


def is_discord_id(user_id: str) -> bool:
    """
    Check if user_id is a Discord ID (numeric) or UUID (web user).
    
    Args:
        user_id: User ID to check
        
    Returns:
        True if Discord ID (all digits), False if UUID format
    
    Examples:
        is_discord_id("246030816692404234") -> True
        is_discord_id("550e8400-e29b-41d4-a716-446655440000") -> False
    """
    return user_id.isdigit()


def get_id_type(user_id: str) -> str:
    """
    Identify the type of user ID.
    
    Args:
        user_id: User ID to classify
        
    Returns:
        "discord" if numeric Discord ID, "uuid" if UUID v4, "unknown" otherwise
    """
    if is_discord_id(user_id):
        return "discord"
    elif len(user_id) == 36 and "-" in user_id:  # UUID v4 format
        return "uuid"
    else:
        return "unknown"


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[users] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[users] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize users collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[users] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[users] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS - Core User Profile
# ═══════════════════════════════════════════════════════════════

def get_user(user_id: str | int) -> Optional[Dict[str, Any]]:
    """Get user profile."""
    try:
        collection = get_collection()
        return collection.find_one({"user_id": str(user_id)})
    except Exception as e:
        logger.error(f"[users] Error getting user {user_id}: {e}")
        return None


def ensure_user_guild_entry(
    user_id: str | int,
    guild_id: str | int,
    guild_name: str,
    nickname: Optional[str],
    joined_at: Optional[datetime] = None,
    last_seen: Optional[datetime] = None
) -> bool:
    """Ensure guild entry exists and is up-to-date for a user.

    Stores guild membership objects in users.guilds with stable guild_id.
    """
    try:
        collection = get_collection()
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)
        now = last_seen or datetime.utcnow()

        update_fields: Dict[str, Any] = {
            "guilds.$.guild_name": guild_name,
            "guilds.$.nickname": nickname,
            "guilds.$.last_seen": now
        }
        if joined_at:
            update_fields["guilds.$.joined_at"] = joined_at

        result = collection.update_one(
            {"user_id": user_id_str, "guilds.guild_id": guild_id_str},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            entry = {
                "guild_id": guild_id_str,
                "guild_name": guild_name,
                "joined_at": joined_at or now,
                "nickname": nickname,
                "last_seen": now
            }
            collection.update_one(
                {"user_id": user_id_str},
                {"$addToSet": {"guilds": entry}}
            )

        return True
    except Exception as e:
        logger.error(f"[users] Error ensuring guild entry for user {user_id}: {e}")
        return False


def get_guild_profile_stats(guild_id: str | int) -> Dict[str, int]:
    """Get total profiles and total memorable facts for a guild."""
    try:
        collection = get_collection()
        guild_id_str = str(guild_id)

        query = {"guilds.guild_id": guild_id_str}
        total_profiles = collection.count_documents(query)

        pipeline = [
            {"$match": query},
            {"$project": {"fact_count": {"$size": {"$ifNull": ["$creative_profile.memorable_facts", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$fact_count"}}}
        ]
        result = list(collection.aggregate(pipeline))
        total_facts = result[0].get("total", 0) if result else 0

        return {"total_profiles": total_profiles, "total_facts": total_facts}
    except Exception as e:
        logger.error(f"[users] Error getting guild profile stats: {e}")
        return {"total_profiles": 0, "total_facts": 0}


def get_top_users_by_fact_count(guild_id: str | int, limit: int = 3) -> List[Dict[str, Any]]:
    """Return top users by memorable fact count in a guild."""
    try:
        collection = get_collection()
        guild_id_str = str(guild_id)

        pipeline = [
            {"$match": {"guilds.guild_id": guild_id_str}},
            {"$addFields": {"fact_count": {"$size": {"$ifNull": ["$creative_profile.memorable_facts", []]}}}},
            {"$project": {"username": {"$ifNull": ["$discord.username", "unknown"]}, "fact_count": 1}},
            {"$sort": {"fact_count": -1}},
            {"$limit": limit}
        ]

        return list(collection.aggregate(pipeline))
    except Exception as e:
        logger.error(f"[users] Error getting top users by fact count: {e}")
        return []


def upsert_user(user_id: int, user_data: Dict[str, Any]) -> bool:
    """Create or update user profile using universal schema enforcement.
    
    DEPRECATED: Use MemoryService.ensure_user_profile() instead for proper schema enforcement.
    This wrapper now routes through MemoryService to ensure compliance with universal schema.
    """
    try:
        from tdos_intelligence.memory.service import create_memory_service
        from tdos_intelligence.memory.storage import MongoMemoryStore
        from abby_core.database.mongodb import connect_to_mongodb
        
        # Build metadata from user_data for platform-specific nesting
        metadata = {
            "_platform": "discord",
            "discord_id": str(user_data.get("discord_id", user_id)),
            "username": user_data.get("username", f"User{user_id}"),
            "avatar_url": user_data.get("avatar_url"),
        }
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # Get MongoDB client and create memory service with explicit storage client
        mongo_client = connect_to_mongodb()
        store = MongoMemoryStore(
            storage_client=mongo_client,
            profile_collection="users"
        )
        memory_service = create_memory_service(store=store, source_id="discord", logger=logger)
        guild_id = user_data.get("guild_id")
        
        # Route through enforcement layer - this ensures proper schema compliance
        profile = memory_service.ensure_user_profile(
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            metadata=metadata
        )
        
        # Update non-platform universal fields if provided
        updates = {}
        if "social_accounts" in user_data:
            updates["social_accounts"] = user_data["social_accounts"]
        if "creative_accounts" in user_data:
            updates["creative_accounts"] = user_data["creative_accounts"]
        if "artist_profile" in user_data:
            updates["artist_profile"] = user_data["artist_profile"]
        if "collaborations" in user_data:
            updates["collaborations"] = user_data["collaborations"]
        if "preferences" in user_data:
            updates["creative_profile.preferences"] = user_data["preferences"]
        
        # Apply any additional updates
        if updates:
            updates["updated_at"] = datetime.utcnow()
            collection = get_collection()
            collection.update_one(
                {"user_id": str(user_id)},
                {"$set": updates}
            )
        
        logger.debug(f"[users] Upserted user {user_id} via universal schema enforcement")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error upserting user {user_id}: {e}")
        return False


def add_guild_to_user(user_id: int, guild_id: int) -> bool:
    """Add guild to user's guild list."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"guilds": guild_id}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[users] Error adding guild: {e}")
        return False


def get_user_guilds(user_id: int) -> List[int]:
    """Get list of guilds user is in."""
    try:
        user = get_user(user_id)
        return user.get("guilds", []) if user else []
    except Exception as e:
        logger.error(f"[users] Error getting guilds for user {user_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# COOLDOWN TRACKING (Universal user-level temporal state)
# ═══════════════════════════════════════════════════════════════
# Stores user-level cooldowns in a single canonical place for:
# - Daily bonus (once per user per day)
# - Daily login bonus (future)
# - Daily quest (future)
# - Battle cooldown (future)
# etc.

def check_user_cooldown(user_id: int, cooldown_name: str) -> bool:
    """
    Check if user has used a cooldown-based feature TODAY.
    
    Uses timezone-aware UTC for consistent date boundary calculations.
    
    Args:
        user_id: User ID (Discord ID string or int)
        cooldown_name: Name of cooldown (e.g., "daily_bonus", "daily_login", "daily_quest")
    
    Returns:
        True if user has already used this feature today, False otherwise
    """
    from datetime import datetime, timezone
    
    try:
        collection = get_collection()
        # UTC midnight of today (timezone-aware)
        now_utc = datetime.now(timezone.utc)
        today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        user_id_str = str(user_id)
        user_id_values: set[str | int] = {user_id_str}
        if user_id_str.isdigit():
            user_id_values.add(int(user_id_str))
        
        # Check if user has cooldown timestamp from today
        # Stored in cooldowns.{cooldown_name}.last_used_at field
        # Note: MongoDB will handle timezone-aware/naive comparison in query
        field_path = f"cooldowns.{cooldown_name}.last_used_at"
        user_record = collection.find_one({
            "user_id": {"$in": list(user_id_values)},
            field_path: {"$gte": today}
        })
        
        has_used = user_record is not None
        logger.debug(f"[users] Checked {cooldown_name} cooldown for {user_id}: has_used={has_used}, today_utc={today.isoformat()}")
        return has_used
    except Exception as e:
        logger.error(f"[users] Error checking {cooldown_name} cooldown for {user_id}: {e}")
        return False  # Fail-safe: if DB fails, allow the action


def record_user_cooldown(user_id: int, cooldown_name: str) -> bool:
    """
    Record that a user has used a cooldown-based feature TODAY.
    
    Args:
        user_id: User ID (Discord ID string or int)
        cooldown_name: Name of cooldown (e.g., "daily_bonus", "daily_login", "daily_quest")
    
    Returns:
        True if successfully recorded, False otherwise
    """
    from datetime import datetime, timezone
    
    try:
        collection = get_collection()
        now = datetime.now(timezone.utc)
        
        user_id_str = str(user_id)
        user_id_values: set[str | int] = {user_id_str}
        if user_id_str.isdigit():
            user_id_values.add(int(user_id_str))
        
        # Update cooldown timestamp in user record
        # Creates cooldowns.{cooldown_name} object if it doesn't exist
        result = collection.update_one(
            {"user_id": {"$in": list(user_id_values)}},
            {
                "$set": {
                    f"cooldowns.{cooldown_name}.last_used_at": now,
                    "updated_at": now
                }
            },
            upsert=False
        )
        
        if result.modified_count == 0:
            logger.warning(f"[users] No user record found to record {cooldown_name} cooldown for {user_id} - attempting to create minimal user record")
            # Try to create a minimal user record as fallback
            result = collection.update_one(
                {"user_id": str(user_id)},
                {
                    "$setOnInsert": {
                        "user_id": str(user_id),
                        "created_at": datetime.utcnow()
                    },
                    "$set": {
                        f"cooldowns.{cooldown_name}.last_used_at": now,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            if result.upserted_id or result.modified_count > 0:
                logger.info(f"[users] Created/updated minimal user record for {user_id} with {cooldown_name} cooldown")
                return True
            return False
        
        logger.debug(f"[users] Recorded {cooldown_name} cooldown for {user_id}")
        return True
    except Exception as e:
        logger.error(f"[users] Error recording {cooldown_name} cooldown for {user_id}: {e}")
        return False


def ensure_user_from_discord(user, guild=None) -> str:
    """
    CANONICAL user initialization from Discord interactions.
    
    Ensures user has a profile in Users collection using universal schema enforcement.
    This is the single source of truth for creating/updating Discord users.
    
    Initializes schema-compliant fields per UNIVERSAL_PROFILE_STRUCTURE:
    - cooldowns: Empty dict for tracking user-level temporal state
    - creative_profile: Empty profile structure for AI memory
    - social_accounts: Empty array for social linking
    - creative_accounts: Empty array for music service linking
    - artist_profile: Empty profile for creator metadata
    - collaborations: Empty array for partnerships
    - releases: Empty array for multi-label tracking
    
    Args:
        user: Discord user or member object
        guild: Optional Discord guild for guild-specific context
    
    Returns:
        str: The user_id (as string)
    
    Usage:
        from abby_core.database.collections.users import ensure_user_from_discord
        
        # From any Discord interaction/event
        user_id = ensure_user_from_discord(interaction.user, interaction.guild)
        
        # From message events
        user_id = ensure_user_from_discord(message.author, message.guild)
    """
    try:
        from tdos_intelligence.memory.service import create_memory_service
        from tdos_intelligence.memory.storage import MongoMemoryStore
        from abby_core.database.mongodb import connect_to_mongodb
        
        user_id = str(user.id)
        guild_id = str(guild.id) if guild else None
        
        # Get MongoDB client and create memory service
        mongo_client = connect_to_mongodb()
        store = MongoMemoryStore(
            storage_client=mongo_client,
            profile_collection="users"
        )
        memory_service = create_memory_service(store=store, source_id="discord", logger=logger)
        
        # Build Discord metadata - nested under 'discord' platform key
        metadata = {
            "_platform": "discord",
            "discord_id": user_id,
            "username": user.name,
            "discriminator": getattr(user, 'discriminator', None),
            "display_name": getattr(user, 'display_name', user.name),
            "avatar_url": str(user.avatar.url) if user.avatar else None,
            "last_seen": datetime.utcnow()
        }
        
        # Add guild-specific data if available
        # NOTE: nickname goes in guilds array, NOT in discord object
        if guild:
            import discord
            if isinstance(user, discord.Member):
                metadata["nickname"] = user.nick
                metadata["guild_id"] = guild_id
                metadata["guild_name"] = guild.name
                if user.joined_at:
                    metadata["joined_at"] = user.joined_at
        
        # Ensure profile exists (idempotent - won't overwrite existing data)
        profile = memory_service.ensure_user_profile(
            user_id=user_id,
            guild_id=guild_id,
            metadata=metadata
        )
        
        # SCHEMA ENFORCEMENT: Ensure all universal profile fields exist
        # This enforces schema compliance and prevents "missing field" issues
        collection = get_collection()
        
        # Initialize cooldowns with all known features set to null initially
        # INDUSTRY STANDARD: Eager initialization with null values ensures:
        #  1. Schema is explicit and discoverable
        #  2. No "magic field creation" on first use
        #  3. Easier debugging (field exists but empty vs field doesn't exist)
        #  4. Matches Stripe/Discord API patterns
        schema_fields = {
            "cooldowns": {  # User-level temporal state - pre-initialized with all features
                "daily_bonus": {
                    "last_used_at": None
                }
                # Add other cooldowns here as features are implemented
            },
            "creative_profile": {  # AI memory and learned patterns
                "domains": [],
                "preferences": {},
                "memorable_facts": [],
                "confidence_score": 0
            },
            "social_accounts": [],  # YouTube, Twitter, Twitch, Instagram, TikTok
            "creative_accounts": [],  # Spotify, Apple Music, SoundCloud, Bandcamp
            "artist_profile": {  # Creator metadata
                "is_artist": False,
                "stage_name": None,
                "bio": None,
                "website": None,
                "links": {}
            },
            "collaborations": [],  # Multi-artist partnerships
            "releases": []  # Multi-label release tracking
        }
        
        # Build fields to always update (discord info + ensure schema fields exist)
        # Note: Discord fields are updated on EVERY call (not just creation)
        # This ensures avatar, username, display_name stay in sync
        always_update_fields = {"discord": metadata.copy()}
        # Remove guild-specific fields from discord object (they go in guilds array)
        always_update_fields["discord"].pop("nickname", None)
        always_update_fields["discord"].pop("guild_id", None)
        always_update_fields["discord"].pop("guild_name", None)
        always_update_fields["discord"].pop("joined_at", None)
        
        # Upsert: 
        # - Create with schema_fields + always_update_fields if new
        # - Update with always_update_fields on every call
        collection.update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": schema_fields,
                "$set": always_update_fields
            },
            upsert=True
        )
        
        if profile.get("created_at") == metadata.get("last_seen"):
            logger.info(f"[users] Created new profile for Discord user {user_id} ({user.name})")
        else:
            logger.debug(f"[users] Updated profile metadata for Discord user {user_id}")
        
        return user_id
        
    except Exception as e:
        logger.error(f"[users] Error ensuring user profile for {user.id}: {e}")
        # Return user_id even if profile creation failed (don't block operations)
        return str(user.id)


def backfill_schema_fields(user_id: str | None = None) -> dict:
    """
    Backfill missing schema fields for existing users.
    
    Call this to ensure all users have schema-compliant profiles.
    Adds cooldowns, creative_profile, social_accounts, etc. only if missing.
    
    Args:
        user_id: Optional. If provided, backfills only this user.
                 If None, backfills ALL users missing any schema fields.
    
    Returns:
        dict: {"matched": count, "modified": count}
    
    Usage:
        from abby_core.database.collections.users import backfill_schema_fields
        
        # Backfill single user
        result = backfill_schema_fields(user_id="246030816692404234")
        
        # Backfill ALL users
        result = backfill_schema_fields()
        print(f"Updated {result['modified']} users with schema fields")
    """
    collection = get_collection()
    
    # Schema fields that should exist on all users
    # Initialize cooldowns with all known features set to null initially
    schema_fields = {
        "cooldowns": {
            "daily_bonus": {
                "last_used_at": None
            }
        },
        "creative_profile": {
            "domains": [],
            "preferences": {},
            "memorable_facts": [],
            "confidence_score": 0
        },
        "social_accounts": [],
        "creative_accounts": [],
        "artist_profile": {
            "is_artist": False,
            "stage_name": None,
            "bio": None,
            "website": None,
            "links": {}
        },
        "collaborations": [],
        "releases": []
    }
    
    # Build query for users missing any schema field
    missing_fields_query: Dict[str, Any] = {
        "$or": [
            {"cooldowns": {"$exists": False}},
            {"creative_profile": {"$exists": False}},
            {"social_accounts": {"$exists": False}},
            {"creative_accounts": {"$exists": False}},
            {"artist_profile": {"$exists": False}},
            {"collaborations": {"$exists": False}},
            {"releases": {"$exists": False}}
        ]
    }
    
    # If user_id provided, filter to just that user
    if user_id:
        missing_fields_query["user_id"] = user_id
    
    # Perform bulk update for missing top-level fields
    result = collection.update_many(
        missing_fields_query,
        {"$set": schema_fields}
    )

    # Ensure cooldowns.daily_bonus exists without overwriting other cooldowns
    cooldowns_query: Dict[str, Any] = {"cooldowns.daily_bonus": {"$exists": False}}
    if user_id:
        cooldowns_query["user_id"] = user_id
    cooldowns_result = collection.update_many(
        cooldowns_query,
        {"$set": {"cooldowns.daily_bonus.last_used_at": None}}
    )
    
    logger.info(
        f"[users] Schema backfill complete: "
        f"matched={result.matched_count}, modified={result.modified_count}; "
        f"cooldowns_matched={cooldowns_result.matched_count}, "
        f"cooldowns_modified={cooldowns_result.modified_count}"
    )
    
    return {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "cooldowns_matched": cooldowns_result.matched_count,
        "cooldowns_modified": cooldowns_result.modified_count
    }



# SOCIAL ACCOUNT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def add_social_account(user_id: int, platform: str, handle: str, url: str) -> bool:
    """Add social account link (YouTube, Twitter, Twitch, etc).
    
    Args:
        user_id: User ID
        platform: Social platform (youtube, twitter, twitch, tiktok, instagram, etc)
        handle: Platform username/handle
        url: Full URL to profile
    """
    try:
        collection = get_collection()
        
        social_account = {
            "platform": platform.lower(),
            "handle": handle,
            "url": url,
            "added_at": datetime.utcnow(),
            "verified": False,
        }
        
        result = collection.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {
                    "social_accounts": {
                        "$each": [social_account],
                        "$position": 0
                    }
                }
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Added {platform} social account for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error adding social account: {e}")
        return False


def remove_social_account(user_id: int, platform: str) -> bool:
    """Remove social account link."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$pull": {"social_accounts": {"platform": platform.lower()}}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Removed {platform} social account for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error removing social account: {e}")
        return False


def get_social_accounts(user_id: int) -> List[Dict[str, Any]]:
    """Get all social accounts for user."""
    try:
        user = get_user(user_id)
        return user.get("social_accounts", []) if user else []
    except Exception as e:
        logger.error(f"[users] Error getting social accounts: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# CREATIVE ACCOUNT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def add_creative_account(user_id: int, platform: str, account_id: str, display_name: Optional[str] = None) -> bool:
    """Add creative account (Spotify, Apple Music, SoundCloud, etc).
    
    Args:
        user_id: User ID
        platform: Creative platform (spotify, apple_music, soundcloud, bandcamp, etc)
        account_id: Platform account ID
        display_name: Display name on platform
    """
    try:
        collection = get_collection()
        
        creative_account = {
            "platform": platform.lower(),
            "account_id": account_id,
            "display_name": display_name,
            "connected_at": datetime.utcnow(),
            "verified": False,
            "access_token_expires": None,
        }
        
        result = collection.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {
                    "creative_accounts": {
                        "$each": [creative_account],
                        "$position": 0
                    }
                }
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Added {platform} creative account for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error adding creative account: {e}")
        return False


def remove_creative_account(user_id: int, platform: str) -> bool:
    """Remove creative account."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$pull": {"creative_accounts": {"platform": platform.lower()}}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Removed {platform} creative account for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error removing creative account: {e}")
        return False


def get_creative_accounts(user_id: int) -> List[Dict[str, Any]]:
    """Get all creative accounts for user."""
    try:
        user = get_user(user_id)
        return user.get("creative_accounts", []) if user else []
    except Exception as e:
        logger.error(f"[users] Error getting creative accounts: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# ARTIST PROFILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def set_artist_profile(user_id: int, stage_name: str, bio: Optional[str] = None, website: Optional[str] = None) -> bool:
    """Enable and configure artist profile for user.
    
    Args:
        user_id: User ID
        stage_name: Artist stage name
        bio: Artist biography
        website: Artist website
    """
    try:
        collection = get_collection()
        
        artist_profile = {
            "is_artist": True,
            "stage_name": stage_name,
            "bio": bio,
            "website": website,
            "links": {},
            "established_at": datetime.utcnow(),
        }
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$set": {"artist_profile": artist_profile}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Set artist profile for user {user_id}: {stage_name}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error setting artist profile: {e}")
        return False


def add_collaboration(user_id: int, collab_artist_id: int, status: str = "pending") -> bool:
    """Add collaboration with another artist.
    
    Args:
        user_id: User ID
        collab_artist_id: Artist ID to collaborate with
        status: Collaboration status (pending, active, archived)
    """
    try:
        collection = get_collection()
        
        collaboration = {
            "artist_id": collab_artist_id,
            "status": status,
            "started_at": datetime.utcnow(),
            "projects": [],
        }
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"collaborations": collaboration}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
        
        logger.debug(f"[users] Added collaboration for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error adding collaboration: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class Users(CollectionModule):
    """Collection module for universal user profiles - follows foolproof pattern.
    
    The users collection serves as the central nexus for all user-related data:
    - Discord presence and guild memberships
    - Social account integrations (YouTube, Twitter, Twitch, etc)
    - Creative account connections (Spotify, Apple Music, etc)
    - Artist profiles and collaborations
    - Multi-artist support structure
    
    This architecture enables:
    1. Single source of truth for user identity
    2. Flexible expansion for new platforms
    3. Multi-artist tracking over 20+ years
    4. Cross-platform account linkage
    """
    
    collection_name = "users"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get users collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not Users.collection_name:
            raise RuntimeError("collection_name not set for Users")
        db = get_database()
        return db[Users.collection_name]
    
    @staticmethod
    def ensure_indexes():
        """Create all indexes for efficient querying."""
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        """Seed default data if needed."""
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        """Orchestrate initialization."""
        return initialize_collection()
