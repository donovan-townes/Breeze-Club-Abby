# Configuration State

Guild/user preferences and knobs; never override platform state. Examples: channels, toggles, summon/dismiss, memory settings, economy rates.

## Source of truth

- Mongo `guild_configuration`
- Mongo `memory_settings`
- Persona config files (`personality/config.py` JSONs)
- Environment variables (interest rates, scheduler verbosity)

## Ownership and mutation

- Operators/admins set guild configs via commands/UI.
- DevOps sets environment defaults (interest, scheduler flags).
- Persona configs deployed with code; operators can reload persona.

## Invariants

- Must not change platform state (seasons/events/modes).
- Scoped to guild/user; defaults should be sane and minimal.
- Changes should be auditable when possible.

## Key fields/examples

- Channels: announcement, random_messages, games, MOTD.
- Scheduling toggles and `last_executed_at` stamps per job.
- Summon/dismiss lists, response patterns (persona config).
- Memory settings: target channels, retention knobs.

## Key functions

- Guild config readers in scheduler/job handlers (`discord/cogs/system/job_handlers.py`).
- Persona config accessors in `abby_core/personality/config.py`.

## Observability

- Track config changes (operator id when possible).
- Validate channel permissions before use.

See also: [STATE_MAP.md](STATE_MAP.md) for catalog and owners.
