# Universal User Profile Architecture

## Overview

The **users collection** is now the central nexus for all user identity and profile management. This is a fundamental architectural shift that enables Abby to scale from a Discord bot to a comprehensive multi-artist platform.

### Core Philosophy

- **Single Source of Truth**: One user profile document contains all identity data
- **Platform Agnostic**: Discord, Twitter, YouTube, Spotify, etc. are all adapters
- **Multi-Artist Support**: Built for tracking artists over 20+ years with collaborations
- **Extensible**: New platforms and social accounts can be added without schema changes

## Data Structure

### Base User Profile

```javascript
{
  "user_id": 123456,           // Unique internal ID
  "discord_id": 987654321,     // Discord user ID (nullable)
  "email": "user@example.com", // Email address (unique, sparse)
  "username": "cool_artist",   // Display username
  "avatar_url": "...",         // Avatar image URL
  "created_at": "2024-01-01",  // Account creation
  "updated_at": "2024-01-15",  // Last profile update
  "profile_visibility": "public" // "public" or "private"
}
```python

### Guild Membership

```javascript
{
  "guilds": [123, 456, 789]    // List of Discord guild IDs user is in
}
```python

### Social Account Integration

Connect user's social profiles (YouTube, Twitter, Twitch, Instagram, TikTok, etc.):

```javascript
{
  "social_accounts": [
    {
      "platform": "youtube",    // youtube, twitter, twitch, tiktok, instagram, etc
      "handle": "@cool_artist", // Username/handle on platform
      "url": "https://youtube.com/@cool_artist",
      "added_at": "2024-01-01",
      "verified": false         // OAuth verification status
    },
    {
      "platform": "twitter",
      "handle": "cool_artist",
      "url": "https://twitter.com/cool_artist",
      "added_at": "2024-01-02",
      "verified": true
    },
    {
      "platform": "twitch",
      "handle": "cool_artist",
      "url": "https://twitch.tv/cool_artist",
      "added_at": "2024-01-03",
      "verified": false
    }
  ]
}
```python

### Creative Account Integration

Connect to music and content platforms (Spotify, Apple Music, SoundCloud, Bandcamp):

```javascript
{
  "creative_accounts": [
    {
      "platform": "spotify",
      "account_id": "spotify_user_id_123",
      "display_name": "Cool Artist",
      "connected_at": "2024-01-05",
      "verified": true,
      "access_token_expires": "2024-02-04"
    },
    {
      "platform": "apple_music",
      "account_id": "am_user_123",
      "display_name": "Cool Artist",
      "connected_at": "2024-01-06",
      "verified": true,
      "access_token_expires": "2024-04-05"
    },
    {
      "platform": "soundcloud",
      "account_id": "cool-artist",
      "display_name": "Cool Artist",
      "connected_at": "2024-01-07",
      "verified": true,
      "access_token_expires": null
    }
  ]
}
```python

### Artist Profile

Enable artist-specific features and metadata:

```javascript
{
  "artist_profile": {
    "is_artist": true,
    "stage_name": "Cool Artist",
    "bio": "Making cool music since 2020",
    "website": "https://coolartist.com",
    "links": {
      "bandcamp": "https://coolartist.bandcamp.com",
      "merch": "https://shop.coolartist.com"
    },
    "established_at": "2020-06-15"
  }
}
```python

### Collaborations (Multi-Artist Support)

Track collaborations with other artists:

```javascript
{
  "collaborations": [
    {
      "artist_id": 654321,          // User ID of collaborating artist
      "status": "active",           // "pending", "active", "archived"
      "started_at": "2023-06-01",
      "projects": [
        {
          "project_id": "proj_123",
          "title": "Summer Collab EP",
          "status": "released",
          "released_at": "2023-08-15"
        }
      ]
    }
  ]
}
```python

### Preferences & Privacy

```javascript
{
  "preferences": {
    "show_socials": true,
    "show_collaborations": true,
    "notifications_enabled": true,
    "language": "en"
  }
}
```python

## API Functions

### Core CRUD

```python
from abby_core.database.collections.users import Users

## Get user profile
user = Users.get_collection().find_one({"user_id": 123456})

## Create/update user
Users.upsert_user(123456, {
    "username": "cool_artist",
    "discord_id": 987654321,
    "email": "user@example.com"
})

## Add guild membership
Users.add_guild_to_user(123456, guild_id)
```python

### Social Account Management

```python
from abby_core.database.collections.users import Users

## Add social account
Users.add_social_account(
    user_id=123456,
    platform="youtube",
    handle="@cool_artist",
    url="https://youtube.com/@cool_artist"
)

## Remove social account
Users.remove_social_account(user_id=123456, platform="youtube")

## Get all social accounts
socials = Users.get_social_accounts(user_id=123456)
```python

### Creative Account Management

```python
## Add creative account (Spotify, Apple Music, etc)
Users.add_creative_account(
    user_id=123456,
    platform="spotify",
    account_id="spotify_user_id_123",
    display_name="Cool Artist"
)

## Remove creative account
Users.remove_creative_account(user_id=123456, platform="spotify")

## Get all creative accounts
creatives = Users.get_creative_accounts(user_id=123456)
```python

### Artist Profile Management

```python
## Enable artist profile
Users.set_artist_profile(
    user_id=123456,
    stage_name="Cool Artist",
    bio="Making cool music since 2020",
    website="https://coolartist.com"
)

## Add collaboration with another artist
Users.add_collaboration(
    user_id=123456,
    collab_artist_id=654321,
    status="pending"
)
```python

## Database Indexes

All indexed fields for optimal query performance:

```javascript
// Core identification
db.discord_profiles.createIndex({ user_id: 1 }, { unique: true });
db.discord_profiles.createIndex(
  { discord_id: 1 },
  { unique: true, sparse: true },
);
db.discord_profiles.createIndex({ email: 1 }, { unique: true, sparse: true });

// Temporal queries
db.discord_profiles.createIndex({ created_at: -1 });
db.discord_profiles.createIndex({ updated_at: -1 });

// Guild membership
db.discord_profiles.createIndex({ guilds: 1 });

// Social account lookups
db.discord_profiles.createIndex({ "social_accounts.platform": 1 });
db.discord_profiles.createIndex({ "social_accounts.handle": 1 });
db.discord_profiles.createIndex({ "social_accounts.url": 1 });

// Creative account lookups
db.discord_profiles.createIndex({ "creative_accounts.platform": 1 });
db.discord_profiles.createIndex({ "creative_accounts.account_id": 1 });

// Artist profile queries
db.discord_profiles.createIndex({ "artist_profile.stage_name": 1 });
db.discord_profiles.createIndex({ "artist_profile.is_artist": 1 });

// Multi-artist collaboration
db.discord_profiles.createIndex({ "collaborations.artist_id": 1 });
db.discord_profiles.createIndex({ "collaborations.status": 1 });
```python

## Migration Strategy

### Backward Compatibility

The users collection still uses the `discord_profiles` collection name internally for backward compatibility with existing code. The architecture is abstracted through collection modules, making future migrations seamless.

### Existing Data

All existing Discord user profiles remain compatible with the new schema. New fields will be added on-demand:

```python
## When updating a user, new fields are automatically initialized
user_data = {
    "username": "cool_artist",
    "discord_id": 987654321,
}

Users.upsert_user(user_id, user_data)
## Result: social_accounts=[], creative_accounts=[], artist_profile={is_artist: false}
```python

## Use Cases

### Social Link Discovery

Find artists and their social profiles by platform:

```python
## Find all users with YouTube channels
artists = collection.find({
    "social_accounts.platform": "youtube"
})

## Find user by Twitter handle
user = collection.find_one({
    "social_accounts": {
        "$elemMatch": {
            "platform": "twitter",
            "handle": "cool_artist"
        }
    }
})
```python

### Artist Directory

Build artist profiles with all their connected accounts:

```python
artist = collection.find_one({"user_id": 123456})

print(f"Artist: {artist['artist_profile']['stage_name']}")
print(f"Social: {[s['url'] for s in artist['social_accounts']]}")
print(f"Music: {[c['platform'] for c in artist['creative_accounts']]}")
```python

### Collaboration Network

Track multi-artist projects and collaborations:

```python
## Find all active collaborations for an artist
artist = collection.find_one({"user_id": 123456})
collabs = [c for c in artist['collaborations'] if c['status'] == 'active']

## Follow collaboration chains
for collab in collabs:
    partner = collection.find_one({"user_id": collab['artist_id']})
    print(f"Collaborating with: {partner['artist_profile']['stage_name']}")
```python

## Future Expansions

This architecture supports future additions without schema migration:

- **Label/Collective Support**: Add `label_membership` array
- **Verification Badges**: Add `verified_badges` array for platform verification
- **Analytics Integration**: Add `analytics_accounts` for YouTube Analytics, Spotify for Artists
- **Payment Methods**: Add `payment_methods` for multi-platform royalty tracking
- **Event Calendars**: Add `event_calendar` for tour dates, releases, streams
- **Fan Community**: Add `fan_community_id` to link to fan server

## Best Practices

1. **Always use the collection module** - Never access `db["discord_profiles"]` directly
2. **Platform names are lowercase** - "youtube", "spotify", not "YouTube", "Spotify"
3. **URLs should be complete** - Include `https://` and full path
4. **Verify before trusting** - OAuth connections set `verified: true`
5. **Handle sparse fields** - Not all users have email, creative accounts, etc.
6. **Update timestamps** - Always refresh `updated_at` when modifying profiles

## Architecture Benefits

✅ **Scalability** - Single schema supports infinite platform additions  
✅ **Maintainability** - All user data in one place, unified CRUD operations  
✅ **Multi-Artist** - Native collaboration and project tracking support  
✅ **Extensibility** - Add new fields without code changes (schema flexibility)  
✅ **Analytics** - All user touchpoints in one document for comprehensive analysis  
✅ **Security** - Centralized access control and privacy management  
✅ **Future-Proof** - Built for 20+ year platform lifecycle

## References

- [collections/**init**.py](abby_core/database/collections/__init__.py) - All 34 collection modules
- [users.py](abby_core/database/collections/users.py) - Universal profile module
- [COLLECTION_INVENTORY.md](COLLECTION_INVENTORY.md) - Canonical collection ownership
- [ARCHITECTURE.md](ARCHITECTURE.md) - Data layer architecture and patterns
