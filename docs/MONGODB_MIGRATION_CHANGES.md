# MongoDB Unified Client Migration - Code Changes

## Overview

This document details all code changes made to migrate from legacy per-user MongoDB databases to the unified tenant-scoped schema.

## Date

2024-01-XX

## Changes Summary

### 1. Banking/bank_central.py

**Changed:**

- **Imports**: Replaced `from utils.mongo_db import *` with unified client imports from `abby-core.utils.mongo_db`
- **Initialization**: Removed `econ_init()` method and separate database connection - unified client handles connection pooling
- **Functions Updated**:
  - `__init__()`: No longer creates separate database connection
  - `bank_update()`: Temporarily disabled pending tenant-aware iteration pattern (marked with TODO)
  - `cooldown_check()`: Uses `get_economy(user_id)` instead of direct collection access
  - `balance()`: Uses `get_economy(user_id)` with automatic tenant scoping
  - `deposit()`: Uses `update_balance(user_id, wallet_delta=-amount, bank_delta=amount)` for atomic updates
  - `withdraw()`: Uses `update_balance(user_id, wallet_delta=amount, bank_delta=-amount)` for atomic updates
  - `list_service()`: Uses `update_balance(user_id, wallet_delta=-price)` for atomic updates

**Key Improvements:**

- All operations now tenant-scoped automatically
- Atomic balance updates prevent race conditions
- User IDs converted to strings for consistency
- Added logging with tenant_id visibility

### 2. Exp/xp_handler.py

**Changed:**

- **Imports**: Replaced legacy `connect_to_mongodb()` with unified client imports (`get_xp`, `add_xp`, `get_xp_collection`, `get_tenant_id`)
- **Removed Function**: `get_user_exp(user_id)` - replaced by unified client's `get_xp()`
- **Functions Updated**:
  - `initialize_xp()`: Uses `add_xp(user_id, 0, "initialization")` instead of direct collection insert
  - `get_user_level()`: Uses `get_xp(user_id)` instead of per-user database access
  - `reset_exp()`: Uses `get_xp_collection()` with tenant_id queries for reset operations
  - `increment_xp()`: Uses `add_xp(user_id, increment, "message")` with automatic tenant scoping
  - `decrement_xp()`: Uses `add_xp()` with negative delta and max(0, result) to prevent negative XP
  - `get_xp()`: Renamed to `get_xp_points()` to avoid conflict with unified client function
  - `check_thresholds()`: Updated to use unified client with `get_xp()` and direct collection access for level updates
  - `update_old_users()`: Deprecated with warning - no longer needed with unified schema
  - `fetch_all_users_exp()`: Queries unified xp collection with tenant*id filter instead of iterating User*{id} databases

**Key Improvements:**

- Eliminated per-user database pattern (`User_{id}`)
- All XP operations now tenant-scoped
- Consistent string conversion for user_ids
- Deprecated legacy migration functions

### 3. Chatbot/chatbot.py

**Changed:**

- **Imports**: Replaced `import utils.mongo_db as mongo_db` with unified client imports (`create_session`, `append_session_message`, `close_session`, `get_sessions_collection`, `get_tenant_id`, `upsert_user`)
- **Initialization**: Removed `self.client = mongo_db.connect_to_mongodb()` - unified client handles pooling
- **Functions Updated**:
  - `__init__()`: No longer creates separate MongoDB client
  - `user_update_chat_history()`: Uses `append_session_message(user_id, session_id, user_input, response)` with automatic encryption
  - `end_summary()`: Uses `close_session(user_id, session_id, summary)` to mark session complete with summary
  - `initalize_user()`:
    - Uses `upsert_user(user_id, {"username": message.author.name})` to update user metadata
    - Queries `get_sessions_collection()` with tenant_id filter to get last completed session
    - Uses `create_session(user_id, session_id, channel_id)` to start new session
    - Retrieves last summary from previous completed session instead of separate summary collection

**Key Improvements:**

- Sessions now tenant-scoped in unified collection
- Message encryption handled automatically by unified client
- Session lifecycle tracked with status field (active/completed)
- Last summary retrieved from most recent completed session
- Consistent tenant isolation across all operations

## Migration Notes

### Before Migration

- **Banking**: Used separate "Abby_Economy" database with "Abby_Bank" collection
- **XP**: Used per-user databases (`User_{user_id}`) with "EXP" collection
- **Chatbot**: Used per-user databases with "Conversations"/"Chat Logs" collections

### After Migration

- **Banking**: Uses unified "Abby" database → "economy" collection with tenant_id scoping
- **XP**: Uses unified "Abby" database → "xp" collection with tenant_id + user_id compound key
- **Chatbot**: Uses unified "Abby" database → "sessions" collection with tenant_id + session_id + user_id compound key

## Testing Requirements

1. **Banking Commands**:

   - Test `/balance` command with new unified client
   - Test `/deposit` and `/withdraw` with atomic balance updates
   - Verify tenant_id is automatically included in all queries

2. **XP System**:

   - Test XP gain from messages (increment_xp)
   - Test level-up detection (check_thresholds)
   - Test leaderboard (fetch_all_users_exp with tenant filter)

3. **Chatbot**:
   - Test new conversation initialization
   - Test message history persistence
   - Test session summary on dismissal
   - Verify last summary retrieval from previous session

## Rollback Plan

If issues are discovered:

1. Keep legacy code in `legacy-outdated/` folder
2. Revert imports to use `utils.mongo_db` (old client)
3. Run migration script in reverse (unified → per-user DBs) - not yet implemented

## Next Steps

1. **Run Migration Script**: Execute `docs/migration_script.py` to migrate existing data
2. **Create Indexes**: Run `python -m abby-core.utils.init_indexes` to create all indexes
3. **Test with Sample Data**: Verify all functionality works with migrated data
4. **Monitor Production**: Watch logs for tenant_id presence in all MongoDB operations
5. **Deprecate Legacy Code**: Move old `utils/mongo_db.py` to `legacy-outdated/`

## TDOS Compliance

All changes ensure TDOS v1.5 compliance:

- ✅ **INV-006**: All MongoDB operations include tenant_id
- ✅ **INV-007**: User data scoped by tenant_id + user_id compound key
- ✅ **INV-008**: Sessions scoped by tenant_id + session_id + user_id
- ✅ **Event Emission**: All operations can emit TDOS events via `tdos_events.py`

## Contributors

- GitHub Copilot (Phase 2 Implementation)

## References

- `abby-core/utils/mongo_db.py` - Unified MongoDB client
- `abby-core/utils/mongo_schemas.py` - Collection schemas
- `docs/migration_script.py` - Data migration tool
- `PLAN_ABBY.md` - Overall modernization plan
