# Abby Modernization & Migration Plan (PLAN_ABBY.md)

Last updated: 2025-12-29
Owner: Donovan Townes
Scope: Comprehensive re-architecture and migration of Abby to TServer + TDOS, with Ollama-first LLM, RAG foundation, slash commands, unified data model, and governance signals aligned to TDOS v1.5 kernel.

---

## 1) Objectives

- Transform Abby into a creative assistant for the Breeze Club, with elevated owner capabilities integrated with TDOS.
- Migrate runtime from Linode to self-hosted TServer (Windows-first; Linux-capable).
- Convert most prefix commands to slash commands; retain minimal admin prefix if needed.
- Introduce an LLM abstraction: Ollama primary (local), OpenAI fallback; align with TDOS Intelligence Interface Layer (IIL) principles.
- Establish an initial, Windows-friendly RAG stack (Chroma), with a migration path to Qdrant.
- Unify and modernize MongoDB schema; plan online→local migration; tenant-scope all data for TDOS compliance.
- Add TDOS-compliant heartbeat + error logging (append-only JSONL) with full v1.5 event envelope.
- Improve moderation/engagement to keep community active without spam.

---

## 2) Target Architecture (High Level)

- Discord runtime: Abby bot (Python) on TServer (Win11); Linux optional.
- LLM: Ollama service on mini PC or TServer (`OLLAMA_HOST`), text generation only. OpenAI as fallback.
- RAG: Chroma for local vector store; metadata in MongoDB; later Qdrant via Docker for scale/performance.
- Data: Unified MongoDB (single DB) hosting users, sessions, xp, economy, submissions, rag_documents; all tenant-scoped.
- TDOS: Governance signals (heartbeat + error) appended to `shared/logs/events.jsonl` with full v1.5 provenance. Abby never mutates TDOS kernel state; conforms to IIL.
- **Code layout**: `abby-core/` (domain logic: LLM, RAG, economy, moderation) + `abby-adapters/discord/` (Discord I/O). Future: web, TDOS CLI adapters.

---

## 2.5) TDOS v1.5 Identity & Tenancy

**Abby as a TDOS Agent + Subject Identity:**

- **Tenant ID**: `TENANT:BREEZE_CLUB` (env: `TDOS_TENANT_ID`; can be overridden for multi-server deployments).
- **Agent Subject ID**: `AGENT:ABBY-DISCORD` (fixed; registered with kernel on startup).
- **Owner Subject ID**: `SUBJECT:DONOVAN` (elevated role for TDOS syscalls, job queries, pipeline triggers).
- **Machine Subject ID**: `MACHINE:TSERVER` (loaded from TDOS registry on startup; identifies hardware).

**Consequence**: Every event, every MongoDB write, every TDOS syscall includes `tenant_id` and `subject_id` fields (enforced at emission layer).

---

## 2.6) TDOS Command & Event Envelopes (v1.5)

### Event Envelope (Append-Only JSONL Signals)

All events written to `TDOS_EVENTS_PATH` must conform to this structure (v1.5 invariant):

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-ABC123",
  "event_type": "HEARTBEAT|JOB.STARTED|JOB.COMPLETED|JOB.FAILED|ERROR|LLM.INFERENCE|RAG.QUERY|DISCORD.COMMAND",
  "timestamp": "2025-12-29T14:30:00.123Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:DISCORD-SLASH-IMAGINE-12345 | JOB:NONE",
  "invoker_subject_id": "SUBJECT:DISCORD-USER-98765 | AGENT:ABBY-DISCORD",
  "payload": {
    /* event_type-specific fields */
  }
}
```

Notes:

- `event_type` replaces `type` to avoid collisions with TDOS kernel reserved fields.
- `schema_version` is mandatory for forward/ backward compatibility; default `tdos.event.v1` injected by helper.
- All emissions must go through the `emit_event()` helper to enforce schema and append-only writes.

**Example: HEARTBEAT**

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-001",
  "event_type": "HEARTBEAT",
  "timestamp": "2025-12-29T14:30:00Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:NONE",
  "invoker_subject_id": "AGENT:ABBY-DISCORD",
  "payload": {
    "uptime_seconds": 3600,
    "active_sessions": 3,
    "pending_submissions": 2,
    "ollama_latency_ms": 450
  }
}
```

**Example: ERROR**

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-002",
  "event_type": "ERROR",
  "timestamp": "2025-12-29T14:35:15Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:NONE",
  "invoker_subject_id": "AGENT:ABBY-DISCORD",
  "payload": {
    "error_type": "OllamaConnectionError",
    "message": "Failed to connect to Ollama at http://localhost:11434",
    "stack_trace": "ConnectionError: ...",
    "recovery_action": "Fallback to OpenAI enabled"
  }
}
```

**Example: LLM.INFERENCE**

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-003",
  "event_type": "LLM.INFERENCE",
  "timestamp": "2025-12-29T14:40:00Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:DISCORD-SLASH-IMAGINE-12345",
  "invoker_subject_id": "SUBJECT:DISCORD-USER-98765",
  "payload": {
    "provider": "ollama",
    "model": "llama3",
    "request_type": "generate",
    "prompt_length": 250,
    "latency_ms": 1200,
    "token_count": 156,
    "success": true
  }
}
```

### TDOS Command Envelope (Owner-Only Syscalls)

When Abby needs to invoke TDOS syscalls (e.g., owner querying job status, listing pipelines), use v1.5 command envelope:

```json
{
  "command_type": "JOB.LIST|PIPELINE.REGISTER|UNIT.CREATE",
  "invoker_subject_id": "SUBJECT:DONOVAN",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "payload": {
    /* syscall-specific params */
  },
  "metadata": {
    "origin": "discord_slash_/tdos-jobs",
    "timestamp": "2025-12-29T14:45:00Z"
  }
}
```

Abby will expose owner-only slash commands like `/tdos jobs`, `/tdos pipelines`, `/tdos trigger` that construct and send these envelopes to the kernel runtime.

---

## 3) Repository Split & Organization

### Folder Structure (Core + Adapters Model)

Restructure Abby around TDOS compatibility and multi-interface design:

```
abby/
├── abby-core/              (domain logic; zero Discord/UI dependencies)
│   ├── llm/                (LLM abstraction: llm_client.py, providers)
│   ├── rag/                (RAG handler, embeddings, Chroma/Qdrant client)
│   ├── economy/            (XP/economy logic)
│   ├── moderation/         (content decision logic)
│   └── utils/              (tdos_events, bdcrypt, mongo_db, logging)
├── abby-adapters/
│   ├── discord/            (Discord I/O: slash commands, cogs, listeners)
│   └── README              (explains adapter pattern; future adapters here)
├── legacy-outdated/        (archived prefix commands, deprecated integrations)
└── docs/                   (PLAN_ABBY.md, migration scripts, schemas)
```

**Dependency Rule**: adapters depend on core; core has no Discord/adapter dependencies. This allows future adapters (web, TDOS CLI, etc.) to reuse core logic.

### Branch / Deploy Strategy

- **Working branch**: stable codebase before refactor (keep for rollback).
- **Development branch**: in-progress slash conversions, core/adapters split, migration scripts.
- **Merge to Working** only after full testing of new schema + TDOS logging.

---

## 4) Per-Command Migration Map (Keep → Convert → Archive)

Note: Slash commands will live in cogs or in `abby-adapters/discord/handlers/slash_commands.py`. Prefix commands retained only for owner/admin operations where needed.

### Admin

- Keep → Convert to slash (with role checks):
  - clear_conv → `/admin clear-conv`
  - persona → `/admin persona set` (subcommands for personas)
  - personality → `/admin personality set` (float 0–1)
  - update_log → `/admin logs reload`
  - profile (server/user tooling) → `/admin profile` (view/update limited fields)
- Maybe keep as prefix: `record` (if needed during transition). Prefer slash `/admin record` if implemented.
- Archive: any ad-hoc administrative helpers not aligned to creative assistant role.

### Creative Assistance (General)

- Keep → Convert:
  - help → `/help` (ephemeral responses; category-aware)
  - suggest → `/suggest` (routes to submissions or feedback; persists)
  - poll → `/poll` (creation + voting)
  - remindme → `/remindme` (slash already supported; consolidate)
  - image_generate/imagine → `/imagine` (style, prompt, cooldowns; 3rd-party image API)
  - generate_script → `/creative generate-text` (routes to LLM abstraction; options for artist promo, captions, blurbs)
- Archive:
  - duplicate or niche image generators if superseded by `/imagine`.

### Engagement / XP

- Keep → Convert:
  - exp check → `/xp status`
  - leaderboard → `/xp leaderboard`
  - admin adjustments → `/xp admin set|add|reset` (owner-only)
- Retain passive XP gain via listeners, with better rate limits.

### Economy

- Keep → Convert:
  - balance → `/eco balance`
  - deposit/withdraw → `/eco move` (subcommands)
  - marketplace listing → `/eco services` (creative services catalog; later tie to redemption)
- Archive: noisy auto-award tasks; replace with rules aligned to engagement.

### Greetings / Announcements

- Keep → Convert:
  - announce → `/announce`
  - motd → `/motd set|send`
  - morning_announcements → owner-only schedule trigger `/announce morning`
- Archive: random_messages if not valuable; otherwise consolidate to `/announce random`.

### Social / Twitch / URL Handler

- Keep:
  - Twitch notifications: `/twitch link`, `/twitch notify enable|disable`
  - URL auto-embeds via existing `abby-adapters/discord/handlers/url_handler.py`
- Archive:
  - Twitter/X commands (keep passive link parsing only)

### Utilities

- Keep → Convert:
  - ping/pong → `/ping`
  - help → `/help` (as above)
- Archive: duplicate prefix `pong` & legacy `help.py` implementations.

Open items:

- Radio/virtual DJ: remove exclamation versions; future slash `/radio` optional or extract to a separate bot.

---

## 5) Unified MongoDB Schema (Single DB)

Target DB name: `Abby` (local and online variants).

### Collection: `users`

- `_id` (string): Discord user ID
- `tenant_id` (string): tenant scope (e.g., `TENANT:BREEZE_CLUB`)
- `username` (string)
- `roles` (array[string]): user roles within tenant
- `created_at` (datetime)
- `last_active_at` (datetime)
- `llm_prefs` (object): `{ persona: string, personality: float }`
- Indexes: `_id` (PK), `tenant_id`, `last_active_at` (TTL optional for activity views)

### Collection: `sessions`

- `_id` (string): session UUID
- `tenant_id` (string): tenant scope
- `user_id` (string): Discord user ID
- `messages` (array[object]): `{ role: 'user'|'assistant'|'system', content: string, ts: datetime }`
- `summary` (string, optional)
- `status` (string): `active|closed`
- `tags` (array[string])
- Encryption: encrypt message bodies with existing `abby-core/utils/bdcrypt.py` keyed to `user_id`.
- Indexes: `tenant_id`, `user_id`, `status`, `tags`

### Collection: `xp`

- `_id` (string): user_id
- `tenant_id` (string): tenant scope
- `points` (int)
- `level` (int)
- `last_award_at` (datetime)
- `sources` (array[object]): `{type: string, delta: int, ts: datetime}`
- Indexes: `tenant_id`, `_id`, `points`, `level`

### Collection: `economy`

- `_id` (string): user_id
- `tenant_id` (string): tenant scope
- `wallet_balance` (int)
- `bank_balance` (int)
- `last_daily` (datetime)
- `transactions` (array[object]): `{amount: int, type: 'deposit'|'withdraw'|'reward'|'purchase', ts: datetime, note?: string}`
- Indexes: `tenant_id`, `_id`, `wallet_balance`, `bank_balance`

### Collection: `submissions`

- `_id` (string): submission UUID
- `tenant_id` (string): tenant scope
- `user_id` (string): Discord user ID
- `type` (string): `demo|image|text|other`
- `title` (string)
- `metadata` (object): `{genre?: string, link?: string, file_ref?: string, ...}`
- `status` (string): `draft|submitted|approved|rejected`
- `score` (int)
- `votes` (array[object]): `{user_id: string, vote: int, ts: datetime}`
- `created_at` (datetime)
- Indexes: `tenant_id`, `user_id`, `type`, `status`, `created_at`, `score`

### Collection: `rag_documents`

- `_id` (string): doc UUID
- `tenant_id` (string): tenant scope
- `source` (string): `label_docs|guidelines|artist_profiles|discord_threads|other`
- `title` (string)
- `text` (string)
- `metadata` (object): `{submission_id?: string, tags?: array[string], ts_ingested: datetime}`
- `embedding_key` (string): external key in Chroma/Qdrant to embedding vectors
- Indexes: `tenant_id`, `source`, `metadata.tags`, `embedding_key`

Migration notes:

- Collapse per-user databases into single collections keyed by `user_id`.
- Write migration scripts to iterate existing DBs, decrypt session content, and re-insert into unified collections.
- Maintain encryption for `sessions.messages.content` via `abby-core/utils/bdcrypt.py`.
- All collections must include `tenant_id` to support multi-server deployments and TDOS isolation invariants.

---

## 6) Data Migration (Online → Local MongoDB)

- Step 1: Snapshot online DBs.
- Step 2: Build migration tool (read online, write unified local):
  - Users → `users` (add `tenant_id`)
  - Experience → `xp` (add `tenant_id`)
  - Economy → `economy` (add `tenant_id`)
  - Chat logs → `sessions` (apply encryption where applicable; add `tenant_id`)
  - Any memes/submissions → `submissions` (add `tenant_id`)
- Step 3: Verify counts, indexes, and sample data integrity.
- Step 4: Switch app connection via `MONGODB_URI` env; keep rollback option.
- Step 5: Monitor performance and adjust indexes.

---

## 7) LLM Abstraction (Ollama Primary, OpenAI Fallback)

- New module: `abby-core/llm/llm_client.py`
  - Interface: `generate(prompt, options)`, `summarize(messages, options)`, `analyze(content, options)`
  - Provider selection: env `LLM_PROVIDER=ollama|openai` or auto based on health check.
  - Ollama config: `OLLAMA_HOST`, `OLLAMA_MODEL` (e.g., `llama3`), timeout settings.
  - OpenAI fallback: `OPENAI_API_KEY`, `OPENAI_MODEL`.
- Integration points:
  - `abby-adapters/discord/cogs/chatbot.py`: replace direct OpenAI calls with `llm_client`.
  - `abby-core/generate_script.py`: route through `llm_client`.
  - Greetings and announcement generators: consolidate any scattered LLM calls here.
- TDOS Intelligence Layer alignment (see TDOS kernel intelligence-layer.md):
  - Abby uses providers via IIL principles: model-agnostic, validated inputs, audit-only outputs.
  - No kernel mutations; any intelligence artifacts stored in shared notes/logs.

### IIL Input Schemas (Minimal Validation)

Three core LLM request types for Abby:

**1) LLM.GENERATE**

```json
{
  "request_type": "generate",
  "prompt": "string",
  "persona_id": "string (e.g., bunny, kitten)",
  "max_tokens": 500,
  "user_id": "string (Discord user ID)",
  "channel_id": "string (Discord channel ID)",
  "safety_flags": ["explicit_content", "off_topic"]
}
```

**2) RAG.QUERY**

```json
{
  "request_type": "rag_query",
  "query": "string",
  "scope": "label_docs|guidelines|artist_profiles|all",
  "top_k": 3,
  "filters": { "tags": ["submission", "demo"], "source": "guidelines" }
}
```

**3) RAG.INGEST**

```json
{
  "request_type": "rag_ingest",
  "source": "label_docs|guidelines|artist_profiles|discord_threads|other",
  "title": "string",
  "text": "string",
  "tags": ["array", "of", "tags"],
  "author": "string (optional)",
  "permissions": { "read": "all", "write": "owner" }
}
```

Open item:

- Fine-tune schemas based on initial Ollama experiments; align with TDOS INTEL contract definitions.

---

## 8) RAG Design (Windows-first, Migratable)

- Phase 1 (Chroma): -- Reference RAG only
  - Embeddings: `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) for Windows simplicity.
  - Store chunks + metadata in Chroma; keep document metadata in MongoDB `rag_documents`.
  - Query flow: user prompt → retriever (Chroma) → context injection → `llm_client.generate()`.
  - Ingestion: CLI or admin slash `/rag ingest` to add docs (label guidelines, artist profiles, curated threads).
- Phase 2 (Qdrant via Docker):
  - Migrate embeddings from Chroma to Qdrant; preserve keys to `submissions`/`rag_documents`.
  - Use payload filters for source/tag scoping; improve scalability and performance.

Open items:

- Corpus scope: which sources to ingest first (label docs, submission guidelines, Discord threads)?
- Embedding model choice for domain specificity; evaluate local vs API embeddings.

Out of Scope for RAG:

- Live conversations
- Raw discord chat logs
- Inferred user traits
- XP/economy history

> Note: RAG is used only for curated, reference-grade knowledge. Conversational memory and user profiling are handled separately.
---

## 9) TDOS Compliance (Heartbeat + Error + Event Envelope)

**New module:** `abby-core/utils/tdos_events.py`

- `emit_event(event_type, payload={})` is the **only** emitter; it enforces the v1.5 envelope (section 2.6), injects `schema_version=tdos.event.v1`, timestamps, IDs, and appends to `TDOS_EVENTS_PATH` (default `shared/logs/events.jsonl`).
- Validates required fields before write: `schema_version`, `agent_subject_id`, `machine_subject_id`, `tenant_id`, `event_id`, `event_type`, `timestamp`, `job_id`, `invoker_subject_id`.
- **Startup**: in `abby-adapters/discord/main.py` post-login, load `TDOS_TENANT_ID` and `TDOS_MACHINE_SUBJECT_ID` from environment; emit `HEARTBEAT`.
- **Periodic heartbeat**: every 30–60s via background task; include active session count, pending submissions, LLM provider health.
- **Error logging**: wrap command errors, LLM failures, MongoDB exceptions; emit `ERROR` with recovery action.
- **Event types**: `HEARTBEAT`, `JOB.STARTED`, `JOB.COMPLETED`, `JOB.FAILED`, `ERROR`, `LLM.INFERENCE`, `RAG.QUERY`, `DISCORD.COMMAND`.
- **Observability goal**: TDOS CLERK:ACTIVITY consumes these signals for behavioral analysis (no kernel mutations by Abby).

**Environment variables** for TDOS integration:

- `TDOS_TENANT_ID` (default: `TENANT:BREEZE_CLUB`)
- `TDOS_AGENT_SUBJECT_ID` (default: `AGENT:ABBY-DISCORD`)
- `TDOS_MACHINE_SUBJECT_ID` (loaded from TDOS registry; e.g., `MACHINE:TSERVER`)
- `TDOS_EVENTS_PATH` (default: `shared/logs/events.jsonl`)
- `TDOS_EVENT_ID_PREFIX` (default: `EVT-ABBY`; used to generate deterministic event IDs)

---

## 10) Moderation & Engagement

- Moderation Cog:
  - Auto-move images/snapshots posted in general to memes channel; reply with friendly note.
  - Use existing `abby-adapters/discord/handlers/url_handler.py` for embeds; extend with gentle nudges.
  - Scheduled nudges (extend `nudge_handler`) for low-activity windows.
- Engagement Logic:
  - XP rewards tuned for quality participation; link economy redemptions to creative services.
  - Owner tools to trigger events or themed discussions.

Open items:

- Define channel IDs and rules (which channels auto-move, thresholds, allowed content types).

---

## 11) Path & Environment Remediation

- Replace hardcoded Linux paths with `pathlib.Path` + env:
  - Working directory, logs, images, audio, songs, avatars.
- Standard env vars (complete list):
  - **Discord**: `ABBY_TOKEN`, `DISCORD_GUILD_ID` (optional for testing)
  - **Database**: `MONGODB_URI`, `MONGODB_DB` (default: `Abby`)
  - **Paths**: `WORKING_DIRECTORY`, `LOG_FILE_PATH`, `IMAGES_DIR`, `AUDIO_ROOT`, `SONGS_DIR`, `AVATAR_DIR`
  - **LLM**: `LLM_PROVIDER` (ollama|openai), `OLLAMA_HOST`, `OLLAMA_MODEL`, `OPENAI_API_KEY`, `OPENAI_MODEL`
  - **RAG**: `CHROMA_PERSIST_DIR`, `CHROMA_HOST` (optional for remote)
  - **TDOS**: `TDOS_TENANT_ID`, `TDOS_AGENT_SUBJECT_ID`, `TDOS_MACHINE_SUBJECT_ID`, `TDOS_EVENTS_PATH`, `TDOS_EVENT_ID_PREFIX`

---

## 12) Deployment Checklist

### Windows-first

- Python 3.11+, Git, FFmpeg (optional), Ollama installed and reachable.
- Create `shared/logs/` and set write permissions.
- Configure `.env` with required vars (above).
- Install deps and run:
  - Create venv, install requirements, start Abby.
- Optional: Register as Windows Service (NSSM) or Task Scheduler.

### Linux (optional)

- systemd service unit; Docker for Qdrant; same envs; ensure file paths are Linux-friendly.

---

## 13) Risks & Sequencing

- Phase 1: Paths + TDOS logging + basic slash commands.
- Phase 2: Unified data model + migration (online → local).
- Phase 3: LLM abstraction + chatbot integration.
- Phase 4: RAG POC (Chroma) + ingestion commands.
- Phase 5: Moderation/engagement tuning.
- Phase 6: Optional Twitch/social refinements and Qdrant migration.

Key risks:

- Data migration complexity; ensure snapshots/backups.
- Slash permission mapping; test owner/admin roles.
- Ollama latency; consider prompt caching.
- RAG corpus quality; define ingestion standards.

---

## 14) Open Questions & Uncertainties

**Breeze Club / Discord specifics:**

- Channel governance: exact channel IDs and auto-move rules (general → memes, etc.).
- Economy catalog: which creative services are redeemable and at what costs (extra image generations, song mastering, cover art)?
- Moderation thresholds: spam detection, mute/kick rules, engagement nudge frequency.

**RAG & Corpus:**

- RAG corpus priorities: which documents first (label docs, submission guidelines, curated threads, artist profiles)?
- Embeddings source: local sentence-transformers vs API-based for domain specificity?
- Who curates RAG documents and how often? Automated ingestion from Notion/Discord or manual uploads?

**TDOS Integration:**

- **Official tenant_id string**: confirm `TENANT:BREEZE_CLUB` or alternative. Can be renamed later with migration, but lock in now.
- **Abby agent contract declaration**: long-term, is Abby a "discord creative assistant + TDOS signal emitter" or broader (e.g., "multi-interface creative services agent")?
- **JSONL consumption**: Will the TDOS `CLERK:ACTIVITY` agent directly read `shared/logs/events.jsonl`, or is there a scheduled importer job that pushes signals into the TDOS ledger?
- **Event ID format**: Does `EVT-ABBY-{TIMESTAMP}-{RANDOM}` work, or do you want a deterministic sequence number?

**Operations & Deployment:**

- Radio/virtual DJ: keep under Abby or extract to separate bot later?
- LLM latency SLA: acceptable response time for slash commands (<3s for Discord, but Ollama + inference might be longer—fallback strategy?).
- How will you manage multi-server scenarios in the future (single tenant for now, but code should not assume it)?

---

## 15) Immediate Next Actions

- Approve command migration map and unified Mongo schema with tenant_id tagging.
- Greenlight Ollama-first `llm_client` abstraction + IIL schemas.
- Confirm RAG Phase 1 (Chroma) and initial corpus list.
- Provide channel IDs, moderation policy details, economy catalog.
- Decide repo split approach (branch vs folders) and begin restructuring.
- Lock in TDOS tenant_id, agent contract, and event consumption strategy.
