# Canonical State Map & Ownership Registry

**Last Updated:** 2026-02-02  
**Purpose:** Single reference for all persistent state in the system. Answers: Who owns this state? How does it change? What depends on it?

---

## State Registry (Authoritative)

### Platform State Tier (Global)

#### `system_state` Collection

```json
{
  "_id": ObjectId,
  "state_id": "winter-2026",           // Unique state identifier
  "state_type": "season",               // season | era | arc | event | mode
  "active": true,                       // Only one per type active at a time
  "start_at": "2026-01-01T00:00:00Z",
  "end_at": "2026-03-31T23:59:59Z",
  "canon_ref": "lore.season.winter.v1",
  "effects": {
    "persona_overlay": "cozy_ceremonial",
    "xp_multiplier": 1.5,
    "egg_hunt_enabled": true
  },
  "created_at": "2026-01-15T10:00:00Z",
  "created_by": "operator:alice",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

**Owner:** `StateActivationService`  
**Persistence:** MongoDB `system_state` collection  
**Cardinality:** One active per `state_type`; no duplicates (unique index enforced)  
**Atomicity:** Activation is transactional (deactivate old + activate new in same tx)  
**Consumers:** Economy service (XP resets), Persona manager (overlays), Scheduler (event jobs)  
**Who must NOT read:** Conversation service (state is independent of user sessions); adapters (must go through services)

---

### Announcement Tier (Guild-scoped)

#### `content_delivery_items` Collection

```json
{
  "_id": ObjectId,
  "guild_id": 547471286801268777,
  "content_type": "system",              // system | world | event | social
  "trigger_type": "scheduled",           // scheduled | event_start | manual | immediate
  "title": "Winter Festival Begins!",
  "description": "Season changed; XP multiplier active",
  "payload": { /* custom data */ },
  "context_refs": {
    "state_id": "winter-2026",
    "reason": "seasonal_transition"
  },
  "idempotency_key": "season_winter_2026",
  "scheduled_at": "2026-01-15T12:00:00Z",
  "priority": 10,
  "delivery_channel_id": 802512963519905852,
  "delivery_roles": [1131231727675768953],
  "lifecycle_state": "generated",        // draft | generated | queued | delivered | archived
  "generation_status": "ready",          // pending | ready | error
  "delivery_status": "pending",          // pending | partial | delivered | failed
  "generated_message": "🎄 Winter is here!...",
  "error_message": null,
  "created_at": "2026-01-15T10:00:00Z",
  "created_by": "operator:alice",
  "updated_at": "2026-01-15T12:30:00Z"
}
```

**Owner:** `AnnouncementDispatcher` (creation), Scheduler job (generation), Discord cog (delivery)  
**Persistence:** MongoDB `content_delivery_items` collection  
**Cardinality:** Many per guild  
**Atomicity:** State transitions validated; no orphaned items; failed items routed to DLQ  
**Consumers:** Scheduler, Discord cogs, MetricsService, DLQService  
**Who must NOT write:** Adapters (must go through dispatcher); conversations (independent)

---

### Session Tier (User-scoped)

#### `sessions` Collection

```json
{
  "_id": ObjectId,
  "user_id": "268871091550814209",
  "session_id": "sess_abc123def456",
  "guild_id": "547471286801268777",
  "channel_id": "1103490012500201632",
  "status": "active",                   // active | cooldown | closed | expired
  "state": "active",                    // OPEN | ACTIVE | COOLDOWN | CLOSED | EXPIRED
  "turn_count": 5,
  "max_turns": 10,
  "last_message_at": "2026-02-02T14:23:45Z",
  "cooldown_until": null,
  "interactions": [
    {
      "user_message": "...",
      "bot_response": "...",
      "intent": "chat",
      "timestamp": "2026-02-02T14:20:00Z"
    }
  ],
  "summary": "User discussed music production...",
  "created_at": "2026-02-02T14:00:00Z",
  "closed_at": null
}
```

**Owner:** `ConversationService`  
**Persistence:** MongoDB `sessions` collection  
**Cardinality:** One active per user per guild (can have multiple cooldown/closed)  
**Atomicity:** Turn increment uses atomic `findOneAndUpdate()` with conditional filter (turn_count < max_turns)  
**Consumers:** Chatbot cog (turn management), UsageGateService (limits), ConversationService (lifecycle)  
**Who must NOT write:** Scheduler, Economy service (read-only); other adapters

---

### Conversation Tier (Ephemeral, Per-Turn)

#### `ConversationTurn` Object (Memory)

```python
@dataclass
class ConversationTurn:
    turn_id: str = "turn_xyz123"
    user_id: str = "268871091550814209"
    guild_id: str = "547471286801268777"
    channel_id: str = "1103490012500201632"
    message: str = "What's new in music?"
    current_state: ConversationState = ConversationState.IDLE
    state_history: List[StateTransition] = [
        StateTransition(
            from_state=IDLE,
            to_state=INGRESS,
            timestamp=...,
            duration_ms=10.5
        ),
        # ... more transitions
    ]
    intent: str = "chat"
    intent_confidence: str = "high"
    used_rag: bool = False
    error_message: Optional[str] = None
    created_at: datetime = datetime.utcnow()
    completed_at: Optional[datetime] = None
```

**Owner:** Orchestrator (state machine logic), Cog (delivery)  
**Persistence:** Memory (ephemeral); optionally serialized to MongoDB `conversation_turns` (Phase 2)  
**Cardinality:** One per active user-message interaction  
**Atomicity:** Transitions validated; invalid transitions raise `StateTransitionError`  
**Consumers:** Cogs (delivery), Metrics (telemetry), Orchestrator (routing)  
**Who must NOT write:** Scheduler, other conversations (isolated per turn)

---

### Scheduler Tier (Job-scoped)

#### `scheduler_jobs` Collection

```json
{
  "_id": ObjectId,
  "job_id": "announcement_daily_motd",
  "job_type": "scheduled_announcement",  // announcement_generation | xp_reset | interest_cycle | etc
  "enabled": true,
  "schedule": {
    "type": "daily",                    // interval | daily | date_based
    "time": "09:00",                    // For daily: HH:MM in specified timezone
    "every_minutes": null,              // For interval: every N minutes
    "jitter_minutes": 5,                // Random offset to avoid thundering herd
    "timezone": "US/Pacific",
    "last_run_at": "2026-02-02T17:00:00Z"
  },
  "context": {
    "guild_id": 547471286801268777,
    "announcement_type": "motd"
  },
  "created_at": "2026-01-01T00:00:00Z",
  "created_by": "operator:system"
}
```

**Owner:** `SchedulerService`  
**Persistence:** MongoDB `scheduler_jobs` collection  
**Cardinality:** One per job type (globally registered at startup)  
**Atomicity:** Job claiming is atomic (only one instance executes per tick)  
**Consumers:** Scheduler tick loop (checks eligibility), job handlers (execution)  
**Who must NOT write:** Cogs (read-only); other services must register through SchedulerService

---

### Guild Configuration Tier

#### `guild_configuration` Collection

```json
{
  "_id": ObjectId,
  "guild_id": 547471286801268777,
  "channels": {
    "motd_channel": 802512963519905852,
    "xp_channel": 1103490012500201632,
    "nudge_channel": 802512963519905852
  },
  "roles": {
    "musician": 808129993460023366,
    "streamer": 1131231727675768953
  },
  "settings": {
    "xp_enabled": true,
    "economy_enabled": true,
    "personality_mode": "default"     // default | festive | ceremonial
  },
  "memory_settings": {
    "retention_days": 90,
    "context_window_messages": 20
  },
  "created_at": "2025-06-01T00:00:00Z",
  "updated_at": "2026-02-02T12:00:00Z"
}
```

**Owner:** `Guild admin` (via commands), `BotConfig` (defaults)  
**Persistence:** MongoDB `guild_configuration` collection  
**Cardinality:** One per guild  
**Atomicity:** Updates are single-document writes (atomic at document level)  
**Consumers:** All guild-scoped queries (cogs, services)  
**Who must NOT write:** Scheduler, Conversation service (read-only); only admin commands

---

### User Tier

#### `users` Collection

```json
{
  "_id": ObjectId,
  "user_id": "268871091550814209",
  "discord": {
    "discord_id": "268871091550814209",
    "username": "alice#1234",
    "avatar_url": "https://...",
    "joined_at": "2025-01-01T00:00:00Z",
    "last_seen": "2026-02-02T14:30:00Z"
  },
  "profile": {
    "xp": 1250,
    "level": 5,
    "coins": 500,
    "rank": "musician"
  },
  "creative_profile": {
    "domains": ["music", "production"],
    "memorable_facts": ["Uses Ableton Live", "Prefers lo-fi hip-hop"]
  },
  "cost_budgets": {
    "llm_tokens_monthly": 10000,        // per-user budget
    "llm_tokens_remaining": 8500,
    "rag_queries_monthly": 100,
    "rag_queries_remaining": 75,
    "budget_reset_at": "2026-03-01T00:00:00Z"
  },
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2026-02-02T14:30:00Z"
}
```

**Owner:** `UserService`, `EconomyService` (updates), `GenerationAuditService` (budgets)  
**Persistence:** MongoDB `users` collection  
**Cardinality:** One per user  
**Atomicity:** Field updates atomic; XP increments use atomic `findOneAndUpdate()`  
**Consumers:** Conversation service (context), Economy service (progression), Generation audit (cost gating)  
**Who must NOT write:** Scheduler (read-only); other adapters (via services)

---

### Audit Trail Tier

#### `system_operations` Collection (Immutable)

```json
{
  "_id": ObjectId,
  "operation_type": "activate_state",   // activate_state | create_announcement | etc
  "operator_id": "operator:alice",
  "reason": "Scheduled seasonal transition",
  "target": {
    "state_id": "winter-2026",
    "resource_id": "...",
    "old_value": null,
    "new_value": "active"
  },
  "result": "success",                  // success | failed | rejected
  "error_message": null,
  "timestamp": "2026-01-15T10:00:00Z",
  "ip_address": "192.168.1.1",
  "user_agent": "Abby/2.0.0"
}
```

**Owner:** All services (append-only)  
**Persistence:** MongoDB `system_operations` collection (immutable)  
**Cardinality:** One per state-changing operation  
**Atomicity:** Write-once; no updates  
**Consumers:** Compliance audits, debugging, operator history  
**Who must NOT write:** Only via `SystemOperations.record()` helper; never direct insert

---

#### `generation_audit` Collection (Immutable, Append-Only)

```json
{
  "_id": ObjectId,
  "generation_id": "gen_abc123",
  "user_id": "268871091550814209",
  "guild_id": 547471286801268777,
  "intent": "chat",
  "model": "gpt-3.5-turbo",
  "input_tokens": 450,
  "output_tokens": 150,
  "cost_usd": 0.0008,                  // cost_usd per call
  "used_rag": false,
  "rag_queries": 0,
  "rag_cost_usd": 0.0,
  "latency_ms": 1250,
  "status": "success",                 // success | timeout | error
  "error_message": null,
  "timestamp": "2026-02-02T14:20:00Z"
}
```

**Owner:** `GenerationAuditService`  
**Persistence:** MongoDB `generation_audit` collection (TTL: never expires for analysis)  
**Cardinality:** One per LLM call  
**Atomicity:** Write-once; no updates  
**Consumers:** Cost projections, capacity planning, compliance  
**Who must NOT write:** Only via `GenerationAuditService.record()` helper

---

#### `content_delivery_dlq` Collection

```json
{
  "_id": ObjectId,
  "announcement_id": ObjectId,
  "guild_id": 547471286801268777,
  "error_type": "delivery_failed",      // state_transition | validation | transient | unknown
  "error_message": "Permission denied: cannot send message to channel",
  "retry_count": 0,
  "max_retries": 3,
  "next_retry_at": "2026-02-02T15:00:00Z",
  "status": "pending",                  // pending | retrying | resolved | abandoned
  "created_at": "2026-02-02T14:30:00Z",
  "updated_at": "2026-02-02T14:30:00Z",
  "operator_id": null,                  // Operator who resolved
  "resolution_note": null
}
```

**Owner:** `DLQService`  
**Persistence:** MongoDB `content_delivery_dlq` collection  
**Cardinality:** One per failed announcement  
**Atomicity:** Updates atomic; retry loop externalized  
**Consumers:** Operator dashboards, manual retry, auto-retry loop  
**Who must NOT write:** Only via `DLQService` methods

---

## Ownership & Mutation Rules

### State Mutation Patterns

| **State**                              | **Who Can Mutate**                                                            | **How**                          | **Atomic Guarantee**                          |
| -------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------- | --------------------------------------------- |
| system_state.active                    | StateActivationService                                                        | activate_state() → MongoDB tx    | ✅ Yes (deactivate old + activate new atomic) |
| content_delivery_items.lifecycle_state | AnnouncementDispatcher (creation), Scheduler (generation), DLQService (retry) | State transition functions       | ✅ Yes (validated transitions)                |
| sessions.turn_count                    | UsageGateService                                                              | increment_and_check_turn_limit() | ✅ Yes (atomic findOneAndUpdate)              |
| ConversationTurn.current_state         | Orchestrator                                                                  | transition_to() method           | ✅ Yes (validation + logging)                 |
| scheduler_jobs.last_run_at             | SchedulerService                                                              | After job execution              | ✅ Yes (atomic document update)               |
| guild_configuration.\*                 | Admin commands                                                                | Via bot commands                 | ✅ Yes (single-doc write)                     |
| users.xp                               | EconomyService                                                                | add_xp() method                  | ✅ Yes (atomic increment)                     |
| users.cost_budgets                     | GenerationAuditService                                                        | decrement_budget()               | ✅ Yes (atomic document update)               |
| system_operations.\*                   | All services                                                                  | via SystemOperations.record()    | ✅ Yes (insert-only, no updates)              |
| generation_audit.\*                    | GenerationAuditService                                                        | via record_generation()          | ✅ Yes (insert-only, no updates)              |

---

## Dependency Graph

```
Platform State (system_state)
  ├── drives Economy Service (XP resets, multipliers)
  ├── drives Persona Manager (overlays)
  ├── drives Scheduler (event jobs)
  └── read by Conversation Service (context snapshot)

Announcement Lifecycle (content_delivery_items)
  ├── created by AnnouncementDispatcher
  ├── generated by Scheduler job
  ├── delivered by Discord cog
  ├── monitored by MetricsService
  └── on error → DLQService

Session Management (sessions)
  ├── created by ConversationService
  ├── turn counts incremented by UsageGateService
  ├── read by Chatbot cog
  └── read by Conversation analytics

Conversation FSM (ConversationTurn)
  ├── created by Orchestrator
  ├── state transitions via Orchestrator + Cog
  ├── persisted to DB by ConversationService (Phase 2)
  ├── metrics via ConversationAnalyticsService
  └── read by Cog (delivery)

Scheduler (scheduler_jobs)
  ├── configured at startup
  ├── ticked by SchedulerService
  ├── executed via registered handlers
  └── outcomes logged to scheduler_outcomes

Guild Config (guild_configuration)
  ├── set by Admin commands
  ├── read by all guild-scoped queries
  └── validated by guild_config_validator (Phase 1)

User Profile (users)
  ├── created by UserService
  ├── xp incremented by EconomyService
  ├── budgets managed by GenerationAuditService
  └── read by Conversation context assembly

Audit Trail (system_operations, generation_audit, content_delivery_dlq)
  ├── append-only
  ├── immutable
  └── consumed by compliance + debugging
```

---

## Validation Rules

### Invariants (Must Always Be True)

1. **One active state per type:** Only one document in `system_state` with `state_type=X` and `active=true`
2. **Session state consistency:** If session status=active, cooldown_until must be null
3. **Turn count bounds:** 0 <= turn_count <= max_turns
4. **Announcement state ordering:** draft → generated → queued → delivered (no skipping backwards)
5. **Cost budgets non-negative:** cost_budget_remaining >= 0 at all times
6. **User XP non-negative:** user.xp >= 0 at all times
7. **Audit trail immutable:** No updates to system_operations or generation_audit; insert-only

### Validation Points (Where to Enforce)

| **State**                   | **Validation**                                | **Enforced By**                          |
| --------------------------- | --------------------------------------------- | ---------------------------------------- |
| system_state activation     | State exists, effects valid, no self-conflict | StateValidationService                   |
| content_delivery transition | Valid state transition                        | AnnouncementDispatcher                   |
| turn increment              | session exists, turn_count < max_turns        | UsageGateService                         |
| ConversationTurn transition | Valid FSM transition                          | ConversationTurn.\_is_valid_transition() |
| guild_configuration update  | Schema valid                                  | guild_config_validator (Phase 1)         |
| cost deduction              | remaining_budget >= cost                      | GenerationAuditService (Phase 2)         |
| xp increment                | xp >= 0, no negative increments               | EconomyService                           |

---

## Future Consolidations (Phase 2+)

- Persist `ConversationTurn` to `conversation_turns` collection (crash recovery)
- Add `cost_budgets` to `users` collection (per-user cost gating)
- Migrate env-var config to `guild_configuration` (single source of truth)
- Add `scheduled_expiration` field to `system_state` (auto-expire old states)
- Deduplicate announcement delivery via `idempotency_key` cache

---

**Last Review:** 2026-02-02  
**Next Review:** After Phase 1 (mid-February 2026)
