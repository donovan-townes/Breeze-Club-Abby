# Gameplay State

Event-bound, temporary features (crush system, egg hunts, daily drops, streaks, games). Should never bleed into persona or platform tone except via platform effects.

## Source of truth

- Event effects on platform state (`system_state` / `system_state_instances`)
- Gameplay data: Mongo `game_stats`; scheduler cursors in `guild_configuration`

## Controls

- Effects toggles (e.g., `crush_system_enabled`, `egg_hunt_enabled`, `daily_drops_enabled`, `festive_theme`) defined in event templates.
- Scheduler job cursors (e.g., `scheduling.jobs.games.emoji.last_executed_at`).

## Turn Management (Phase 2: Fairness & Rate Limiting)

### User conversation turn limits enforce fairness under concurrent load:

- **Storage:** MongoDB atomic counters (user_id, guild_id scoped)
- **Enforcement:** TurnManager via `increment_and_check_turn()` using `find_one_and_update()` with conditional filter
- **Atomicity:** Increment happens before LLM invocation; parallel requests cannot bypass limits
- **Persistence:** Turn counts stored in MongoDB with session context for audit trails
- **Session Scope:** Turn count resets per conversation session; tracked in `chat_sessions` collection

**Owner:** [abby_core/discord/adapters/turn_manager.py](../../abby_core/discord/adapters/turn_manager.py)  
**Key Function:** `increment_and_check_turn()` (delegates to [usage_gate_service.py](../../abby_core/services/usage_gate_service.py) `increment_and_check_turn_limit()`)  
**Invoked From:** LLM pipeline (conversation.py, respond() function)  
**Impact:** Prevents turn limit bypass under high contention; ensures fair usage across users

## Ownership and mutation

- Operators enable via platform events; gameplay code consumes the flags.
- Scheduler updates per-job cursors; gameplay flows update stats.

## Invariants

- Features active only when event effects enable them.
- Gameplay data is guild/user scoped; do not leak into persona overlays.
- Resets follow platform season/event boundaries when specified.

## Key functions

- Event templates and creation: `abby_core/system/state_registry.py`
- Game stats: `record_game_result` in `abby_core/economy/leveling.py`
- Scheduled games: handlers in `abby_core/discord/cogs/system/job_handlers.py`

## Observability

- Track feature flags per active event.
- Monitor `game_stats` growth and job run timestamps.

See also: [STATE_MAP.md](STATE_MAP.md) for catalog and owners.
