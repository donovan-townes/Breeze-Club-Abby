## Bug Fix: Profile Display Name Shows Guild Nickname Instead of Discord Display Name

**Issue**: The `/profile` command was showing a guild nickname (e.g., "dOnOvAn" from prod) instead of the user's Discord display name (e.g., "Z8phyR") when viewing the universal profile.

**Root Cause**:
The profile title was using `discord_info.get('display_name')` which could potentially be contaminated if any code path was accidentally storing a guild nickname in the `discord` object instead of keeping it in the `guilds` array where it belongs.

**Schema Clarification**:
The universal user profile stores:

- **Discord-specific data**: `discord { display_name, username, avatar_url, ... }` - NEVER contains guild nicknames
- **Guild memberships**: `guilds[] { guild_id, guild_name, nickname, ... }` - Contains guild-specific nickname if set

**Fixes Applied**:

### 1. **Profile Panel Enhanced** (`profile_panel_enhanced.py`)

- **Line 139-149**: Extracted display_name logic to be explicit
  - Now clearly states "use Discord display_name, never guild nickname"
  - Falls back to `interaction.user.display_name` if database field is missing
- **Line 77-120**: Enhanced guild update logic
  - When adding/updating guilds, now ALWAYS ensures `discord.display_name` is set to current Discord display name
  - Never allows guild nickname to overwrite `discord.display_name`
  - Added comments emphasizing the separation: "NEVER store nickname in discord object"

### 2. **Chatbot Service** (`chatbot.py`)

- **Line 159-191**: Added explicit docstring warning
  - Clarifies that `metadata["nickname"]` gets stored in `guilds[].nickname`, not in discord object
  - Reinforces that `discord.display_name` is always the Discord display name, never a guild nickname

**Testing**:
To verify the fix:

1. Create a user profile in dev database with null nickname
2. Switch to a guild and run `/profile`
3. Switch to a different guild with a guild nickname set
4. Run `/profile` again
5. Verify the title always shows Discord display name ("Z8phyR"), not guild nickname ("dOnOvAn")
6. Verify guild-specific info still shows correct nickname in `guilds` array

**Prevention**:

- Always use `discord.display_name` for profile title/identity
- Guild nicknames should ONLY be read from `guilds[].nickname`
- Added defensive code to always update `discord.display_name` when profile is accessed
