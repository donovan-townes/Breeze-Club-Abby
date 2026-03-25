# MongoDB Collection Inventory

**Purpose:** Canonical reference for all MongoDB collections, their owners, lifecycles, and migration status.

**Last Updated:** February 1, 2026

---

## Legend

- **Status:** `ACTIVE` (in use), `DEPRECATED` (migrate away), `LEGACY` (low/no usage), `PLANNED` (future)
- **Write Frequency:** `HIGH` (>100/day), `MEDIUM` (10-100/day), `LOW` (<10/day), `RARE` (manual only)
- **Lifecycle:** `PERSISTENT` (never delete), `TRANSIENT` (auto-expire), `ARCHIVE` (move to cold storage)

---

## Core Collections (Active)

### 1. `system_state`

- **Purpose:** Canonical system states (seasons, events, eras, modes)
- **Owner:** [abby_core/system/system_state.py](../abby_core/system/system_state.py)
- **Fields:** `state_id`, `state_type`, `key`, `label`, `canon_ref`, `active`, `start_at`, `end_at`, `effects`, `metadata`, `created_at`, `activated_at`, `activated_by`
- **Indexes:** `state_id` (unique), `state_type + active`, `start_at + end_at`
- **Write Frequency:** LOW (operator-driven, seasonal changes)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 2. `system_state_instances`

- **Purpose:** Activation instances of system states (global, guild, user scoped)
- **Owner:** [abby_core/system/state_instance_sync.py](../abby_core/system/state_instance_sync.py)
- **Fields:** `state_id`, `state_type`, `scope`, `active`, `priority`, `start_at`, `end_at`, `activated_at`, `activated_by`
- **Indexes:** `state_id`, `scope + active`, `start_at + end_at`
- **Write Frequency:** LOW (synced from `system_state`)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 3. `content_delivery_items`

- **Purpose:** Unified lifecycle for announcements, world updates, social posts
- **Owner:** [abby_core/services/content_delivery.py](../abby_core/services/content_delivery.py)
- **Fields:** `guild_id`, `content_type`, `trigger_type`, `title`, `description`, `payload`, `context_refs`, `idempotency_key`, `scheduled_at`, `priority`, `delivery_channel_id`, `delivery_roles`, `lifecycle_state`, `generation_status`, `delivery_status`, `generated_message`, `error_message`, `delivery_result`, `created_at`, `updated_at`
- **Indexes:** `guild_id + trigger_type + scheduled_at`, `lifecycle_state + generation_status`
- **Write Frequency:** MEDIUM (daily announcements, events)
- **Lifecycle:** ARCHIVE (after 90 days)
- **Status:** ✅ ACTIVE

---

### 4. `chat_sessions`

- **Purpose:** Conversation sessions with encrypted messages
- **Owner:** [abby_core/database/session_repository.py](../abby_core/database/session_repository.py)
- **Fields:** `_id` (session UUID), `user_id`, `guild_id`, `channel_id`, `messages[]`, `summary`, `status`, `state`, `turn_count`, `last_message_at`, `cooldown_until`, `tags`, `created_at`, `closed_at`
- **Indexes:** `user_id`, `user_id + guild_id`, `status`, `state`
- **Write Frequency:** HIGH (every user message)
- **Lifecycle:** ARCHIVE (after session closed + 30 days)
- **Status:** ✅ ACTIVE

---

### 5. `user_xp`

- **Purpose:** User experience points, levels, and award history
- **Owner:** [abby_core/economy/xp.py](../abby_core/economy/xp.py)
- **Fields:** `user_id`, `guild_id`, `points`, `level`, `last_award_at`, `sources[]` (type, delta, ts)
- **Indexes:** `user_id + guild_id`, `guild_id + points`, `guild_id + level`
- **Write Frequency:** HIGH (every qualified message/action)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 6. `economy`

- **Purpose:** User economy (wallets, banks, transactions, tipping)
- **Owner:** [abby_core/economy/services/](../abby_core/economy/services/)
- **Fields:** `user_id`, `guild_id`, `wallet_balance`, `bank_balance`, `last_daily`, `tip_budget_used`, `tip_budget_reset`, `transactions[]` (amount, type, ts, note)
- **Indexes:** `user_id + guild_id`, `guild_id + wallet_balance`, `guild_id + bank_balance`
- **Write Frequency:** MEDIUM (commands, rewards, purchases)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 7. `rag_documents`

- **Purpose:** RAG corpus documents with embeddings (knowledge retrieval)
- **Owner:** [abby_core/rag/](../abby_core/rag/)
- **Fields:** `_id`, `tenant_id`, `source`, `title`, `text`, `metadata`, `embedding_key`
- **Indexes:** `tenant_id`, `tenant_id + source`, `tenant_id + metadata.tags`, `tenant_id + embedding_key`
- **Write Frequency:** LOW (ingestion jobs)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 8. `guild_configuration`

- **Purpose:** Guild-level preferences and settings
- **Owner:** [abby_core/database/guild_configuration.py](../abby_core/database/guild_configuration.py)
- **Fields:** `guild_id`, `schema_version`, `features` (memory, announcements, economy), `channels`, `roles`, `settings`, `created_at`, `updated_at`
- **Indexes:** `guild_id` (unique)
- **Write Frequency:** LOW (operator changes, guild joins)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 9. `scheduler_jobs`

- **Purpose:** Background job configurations and execution tracking
- **Owner:** [abby_core/services/scheduler.py](../abby_core/services/scheduler.py)
- **Fields:** `job_type`, `enabled`, `schedule` (type, time, every_minutes, etc.), `last_run_at`, `guild_id`, `config`, `created_at`, `updated_at`
- **Indexes:** `job_type + enabled`, `guild_id + job_type`, `last_run_at`
- **Write Frequency:** MEDIUM (job ticks, updates)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 10. `system_operations`

- **Purpose:** Audited system mutations (XP reset, level adjustments, etc.)
- **Owner:** [abby_core/system/system_operations.py](../abby_core/system/system_operations.py)
- **Fields:** `operation_id`, `operation_type`, `status`, `operator_id`, `reason`, `context`, `target_users`, `affected_count`, `snapshot_ids`, `created_at`, `applied_at`, `rolled_back_at`
- **Indexes:** `operation_id` (unique), `operation_type + status`, `created_at`
- **Write Frequency:** LOW (operator actions)
- **Lifecycle:** PERSISTENT (audit trail)
- **Status:** ✅ ACTIVE

---

### 11. `operation_snapshots`

- **Purpose:** Pre-mutation state backups for rollback
- **Owner:** [abby_core/system/system_operations.py](../abby_core/system/system_operations.py)
- **Fields:** `snapshot_id`, `operation_id`, `collection_name`, `document_id`, `original_state`, `created_at`
- **Indexes:** `operation_id`, `snapshot_id` (unique)
- **Write Frequency:** LOW (matches `system_operations`)
- **Lifecycle:** ARCHIVE (after operation confirmed + 90 days)
- **Status:** ✅ ACTIVE

---

### 12. `generation_audit` (Phase 2)

- **Purpose:** Permanent audit trail of all LLM generations with cost tracking and observability
- **Owner:** [abby_core/services/generation_audit_service.py](../abby_core/services/generation_audit_service.py)
- **Fields:** `session_id` (uuid4), `input_tokens` (int), `output_tokens` (int), `total_cost_usd` (float), `latency_ms` (int), `provider` (enum: openai | anthropic | ollama), `model` (str), `timestamp` (ISO8601), `user_id` (snowflake), `guild_id` (snowflake), `intent` (str), `turn_number` (int)
- **Indexes:** `timestamp`, `session_id`, `user_id`, `provider`, `timestamp + user_id`, `timestamp + provider`
- **Write Frequency:** HIGH (every LLM call: respond, summarize, analysis)
- **Lifecycle:** PERSISTENT (permanent audit trail for cost analysis and capacity planning)
- **Status:** ✅ ACTIVE (Phase 2)

---

### 13. `delivery_failures` (Phase 2)

- **Purpose:** Dead-letter queue for failed content delivery attempts with retry tracking
- **Owner:** [abby_core/services/delivery_retry_service.py](../abby_core/services/delivery_retry_service.py)
- **Fields:** `delivery_id`, `content_item_id`, `channel_id`, `error_code` (4xx | 5xx | timeout), `error_message`, `retry_count` (max 3), `next_retry_at` (ISO8601), `last_error_at`, `backoff_delay_ms`, `created_at`, `moved_to_dead_letter_at`
- **Indexes:** `content_item_id`, `retry_count`, `next_retry_at`, `created_at`
- **Write Frequency:** MEDIUM (proportional to delivery failures)
- **Lifecycle:** PERSISTENT (audit trail for failed deliveries; inspect for non-retryable errors)
- **Status:** ✅ ACTIVE (Phase 2)

---

## Deprecated Collections (Removed)

### 14. `system_events` (REMOVED)

- **Status:** ❌ REMOVED from MongoDB (2026-01-28)
- **Replaced by:** `content_delivery_items`
- **Migration:** Complete - all code routes through content_delivery service
- **Legacy API:** Maintained by [abby_core/services/events_lifecycle.py](../abby_core/services/events_lifecycle.py) for backward compatibility

### 15. `scheduled_announcements` (REMOVED)

- **Status:** ❌ REMOVED from MongoDB (2026-01-28)
- **Replaced by:** `content_delivery_items`
- **Migration:** Complete - all code routes through content_delivery service
- **Legacy API:** Maintained by [abby_core/services/events_lifecycle.py](../abby_core/services/events_lifecycle.py) for backward compatibility

---

## Secondary Collections (Active but Low Usage)

### 16. `discord_profiles`

- **Purpose:** Discord-specific user profiles (avatars, usernames, etc.)
- **Owner:** [abby_core/database/mongodb.py:get_profile](../abby_core/database/mongodb.py)
- **Fields:** `user_id`, `username`, `avatar_url`, `created_at`, `last_seen_at`
- **Indexes:** `user_id` (unique)
- **Write Frequency:** LOW (user joins, profile updates)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE (low priority)

---

### 17. `giveaways`

- **Purpose:** Giveaway lifecycle, participation, and winners
- **Owner:** [abby_core/database/collections/giveaways.py](../abby_core/database/collections/giveaways.py)
- **Fields:** `prize`, `description`, `channel_id`, `guild_id`, `host_id`, `start_time`, `end_time`, `duration_minutes`, `winner_count`, `participants[]`, `winners[]`, `active`, `message_id`
- **Indexes:** `guild_id + active + end_time`, `message_id` (sparse), `end_time`
- **Write Frequency:** LOW (manual giveaway creation)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 18. `game_stats`

- **Purpose:** Per-user, per-guild game performance stats
- **Owner:** [abby_core/database/collections/game_stats.py](../abby_core/database/collections/game_stats.py)
- **Fields:** `user_id`, `guild_id`, `game_type`, `games_played`, `games_won`, `games_lost`, `win_rate`, `created_at`, `updated_at`
- **Indexes:** `user_id + guild_id + game_type` (unique), `guild_id + game_type + games_won + win_rate`
- **Write Frequency:** MEDIUM (game results)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 19. `memes`

- **Purpose:** Meme assets and voting metadata
- **Owner:** [abby_core/database/collections/memes.py](../abby_core/database/collections/memes.py)
- **Fields:** `_id` (meme URL), `url`, `upvotes`, `downvotes`, `score`, `timestamp`
- **Indexes:** `score`, `timestamp`
- **Write Frequency:** LOW
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 20. `user_tasks`

- **Purpose:** User task/reminder management
- **Owner:** [abby_core/database/mongodb.py:add_task](../abby_core/database/mongodb.py)
- **Fields:** `user_id`, `taskDescription`, `taskTime`
- **Indexes:** `user_id`
- **Write Frequency:** RARE (manual user actions)
- **Lifecycle:** TRANSIENT (auto-expire after task time)
- **Status:** 🟡 LEGACY (low usage, consider deprecating)

---

### 21. `music_genres`

- **Purpose:** Music genre metadata (for label/promo features)
- **Owner:** [abby_core/database/mongodb.py:get_genres](../abby_core/database/mongodb.py)
- **Fields:** Genre definitions (structure unclear)
- **Indexes:** None
- **Write Frequency:** RARE (manual updates)
- **Lifecycle:** PERSISTENT
- **Status:** 🟡 LEGACY (domain-specific, consider moving to separate DB)

---

### 22. `music_promo_sessions`

- **Purpose:** Music promo session metadata
- **Owner:** [abby_core/database/mongodb.py:get_promo_session](../abby_core/database/mongodb.py)
- **Fields:** Session length definitions (1_week, etc.)
- **Indexes:** None
- **Write Frequency:** RARE (manual updates)
- **Lifecycle:** PERSISTENT
- **Status:** 🟡 LEGACY (domain-specific)

---

## Canon Collections (Append-Only)

### 23. `canon_staging`

- **Purpose:** Mutable staging artifacts pending review
- **Owner:** [abby_core/personality/canon_service.py](../abby_core/personality/canon_service.py)
- **Fields:** `artifact_id`, `canon_type`, `status`, `content`, `author_id`, `created_at`, `reviewed_at`, `reviewer_id`
- **Indexes:** `status`, `canon_type`
- **Write Frequency:** LOW (operator/creator submissions)
- **Lifecycle:** TRANSIENT (promoted to canon\_\* or rejected)
- **Status:** ✅ ACTIVE

---

### 24. `canon_commits`

- **Purpose:** Immutable audit log of canon writes
- **Owner:** [abby_core/personality/canon_service.py](../abby_core/personality/canon_service.py)
- **Fields:** `commit_id`, `canon_type`, `artifact_id`, `author_id`, `timestamp`, `action`
- **Indexes:** `commit_id` (unique), `canon_type`, `artifact_id`
- **Write Frequency:** LOW (matches canon writes)
- **Lifecycle:** PERSISTENT (audit trail)
- **Status:** ✅ ACTIVE

---

### 25-29. Canon Namespaces

- `lore_documents` - Canonical lore documents
- `persona_identity` - Canonical persona identity documents
- `book_frontmatter` - Canonical book/frontmatter documents
- `canon_appendix` - Canonical appendix documents

**Owner:** [abby_core/personality/canon_service.py](../abby_core/personality/canon_service.py)  
**Write Frequency:** RARE (operator-approved commits)  
**Lifecycle:** PERSISTENT (append-only)  
**Status:** ✅ ACTIVE

---

## System Configuration Collections

### 30. `system_config`

- **Purpose:** System-wide configuration (timezone, job schedules, etc.)
- **Owner:** [abby_core/database/system_configuration.py](../abby_core/database/system_configuration.py)
- **Fields:** `_id: "primary"`, `timezone`, `system_jobs` (nested), `updated_at`
- **Indexes:** None (single document)
- **Write Frequency:** RARE (operator changes)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

### 31. `bot_settings`

- **Purpose:** Bot-wide settings (active persona, personality)
- **Owner:** [abby_core/database/mongodb.py:get_personality](../abby_core/database/mongodb.py)
- **Fields:** `_id: "personality"`, `personality_number`, `_id: "active_persona"`, `persona`
- **Indexes:** None (single/few documents)
- **Write Frequency:** RARE (operator changes)
- **Lifecycle:** PERSISTENT
- **Status:** ✅ ACTIVE

---

## Summary Statistics

| Category         | Count  | Active | Deprecated | Legacy |
| ---------------- | ------ | ------ | ---------- | ------ |
| Core Collections | 13     | 13     | 0          | 0      |
| Deprecated       | 2      | 0      | 2          | 0      |
| Secondary        | 7      | 4      | 0          | 3      |
| Canon            | 6      | 6      | 0          | 0      |
| System Config    | 2      | 2      | 0          | 0      |
| **TOTAL**        | **30** | **25** | **2**      | **3**  |

---

## Recommendations

1. **Phase 2 Collections Added (2026-01-28):**
   - ✅ `generation_audit` collection for cost tracking (GenerationAuditService)
     - Logs all LLM calls (respond, summarize, analysis) with tokens, cost, latency
     - Enables 50-year cost projections and capacity planning
     - Indexes on timestamp, user_id, provider for operator queries
   - ✅ `delivery_failures` collection for dead-letter queue (DeliveryRetryService)
     - Tracks failed delivery attempts with retry history and backoff schedule
     - Supports operator inspection of non-retryable errors (403, 404, 400)
     - Max 3 retries per delivery with exponential backoff
   - ✅ Both collections documented with ownership, indexes, and persistence model

1. **Completed Migration (2026-01-28):**
   - ✅ Migration from `system_events` and `scheduled_announcements` to `content_delivery_items` complete
   - ✅ All code verified to route through unified model
   - ✅ Deprecated collections removed from MongoDB
   - ✅ No active code paths access deleted collections

1. **Review Legacy Collections (Phase 2):**
   - Audit usage of `user_tasks`, `music_genres`, `music_promo_sessions`
   - Consider deprecating low-usage collections or moving to separate domain DB
   - Document rationale for keeping or removing

1. **Add Collection Ownership Tests:**
   - Test that each collection has exactly one owner module
   - Test that all collections have documented indexes
   - Test that DEPRECATED collections receive no new writes

---

### END OF INVENTORY
