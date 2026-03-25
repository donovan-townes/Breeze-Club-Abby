# Universal User Profile Schema

## Overview

The `users` collection implements a **platform-agnostic user schema** that supports multi-platform integration. Users can have identities on Discord, web app, and future platforms, all under a single universal `user_id`.

## Schema Structure

### Root Level

````json
{
  "_id": ObjectId,                          // MongoDB document ID
  "user_id": String,                        // Universal unique identifier (primary key)
  "discord": Object,                        // Discord platform data (optional)
  "web": Object,                            // Web app platform data (optional, future)
  "guilds": Array,                          // Cross-platform communities
  "cooldowns": Object,                      // User-level temporal state (daily bonuses, cooldowns)
  "creative_profile": Object,               // AI memory & learned patterns
  "social_accounts": Array,                 // External social profiles
  "creative_accounts": Array,               // External creative platforms
  "artist_profile": Object,                 // Creator/artist metadata
  "collaborations": Array,                  // Multi-artist partnerships
  "created_at": Date,                       // Profile creation timestamp
  "updated_at": Date                        // Last profile update timestamp
}
```python

## User ID Generation Strategy

### Discord Users (Existing Flow)

- **Source**: Discord interaction
- **ID Format**: Discord ID (numeric string)
- **Example**: `"246030816692404234"`
- **Type Check**: `user_id.isdigit()` returns `true`
- **Purpose**: Semantic, matches Discord ecosystem, sortable

### Web Users (Future Flow)

- **Source**: Web app registration
- **ID Format**: UUID v4 (36-character string)
- **Example**: `"550e8400-e29b-41d4-a716-446655440000"`
- **Type Check**: UUID format with hyphens
- **Purpose**: Platform-independent, no collisions with Discord IDs

### Hybrid: Linking Accounts

When a web user later connects their Discord account:

- **Keep**: Original user_id (UUID)
- **Add**: `discord` platform object with `discord_id`
- **Result**: Single user with both platforms

## Platform Objects

### Discord Platform

```json
{
  "discord": {
    "discord_id": String,           // Unique Discord ID (main identifier)
    "username": String,             // Discord username
    "display_name": String,         // Discord display name
    "discriminator": String,        // Discord discriminator (0 for new users)
    "avatar_url": String,           // Discord avatar URL
    "joined_at": Date,              // When user first connected Discord
    "last_seen": Date               // Last Discord activity
  }
}
```python

### Web Platform (Future)

```json
{
  "web": {
    "email": String,                // Email address (unique)
    "username": String,             // Web username
    "password_hash": String,        // Hashed password (never plaintext)
    "avatar_url": String,           // Web avatar URL
    "email_verified": Boolean,      // Email verification status
    "joined_at": Date,              // When user registered
    "last_seen": Date               // Last web activity
  }
}
```python

## Universal Profile Data

### Creative Profile (AI Memory)

```json
{
  "creative_profile": {
    "domains": Array,               // User's domains of expertise
    "preferences": Object,          // User preferences learned from conversation
    "memorable_facts": Array,       // AI-extracted facts about user
    "confidence_score": Number      // Confidence in current model (0-1)
  }
}
```python

### Social Accounts

```json
{
  "social_accounts": [
    {
      "platform": String,           // "youtube", "twitter", "twitch", etc.
      "handle": String,             // Username/handle
      "url": String,                // Profile URL
      "verified": Boolean,          // Verification status
      "added_at": Date,             // When linked
      "metadata": Object            // Platform-specific metadata
    }
  ]
}
```python

### Creative Accounts

```json
{
  "creative_accounts": [
    {
      "platform": String,           // "spotify", "apple_music", "soundcloud", etc.
      "display_name": String,       // Display name on platform
      "account_id": String,         // Platform account ID
      "url": String,                // Profile URL
      "verified": Boolean,          // Verification status
      "added_at": Date,             // When linked
      "metadata": Object            // Platform-specific metadata
    }
  ]
}
```python

### Guilds (Communities)

```json
{
  "guilds": [
    {
      "guild_id": String,           // Community ID
      "guild_name": String,         // Community name
      "joined_at": Date,            // When user joined
      "nickname": String,           // User's nickname in community (nullable)
      "last_seen": Date             // Last activity in community
    }
  ]
}
```python

### Cooldowns (User-Level Temporal State)

**Purpose**: Track daily bonuses and cooldown-based features globally per user.
Stored at user-level (not guild-scoped) since features like daily bonus are global per user per day.

```json
{
  "cooldowns": {
    "daily_bonus": {
      "last_used_at": Date          // Last time user claimed daily bonus
    },
    "daily_login": {
      "last_used_at": Date          // Last login bonus claim (future)
    },
    "daily_quest": {
      "last_used_at": Date          // Last quest completion (future)
    }
  }
}
```python

**Checking a Cooldown**:

```python
from abby_core.database.collections.users import check_user_cooldown

# Check if user used daily bonus today (returns True if yes, False if no)
if check_user_cooldown(user_id, "daily_bonus"):
    return  # Already used today
````

**Recording a Cooldown**:

```python
from abby_core.database.collections.users import record_user_cooldown

# Grant the bonus/feature...
record_user_cooldown(user_id, "daily_bonus")  # Mark as used today
```

**Query Examples**:

```python
# Find users who haven't used daily bonus today
today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
users_collection.find({
    "cooldowns.daily_bonus.last_used_at": {"$lt": today}
})

# Or use the helper
if not check_user_cooldown(user_id, "daily_bonus"):
    # Can claim bonus today
    pass
```

### Artist Profile

````json
{
  "artist_profile": {
    "is_artist": Boolean,           // Is user a creator
    "stage_name": String,           // Artist name
    "bio": String,                  // Artist bio
    "website": String,              // Artist website
    "established_at": Date,         // When artist profile created
    "genres": Array,                // Music genres
    "collaboration_score": Number   // Collaboration activity score
  }
}
```python

## Database Indexes

### Primary Key

- **Index**: `user_id` (unique)
- **Type**: Unique
- **Usage**: All user lookups

### Platform Lookups

- **Index**: `discord.discord_id` (unique, sparse)
- **Type**: Unique with sparse option (null values ignored)
- **Usage**: Discord user lookups

- **Index**: `web.email` (unique, sparse)
- **Type**: Unique with sparse option
- **Usage**: Web app email lookups

### Activity Tracking

- **Indexes**: `discord.last_seen`, `web.last_seen` (descending)
- **Usage**: Finding active users by platform

### Temporal Queries

- **Indexes**: `created_at`, `updated_at` (descending)
- **Usage**: Time-based queries

### Cooldowns (User-Level Temporal State)

- **Indexes**:
  - `cooldowns.daily_bonus.last_used_at`
  - `cooldowns.daily_login.last_used_at`
  - `cooldowns.daily_quest.last_used_at`
- **Type**: Non-unique
- **Usage**: Finding users eligible for cooldown-based features
- **Query Pattern**: Find users where `cooldowns.{feature}.last_used_at < today`

### Community Queries

- **Index**: `guilds.guild_id`
- **Usage**: Finding all users in a community

### Social & Creative Lookups

- **Indexes**:
  - `social_accounts.platform`
  - `social_accounts.handle`
  - `creative_accounts.platform`
  - `creative_accounts.account_id`
- **Usage**: Discovering users by social/creative presence

## Example Documents

### Discord User (Current State)

```json
{
  "user_id": "246030816692404234",
  "discord": {
    "discord_id": "246030816692404234",
    "username": "z8phyr_",
    "display_name": "Z8phyR",
    "discriminator": "0",
    "avatar_url": "https://cdn.discordapp.com/avatars/.../...",
    "joined_at": "2026-01-30T23:36:12.051Z",
    "last_seen": "2026-01-30T23:36:12.051Z"
  },
  "guilds": [
    {
      "guild_id": "1420807994525876267",
      "guild_name": "Star Lab",
      "joined_at": "2026-01-30T23:36:12.051Z",
      "nickname": null,
      "last_seen": "2026-01-30T23:36:12.051Z"
    }
  ],
  "creative_profile": {
    "domains": [],
    "preferences": {},
    "memorable_facts": [],
    "confidence_score": 0
  },
  "social_accounts": [],
  "creative_accounts": [],
  "artist_profile": {},
  "collaborations": [],
  "created_at": "2026-01-30T23:36:12.051Z",
  "updated_at": "2026-01-30T23:36:12.051Z"
}
```python

### Web User Registering

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "web": {
    "email": "user@example.com",
    "username": "z8phyr_web",
    "password_hash": "$2b$12$...",
    "avatar_url": "https://...",
    "email_verified": true,
    "joined_at": "2026-02-01T10:00:00.000Z",
    "last_seen": "2026-02-01T10:00:00.000Z"
  },
  "guilds": [],
  "creative_profile": {...},
  "social_accounts": [],
  "creative_accounts": [],
  "artist_profile": {},
  "collaborations": [],
  "created_at": "2026-02-01T10:00:00.000Z",
  "updated_at": "2026-02-01T10:00:00.000Z"
}
```python

### Hybrid User (Discord + Web)

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",  // Original web UUID
  "discord": {
    "discord_id": "246030816692404234",
    "username": "z8phyr_",
    "display_name": "Z8phyR",
    "discriminator": "0",
    "avatar_url": "https://cdn.discordapp.com/avatars/.../...",
    "joined_at": "2026-02-05T15:30:00.000Z",  // When Discord was linked
    "last_seen": "2026-02-05T15:30:00.000Z"
  },
  "web": {
    "email": "user@example.com",
    "username": "z8phyr_web",
    "password_hash": "$2b$12$...",
    "avatar_url": "https://...",
    "email_verified": true,
    "joined_at": "2026-02-01T10:00:00.000Z",
    "last_seen": "2026-02-05T15:30:00.000Z"
  },
  "guilds": [...],
  "creative_profile": {...},
  "social_accounts": [...],
  "creative_accounts": [...],
  "artist_profile": {...},
  "collaborations": [...],
  "created_at": "2026-02-01T10:00:00.000Z",  // Original creation
  "updated_at": "2026-02-05T15:30:00.000Z"   // Last update
}
```python

## Implementation Guidelines

### Creating a User (Discord)

```python
from abby_core.database.collections.users import Users

user_id = str(interaction.user.id)  # Use Discord ID as-is
Users.get_collection().insert_one({
    "user_id": user_id,
    "discord": {
        "discord_id": user_id,
        "username": interaction.user.name,
        "display_name": interaction.user.display_name,
        "discriminator": interaction.user.discriminator or "0",
        "avatar_url": str(interaction.user.display_avatar.url),
        "joined_at": datetime.utcnow(),
        "last_seen": datetime.utcnow()
    },
    ...  # Other fields
})
```python

### Creating a User (Web App)

```python
from abby_core.database.collections.users import generate_user_id, Users

user_id = generate_user_id()  # Generate UUID
Users.get_collection().insert_one({
    "user_id": user_id,
    "web": {
        "email": email,
        "username": username,
        "password_hash": hash_password(password),
        "avatar_url": None,
        "email_verified": False,
        "joined_at": datetime.utcnow(),
        "last_seen": datetime.utcnow()
    },
    ...  # Other fields
})
```python

### Linking Platforms

```python
from abby_core.database.collections.users import Users

## Web user links Discord
user_id = "550e8400-e29b-41d4-a716-446655440000"  # Original UUID
discord_id = str(interaction.user.id)

Users.get_collection().update_one(
    {"user_id": user_id},
    {"$set": {
        "discord": {
            "discord_id": discord_id,
            "username": interaction.user.name,
            ...
            "joined_at": datetime.utcnow(),
            "last_seen": datetime.utcnow()
        },
        "updated_at": datetime.utcnow()
    }}
)
```python

## Migration Notes

- Existing Discord users: user_id = Discord ID (already deployed)
- Web app integration: Future users get UUID v4
- No collisions: Discord IDs are numeric, UUIDs are 36-char strings
- Backward compatible: All existing code continues to work
- Platform-independent: Creative profile, social, etc. work across platforms

## Future Extensions

Easily add new platforms by adding platform objects:

- `"github": {...}`
- `"steam": {...}`
- `"twitch": {...}`
- `"youtube": {...}`
- `"patreon": {...}`

Each platform follows the same pattern:

```json
{
  "platform_name": {
    "platform_id": String,
    "username": String,
    "url": String,
    "joined_at": Date,
    "last_seen": Date,
    "metadata": Object
  }
}
```python

---

## Multi-Domain Creative Profiles & Content Tracking

## Overview

To support multiple creative domains (music, art, programming, writing, game development, etc.) and track user-released content across platforms, the schema needs expansion in two areas:

1. **Domain-based Creative Profiles** - Support users with expertise/identity in multiple domains
2. **User Content Registry** - Automatically track and cache user releases/content shared publicly

## Domain-Based Creative Profile Architecture

### Expanded creative_profile Structure

The `creative_profile` evolves from a single profile to a **multi-domain awareness system**:

```json
{
  "creative_profile": {
    "primary_domain": String,           // User's main focus ("music", "art", "programming", etc.)
    "active_domains": Array,            // All domains user has profiles in
    "domains": Object,                  // Domain-specific data
    "cross_domain_skills": Array,       // Skills applicable across domains
    "ai_memory": Object                 // Shared AI memory across all domains
  }
}
```python

### Domain-Specific Structure

Each domain gets its own profile namespace:

```json
{
  "domains": {
    "music": {
      "bio": String,                    // User's music bio/description
      "genres": Array,                  // Genres they work in
      "instruments": Array,             // Instruments they play
      "role": String,                   // "producer", "vocalist", "instrumentalist", etc.
      "memorable_facts": Array,         // AI-learned facts specific to music
      "platforms": Object,              // Platform accounts for this domain
      "release_count": Number,          // Total known releases
      "collaborative_genres": Array,    // Genres they want to collaborate on
      "technical_interests": Array      // Production software, DAWs, equipment
    },
    "art": {
      "bio": String,                    // Artist bio
      "mediums": Array,                 // ["digital", "traditional", "pixel art", "3D", etc.]
      "styles": Array,                  // Art styles they work in
      "subjects": Array,                // What they typically create ("portraits", "landscapes", etc.)
      "memorable_facts": Array,
      "platforms": Object,              // ArtStation, Instagram, DeviantArt, etc.
      "portfolio_url": String,          // Primary portfolio website
      "tools": Array                    // Software/tools they use
    },
    "programming": {
      "bio": String,                    // Developer bio
      "languages": Array,               // Programming languages
      "specializations": Array,         // ["web", "gamedev", "AI/ML", "systems", etc.]
      "frameworks": Array,
      "memorable_facts": Array,
      "platforms": Object,              // GitHub, GitLab, portfolio site
      "project_count": Number,
      "open_source_active": Boolean
    },
    "writing": {
      "bio": String,
      "genres": Array,                  // ["fiction", "technical", "poetry", "blog", etc.]
      "memorable_facts": Array,
      "platforms": Object,              // Medium, Substack, personal blog, etc.
      "published_works": Number,
      "writing_style": String           // Narrative voice description
    },
    "game_development": {
      "bio": String,
      "engines": Array,                 // ["Unreal", "Unity", "Godot", "Custom", etc.]
      "specializations": Array,         // ["gameplay", "graphics", "audio", "narrative", etc.]
      "memorable_facts": Array,
      "platforms": Object,              // itch.io, Steam, etc.
      "game_count": Number,
      "preferred_genres": Array         // Game genres they make
    }
  },

  "cross_domain_skills": [
    {
      "skill": "composition",           // Applicable to music + games + writing
      "proficiency": "expert",
      "domains": ["music", "game_development", "writing"]
    }
  ],

  "ai_memory": {
    "memorable_facts": Array,           // General facts not domain-specific
    "personality_traits": Array,
    "collaboration_preferences": Object,
    "creative_process": String,         // How they describe their creative approach
    "confidence_score": Number
  }
}
```python

### Database Indexes for Domain Queries

```python
{
    "creative_profile.primary_domain": 1,
    "creative_profile.active_domains": 1,
    "creative_profile.domains.music.genres": 1,
    "creative_profile.domains.art.mediums": 1,
    "creative_profile.domains.programming.languages": 1,
    "creative_profile.cross_domain_skills.skill": 1
}
```python

## User Content Registry

### Problem Statement

Users share links to their work across multiple platforms:

- **Music**: Spotify, Apple Music, SoundCloud, Bandcamp
- **Streaming**: YouTube, Twitch clips
- **Visual**: Instagram, ArtStation, DeviantArt
- **Code**: GitHub, GitLab
- **Writing**: Medium, Substack, personal blog

**Goal**: Automatically detect, verify, and cache these shared items for later promotion/sharing.

### Approach 1: Embedded Releases Array (Small Scale - Recommended)

If users typically share <100 items per year, embed in user document:

```json
{
  "releases": [
    {
      "_id": ObjectId,
      "domain": String,                 // "music", "art", "programming"
      "type": String,                   // "song", "album", "artwork", "game", "blog_post"
      "title": String,
      "url": String,                    // Direct link to content
      "platform": String,               // "spotify", "instagram", "github"
      "platform_id": String,            // Unique ID on that platform
      "user_url": String,               // Link to artist profile on platform
      "shared_at": Date,                // When user shared it with bot
      "discovered_at": Date,            // When bot first detected it
      "metadata": {
        "plays": Number,                // For music: play count
        "streams": Number,              // Spotify streams
        "likes": Number,                // Instagram likes
        "stars": Number,                // GitHub stars
        "image_url": String,            // Album art, video thumbnail, etc.
        "description": String,          // From platform
        "duration": Number              // For audio/video
      },
      "verified": Boolean,              // Did we confirm this belongs to user?
      "verification_method": String,    // "exact_url_match", "profile_owner", "manual"
      "promoted": Boolean               // Has been shared by bot/featured
    }
  ]
}
```python

### Approach 2: Separate Collection (Large Scale)

If you expect users to accumulate 500+ items, use a separate `user_releases` collection:

```json
{
  "_id": ObjectId,
  "user_id": String,                    // Reference to users collection
  "domain": String,
  "type": String,
  "title": String,
  "url": String,
  "platform": String,
  "platform_id": String,
  "user_url": String,
  "shared_at": Date,
  "discovered_at": Date,
  "metadata": Object,
  "verified": Boolean,
  "verification_method": String,
  "promoted": Boolean,
  "created_at": Date,
  "updated_at": Date
}
```python

**Recommendation**: **Start with embedded** (Approach 1) - simpler, faster queries, no joins needed. Migrate to separate collection only if data grows or you need complex analytics.

## Implementation Roadmap

### Phase 1: Current State (No Breaking Changes)

```python
creative_profile: {
    "primary_domain": "music",
    "active_domains": ["music"],
    "domains": {
        "music": {
            "bio": "...",
            "genres": [...],
            "memorable_facts": [...],
            "platforms": {...}
        }
    },
    "cross_domain_skills": [],
    "ai_memory": {...}
}

## releases array not required yet
```python

**Migration**: Optional - update existing music profiles gradually or on-demand.

### Phase 2: Add Release Tracking (3-6 months)

```python
## When user shares a link, verify and cache:

releases: [{
    "domain": "music",
    "type": "song",
    "title": "Midnight Echo",
    "url": "https://open.spotify.com/track/...",
    "platform": "spotify",
    "platform_id": "spotify_track_id",
    "user_url": "https://open.spotify.com/artist/...",
    "shared_at": <datetime>,
    "verified": True,
    "verification_method": "profile_owner",
    "metadata": {
        "streams": 1250,
        "image_url": "spotify_album_art.jpg"
    }
}]
```python

**Benefits**:

- Automatic portfolio building
- Shareable content library
- Growth tracking over time
- No manual data entry

### Phase 3: Multi-Domain Support (6-12 months)

```python
creative_profile.active_domains: ["music", "art"]

domains.art: {
    "mediums": ["digital", "pixel art"],
    "styles": ["anime", "pixel animation"],
    "platforms": {
        "instagram": {...},
        "artstation": {...}
    }
}

## Art releases tracked automatically
## Existing music code unchanged
```python

### Phase 4: Future Extensions

- Cross-domain collaborations (musician + visual artist)
- Domain transition tracking (DJ → music producer)
- Skill graphs (who's skilled in composition across domains?)
- Content recommendations by domain
- Archival tracking (track deleted/historical content)

## URL Extraction & Verification Strategy

### Supported Platforms (Extensible Pattern)

```python
PLATFORM_CONFIGS = {
    "spotify": {
        "domains": ["open.spotify.com", "spotify.com"],
        "patterns": [
            r"spotify\.com/(track | album)/(\w+)",
            r"open\.spotify\.com/artist/(\w+)"
        ],
        "api": "https://api.spotify.com/v1",
        "content_types": ["song", "album", "playlist"],
        "verification": "artist_profile_match"
    },
    "youtube": {
        "domains": ["youtube.com", "youtu.be"],
        "patterns": [
            r"youtube\.com/watch\?v=([^&]+)",
            r"youtu\.be/([^?]+)"
        ],
        "api": "https://www.youtube.com/oembed",
        "content_types": ["video", "clip", "stream"],
        "verification": "channel_owner_match"
    },
    "instagram": {
        "domains": ["instagram.com"],
        "patterns": [r"instagram\.com/p/([^/?]+)"],
        "api": "https://graph.instagram.com",
        "content_types": ["post", "reel", "story"],
        "verification": "profile_owner_match"
    },
    "soundcloud": {
        "domains": ["soundcloud.com"],
        "patterns": [r"soundcloud\.com/(\w+)/(\w+)"],
        "api": "https://api.soundcloud.com",
        "content_types": ["track", "playlist"],
        "verification": "artist_profile_match"
    },
    "github": {
        "domains": ["github.com"],
        "patterns": [r"github\.com/([\w-]+)/([\w-]+)"],
        "api": "https://api.github.com",
        "content_types": ["repository", "release"],
        "verification": "repo_owner_match"
    }
}
```python

### Verification Workflow

```python
async def verify_and_track_release(user_id, shared_url):
    """
    Workflow:

    1. Extract platform and content ID from URL
    2. Query platform API for metadata & owner
    3. Check if owner matches user's profile on that platform
    4. If verified, add to releases array
    """

    user = Users.get_collection().find_one({"user_id": user_id})
    platform = extract_platform_from_url(shared_url)
    config = PLATFORM_CONFIGS[platform]

    # Extract content ID
    content_id = re.search(config["patterns"][0], shared_url)

    # Query platform API
    metadata = await query_api(config["api"], content_id, platform)

    # Verify ownership
    user_profile = user["creative_accounts"][platform]
    content_owner = metadata["owner_url"]

    if normalize_url(user_profile["url"]) == normalize_url(content_owner):
        # Add to releases
        release_doc = {
            "domain": DOMAIN_MAP[platform],  # spotify → music, github → programming
            "type": infer_content_type(metadata),
            "title": metadata["title"],
            "url": shared_url,
            "platform": platform,
            "platform_id": content_id,
            "user_url": user_profile["url"],
            "shared_at": datetime.utcnow(),
            "verified": True,
            "verification_method": "profile_owner",
            "metadata": {
                "plays": metadata.get("plays"),
                "image_url": metadata.get("image_url")
            }
        }

        Users.get_collection().update_one(
            {"user_id": user_id},
            {"$push": {"releases": release_doc}}
        )

        return {"status": "tracked", "title": metadata["title"]}
    else:
        return {"status": "unverified", "reason": "owner_mismatch"}
```python

## Query Patterns

### Find Users by Domain

```python
## All musicians
Users.get_collection().find({
    "creative_profile.active_domains": "music"
})

## Musicians interested in synthwave
Users.get_collection().find({
    "creative_profile.domains.music.genres": "synthwave"
})

## Programmers who also do game dev
Users.get_collection().find({
    "creative_profile.active_domains": {
        "$all": ["programming", "game_development"]
    }
})
```python

### Content Discovery

```python
## User's latest releases
Users.get_collection().aggregate([
    {"$match": {"user_id": user_id}},
    {"$project": {
        "latest_releases": {
            "$slice": ["$releases", -10]  // Last 10
        }
    }}
])

## Trending releases this week
Users.get_collection().find({
    "releases": {
        "$elemMatch": {
            "verified": True,
            "shared_at": {"$gte": one_week_ago}
        }
    }
})

## All unverified content
Users.get_collection().find({
    "releases.verified": False
})
```python

## Why This Architecture

✅ **No Breaking Changes** - Existing music profiles work as-is
✅ **Extensible** - Add domains/platforms without migration
✅ **Query Efficient** - Indexes support all common queries
✅ **Scalable** - Start embedded, migrate to separate collection if needed
✅ **Privacy Aware** - Content only added if user shares it
✅ **Promotion Ready** - Automatic portfolio building
✅ **Future Proof** - Supports cross-domain collaboration, domain transitions, etc.
````
