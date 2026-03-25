# Operator Guide (Power + Safety)

Practical checklist for admins/operators. Keep concise; update alongside STATE_MAP.

## Principles

- Canonical changes go through platform state (activate season/event/mode); avoid ad-hoc flags.
- Lifecycle items move through pending → ready → delivered → archived; do not short-circuit except for emergencies.
- Generation state stays ephemeral; never store prompts/outputs unless part of a lifecycle (e.g., announcements).

## Startup operations (summary)

Use the detailed runbook for full startup sequencing and troubleshooting:

- [STARTUP_OPERATIONS_GUIDE.md](STARTUP_OPERATIONS_GUIDE.md)

Quick checks:

- Confirm MongoDB connectivity before launching.
- Validate Discord token and required API keys.
- On startup, verify health line shows all OK or expected degraded components.

## What operators can do

- Activate/deactivate seasons/events/modes via state registry or commands.
- Queue announcements (system events, scheduled guild announcements).
- Configure guild channels and feature toggles (random messages, nudges, games, MOTD).
- Run maintenance jobs (memory decay) via scheduler-adjacent commands.
- Adjust economy rates via environment/config (interest, XP curve) with deployment change control.

## What operators cannot do

- Override platform state with guild config (no local season overrides).
- Persist generation prompts/content outside approved lifecycles.
- Enable gameplay features without corresponding platform state effects.
- Disable safety rails in persona or context assembly.

## Checklists

### Before activating a season/event

- [ ] Confirm state definition exists in `system_state` and instance in `system_state_instances`.
- [ ] Review `effects` (xp_reset, persona_overlay, gameplay toggles) for correctness.
- [ ] Ensure announcement templates are ready if public messaging is required.
- [ ] Verify scheduler jobs that depend on state (rollover, announcements) are enabled.

### Announcements lifecycle

- [ ] Record event via operator command or API (state change, world announcement, scheduled guild announcement).
- [ ] Ensure generation job is running (scheduler handler registered).
- [ ] Check `generation_status` transitions to `ready`; investigate failures.
- [ ] Delivery job sends to configured channels; confirm `deliveries[]` entries exist.
- [ ] **Scheduled delivery timing:** Announcements scheduled for specific times respect timezone conversions (user input converted to UTC for storage, prevents premature delivery).
- [ ] **DLQ inspection:** If delivery or generation fails, item appears in DLQ Inspector (System tab).
  - View DLQ items with error category and retry count.
  - **Diagnostics:** Call `DLQService.get_failure_diagnostics(dlq_item_id)` for root cause analysis and remediation suggestions
  - Manually retry individual items or let automatic scheduler handle (runs every 5 minutes).
  - Discard items permanently if announcement was deleted or is no longer valid.
- [ ] **Graceful handling:** Non-retryable errors (announcement not found, validation errors) are marked abandoned immediately without retry spam.

### Guild configuration

- [ ] Set announcement, random message, game, and MOTD channels in `guild_configuration`.
- [ ] Toggle community jobs (random_messages, nudge) appropriately for the guild.
- [ ] Validate permissions for target channels (send_messages allowed).

### Safety and overrides

- [ ] **Memory injection gating:** Guild custom_memory is only injected during knowledge-seeking queries (contains "?" or knowledge keywords). Casual conversation does not leak guild context.
- [ ] **Memory sanitization:** All custom_memory fields are automatically sanitized against prompt injection attacks before LLM injection. Admin-set memory cannot be used to jailbreak Abby.
- [ ] For emergency shutdown of a feature, disable the relevant scheduler job or platform state effect, not the persona.
- [ ] For persona tone shifts, use platform state overlays (season/event) rather than editing base persona.
- [ ] Audit logs/telemetry after significant overrides.

## Auditable surfaces

- Mongo collections: `system_state`, `system_state_instances`, `content_delivery_items` (unified announcements/events), `guild_configuration`, `user_xp`, `user_levels`, `game_stats`, `dlq_items` (failed messages with retry tracking), `metrics` (performance statistics).
- **DLQ Inspector (System tab → DLQ subtab):**
  - **List DLQ:** Shows 10 most recent items with status (pending/retrying/resolved/abandoned) and retry count.
  - **DLQ Stats:** Aggregates by status and error category (state_transition, validation, transient, unknown).
  - **Retry Item:** Manually retry a specific DLQ item by ID (operator-initiated retry outside scheduler).
  - **Discard Item:** Mark item abandoned with audit trail (records operator_id and timestamp).
- **Metrics Dashboard (System tab → Metrics subtab):**
  - **Dashboard:** 24-hour performance overview (average timing: generation, queue wait, delivery, total cycle; error counts by category).
  - **7-Day Trend:** Daily error volume over past week for trend analysis.
  - **By Guild:** Top 5 guilds by activity (announcement count) in last 7 days.
  - **Cost Analysis:** 30-day actual cost + 50-year projection based on metadata.
- **Cost tracking (Phase 2):** `generation_audit` collection records all LLM calls (chat, summary, analysis) with tokens, costs, latency, provider, model, session context. Query for cost reports:
  ```js
  db.generation_audit.aggregate([
    { $match: { timestamp: { $gte: ISODate("2026-01-01") } } },
    {
      $group: {
        _id: "$provider",
        total_cost: { $sum: "$total_cost_usd" },
        total_tokens: { $sum: "$total_tokens" },
      },
    },
  ]);
  ```

- Scheduler job run stamps (`last_run_at` fields in guild config and scheduler_jobs collection).
- Operator commands and state activation events (store operator id where possible).
- **Validation audit:** State activation logs record validation results and any rejected definitions.

## Runbook stubs to add next

- Command list and scopes for operator actions.
- How to rotate environment-driven config safely.
- How to backfill or repair state after outages.

Keep this guide lean; link deeper technical details from STATE_MAP and SYSTEM_ARCHITECTURE when necessary.
