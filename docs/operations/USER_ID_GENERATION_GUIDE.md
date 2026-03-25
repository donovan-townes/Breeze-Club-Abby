# User ID Generation & Platform Linking Guide

## Quick Reference

### ID Types

| Type | Format | Example | Function | Use Case |
| -------- | -------------- | ---------------------------------------- | --------------------------- | ------------- |
| Discord | Numeric String | `"246030816692404234"` | `is_discord_id(id)` → True | Discord users |
| Web UUID | UUID v4 | `"550e8400-e29b-41d4-a716-446655440000"` | `is_discord_id(id)` → False | Web app users |

### Helper Functions (in `abby_core.database.collections.users`)

```python
## Generate a new user ID for web app users
user_id = generate_user_id()  # Returns UUID v4

## Check if ID is Discord or UUID
is_discord_id("246030816692404234")  # True
is_discord_id("550e8400-e29b-41d4-a716-446655440000")  # False

## Get ID type for logging/routing
get_id_type(user_id)  # Returns "discord", "uuid", or "unknown"
```python

## Common Scenarios

### Scenario 1: Discord User First Time (Current)

```python
from abby_core.database.collections.users import Users
from datetime import datetime

interaction = ...  # Discord interaction
user_id = str(interaction.user.id)  # Use Discord ID directly: "246030816692404234"

Users.get_collection().insert_one({
    "user_id": user_id,  # Discord ID as user_id
    "discord": {
        "discord_id": user_id,
        "username": interaction.user.name,
        "display_name": interaction.user.display_name,
        "discriminator": interaction.user.discriminator or "0",
        "avatar_url": str(interaction.user.display_avatar.url),
        "joined_at": datetime.utcnow(),
        "last_seen": datetime.utcnow()
    },
    "guilds": [...],
    "creative_profile": {...},
    "social_accounts": [],
    "creative_accounts": [],
    "artist_profile": {},
    "collaborations": [],
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
})
```python

### Scenario 2: Web App User Registration (Future)

```python
from abby_core.database.collections.users import generate_user_id, Users
from datetime import datetime
import bcrypt

## User submits web form
email = request.form.get("email")
password = request.form.get("password")
username = request.form.get("username")

## Generate unique ID for this web user
user_id = generate_user_id()  # UUID: "550e8400-e29b-41d4-a716-446655440000"

## Hash password (never store plaintext!)
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

Users.get_collection().insert_one({
    "user_id": user_id,  # UUID as user_id
    "web": {
        "email": email,
        "username": username,
        "password_hash": password_hash,
        "avatar_url": None,  # Set later if user uploads
        "email_verified": False,  # Require email verification
        "joined_at": datetime.utcnow(),
        "last_seen": datetime.utcnow()
    },
    "guilds": [],
    "creative_profile": {...},
    "social_accounts": [],
    "creative_accounts": [],
    "artist_profile": {},
    "collaborations": [],
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
})

## Send verification email to user.email
```python

### Scenario 3: Web User Links Discord (Linking)

```python
from abby_core.database.collections.users import Users
from datetime import datetime

## Web user clicks "Link Discord" and goes through OAuth
web_user_id = session.get("user_id")  # UUID from web session
interaction = ...  # Discord interaction

Users.get_collection().update_one(
    {"user_id": web_user_id},  # Find by original UUID
    {"$set": {
        "discord": {  # Add Discord object
            "discord_id": str(interaction.user.id),
            "username": interaction.user.name,
            "display_name": interaction.user.display_name,
            "discriminator": interaction.user.discriminator or "0",
            "avatar_url": str(interaction.user.display_avatar.url),
            "joined_at": datetime.utcnow(),  # When Discord was linked
            "last_seen": datetime.utcnow()
        },
        "updated_at": datetime.utcnow()
    }}
)

## User now has both web and discord objects
## Same user_id (UUID) for all operations
```python

### Scenario 4: Update Activity on Platform

```python
from abby_core.database.collections.users import Users
from datetime import datetime

user_id = ...  # Can be Discord ID or UUID
guild_id = str(interaction.guild.id) if interaction.guild else None

## Update Discord last_seen for user
Users.get_collection().update_one(
    {"user_id": user_id},
    {"$set": {
        "discord.last_seen": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }}
)

## Update guild last_seen
if guild_id:
    Users.get_collection().update_one(
        {"user_id": user_id, "guilds.guild_id": guild_id},
        {"$set": {
            "guilds.$.last_seen": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
```python

### Scenario 5: Lookup User by Platform ID

```python
from abby_core.database.collections.users import Users

## Find Discord user
discord_user = Users.get_collection().find_one({
    "discord.discord_id": "246030816692404234"
})

## Find web user by email
web_user = Users.get_collection().find_one({
    "web.email": "user@example.com"
})
```python

## Schema Validation

When creating/updating users, ensure:

1. **user_id exists and is valid**
   - Discord: numeric string ✓
   - Web: UUID v4 ✓

1. **At least one platform object**
   - Discord users need `discord` object ✓
   - Web users need `web` object ✓
   - Linked users have both ✓

1. **Required platform fields**

   ```python
   discord: {
       "discord_id": str,        # Required
       "username": str,          # Required
       "display_name": str,      # Required
       "discriminator": str,     # Required
       "avatar_url": str,        # Required
       "joined_at": datetime,    # Required
       "last_seen": datetime     # Required
   }

   web: {
       "email": str,             # Required
       "username": str,          # Required
       "password_hash": str,     # Required (NEVER plaintext)
       "avatar_url": str,        # Required
       "email_verified": bool,   # Required
       "joined_at": datetime,    # Required
       "last_seen": datetime     # Required
   }
   ```

1. **Universal fields present**
   ```python
   {
       "user_id": str,
       "guilds": list,
       "creative_profile": dict,
       "social_accounts": list,
       "creative_accounts": list,
       "artist_profile": dict,
       "collaborations": list,
       "created_at": datetime,
       "updated_at": datetime
   }
   ```

## Querying Tips

### Find all Discord users in a guild

```python
Users.get_collection().find({
    "guilds.guild_id": guild_id,
    "discord.discord_id": {"$exists": True}
})
```python

### Find all web users (no Discord)

```python
Users.get_collection().find({
    "web.email": {"$exists": True},
    "discord.discord_id": {"$exists": False}
})
```python

### Find all verified web users

```python
Users.get_collection().find({
    "web.email_verified": True
})
```python

### Find users active in last 7 days (any platform)

```python
from datetime import datetime, timedelta

threshold = datetime.utcnow() - timedelta(days=7)

Users.get_collection().find({
    "$or": [
        {"discord.last_seen": {"$gte": threshold}},
        {"web.last_seen": {"$gte": threshold}}
    ]
})
```python

### Find users by social media handle

```python
Users.get_collection().find({
    "social_accounts": {
        "$elemMatch": {
            "platform": "twitter",
            "handle": "@z8phyr_"
        }
    }
})
```python

## Index Performance

- **user_id lookups**: O(1) - unique indexed ✓
- **Discord lookups**: O(1) - unique indexed ✓
- **Email lookups**: O(1) - unique indexed ✓
- **Guild queries**: Indexed on `guilds.guild_id` ✓
- **Activity queries**: Indexed on `discord.last_seen`, `web.last_seen` ✓

## Migration Path (Existing → Future)

1. **Phase 1 (Current)**: Discord users with user_id = Discord ID
2. **Phase 2 (Next)**: Add web platform support, new users get UUID
3. **Phase 3 (Later)**: Support linking (web user + Discord)
4. **Phase 4 (Future)**: Add more platforms (GitHub, Twitch, etc.)

No breaking changes needed! Existing Discord functionality continues to work while new web features are added.
