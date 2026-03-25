# Configuration Reference

Comprehensive guide to all environment variables, defaults, and requirements for a 50-year deployment of Abby.

**Last Updated:** January 31, 2026  
**Scope:** All deployment environments (development, staging, production)  
**Maintenance:** Update when adding new env vars or changing validation rules

---

## Quick Start

Minimum required configuration for local development:

```bash
cp .env.example .env

## Fill in these REQUIRED variables:
ABBY_TOKEN=<discord_bot_token>
MONGODB_URI=mongodb://localhost:27017
OPENAI_API_KEY=<openai_api_key>  # OR use Ollama
```python

For production deployments with RAG and distributed scheduling, see full reference below.

---

## Configuration Groups

### Discord Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `ABBY_TOKEN` | string | **YES** | none | Discord bot token from [Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_GUILD_ID` | string | no | none | Optional: test guild ID for local development (speeds up slash command sync) |

### Validation:

- `ABBY_TOKEN` must be non-empty; bot cannot start without it
- Token format: 24 alphanumeric characters followed by dot

---

### Database Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `MONGODB_URI` | string | **YES** | none | MongoDB connection string (local: `mongodb://localhost:27017` or Atlas connection string) |
| `MONGODB_DB` | string | no | `Abby_Database` | Database name within MongoDB instance |
| `MONGODB_USER` | string | no | none | MongoDB username (if authentication required) |
| `MONGODB_PASS` | string | no | none | MongoDB password (if authentication required) |

### Validation:

- `MONGODB_URI` must be valid MongoDB connection string
- Database must be accessible at startup; startup fails if connection cannot be made
- For production: use MongoDB Atlas with IP allowlist

### Connection String Examples:
```python
## Local development
mongodb://localhost:27017

## MongoDB Atlas (cloud)
mongodb+srv://username:password@cluster.mongodb.net/

## Production with authentication
mongodb://user:pass@host1,host2,host3/dbname?replicaSet=rs0
```python

---

### LLM Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `LLM_PROVIDER` | enum | no | `ollama` | LLM provider: `ollama` (local) or `openai` (cloud) |
| `OLLAMA_HOST` | string | no | `http://localhost:11434` | Ollama endpoint URL (only if `LLM_PROVIDER=ollama`) |
| `OLLAMA_MODEL` | string | no | `llama3` | Ollama model name (e.g., `llama3`, `neural-chat`) |
| `OPENAI_API_KEY` | string | conditional | none | OpenAI API key (required if `LLM_PROVIDER=openai`) |
| `OPENAI_MODEL` | string | no | `gpt-3.5-turbo` | OpenAI model (e.g., `gpt-4`, `gpt-3.5-turbo`) |

### LLM Selection Logic:

1. If `OPENAI_API_KEY` is set and `LLM_PROVIDER=openai`: use OpenAI
2. If `OLLAMA_HOST` is reachable and `LLM_PROVIDER=ollama`: use Ollama
3. Otherwise: fallback to OpenAI (if key available)
4. If neither available: bot responds with degraded LLM_UNAVAILABLE error

### Temperature & Tokens:

- `LLM_TEMPERATURE` (float, 0.0-2.0, default: 0.7) — creativity level
- `LLM_MAX_TOKENS` (int, default: 2000) — max response length
- `LLM_TIMEOUT_SECONDS` (int, default: 30) — request timeout

---

### RAG Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `RAG_CONTEXT_ENABLED` | bool | no | `false` | Enable/disable RAG context injection in chatbot |
| `VECTOR_STORE` | enum | no | `chroma` | Vector database: `chroma` (dev) or `qdrant` (production) |
| `CHUNK_SIZE` | int | no | `500` | Document chunk size (in characters) |
| `CHUNK_OVERLAP` | int | no | `50` | Overlap between chunks (prevents context loss) |
| `EMBEDDING_MODEL` | string | no | `all-MiniLM-L6-v2` | Embedding model for encoding documents |
| `EMBEDDING_DEVICE` | enum | no | `cpu` | `cpu` or `cuda` (for GPU acceleration) |
| `CHROMA_PERSIST_DIR` | string | no | `./chroma_db` | ChromaDB storage directory |
| `CHROMA_HOST` | string | no | none | Optional: remote Chroma host (for distributed setup) |
| `QDRANT_HOST` | string | no | `localhost` | Qdrant server host (for production RAG) |
| `QDRANT_PORT` | int | no | `6333` | Qdrant server port |
| `QDRANT_API_KEY` | string | no | none | Qdrant API key (if using Qdrant Cloud) |
| `MIGRATE_DRY_RUN` | bool | no | `false` | Dry run for Chroma → Qdrant migration (no changes) |

### RAG Selection Logic:

- If `RAG_CONTEXT_ENABLED=false`: RAG disabled (memory only)
- If `VECTOR_STORE=chroma`: use ChromaDB (development)
- If `VECTOR_STORE=qdrant`: use Qdrant (production, scales to 100+ guilds)

---

### Path Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `WORKING_DIRECTORY` | path | no | `<current_directory>` | Root working directory |
| `IMAGES_DIR` | path | no | `Images` | Directory for user-generated images |
| `AUDIO_ROOT` | path | no | `Audio_Recordings` | Directory for audio files |
| `SONGS_DIR` | path | no | `songs` | Directory for music files |
| `LOG_FILE_PATH` | path | no | `logs/abby.log` | Log file path |
| `TDOS_EVENTS_PATH` | path | no | `shared/logs/events.jsonl` | TDOS event log path |

### Path Resolution:

- All paths are relative to `WORKING_DIRECTORY` unless absolute
- Directories are created automatically at startup if missing
- Use absolute paths for production (e.g., `/opt/abby/shared/storage`)

---

### Storage & Quotas

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `STORAGE_ROOT` | path | **YES** (production) | none | Root storage directory for all user data |
| `MAX_GLOBAL_STORAGE_MB` | int | no | `5000` | Total bot storage limit across all users |
| `MAX_USER_STORAGE_MB` | int | no | `500` | Per-user storage limit |
| `MAX_USER_DAILY_GENS` | int | no | `5` | Daily image generation limit per user |
| `CLEANUP_DAYS` | int | no | `7` | Auto-delete files after N days |
| `OWNER_USER_IDS` | csv | no | none | Comma-separated Discord user IDs with unlimited storage |
| `OWNER_DAILY_LIMIT` | int | no | `9999` | Daily gen limit for owners (effectively unlimited) |

### Quota Overrides by Level:

- Level 1-4: 10 daily gens
- Level 5-9: 25 daily gens
- Level 10+: 50 daily gens
- Owner: 9999 daily gens (unlimited)

---

### Timing & Intervals

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `XP_MESSAGE_COOLDOWN_SECONDS` | int | no | `60` | Cooldown between XP gains from messages |
| `XP_ATTACHMENT_COOLDOWN_SECONDS` | int | no | `600` | Cooldown between XP gains from attachments |
| `XP_STREAM_INTERVAL_MINUTES` | int | no | `5` | Stream XP grant interval (for Twitch streamers) |
| `XP_DAILY_START_HOUR` | int | no | `5` | UTC hour when daily XP reset occurs |
| `TWITCH_POLL_MINUTES` | int | no | `15` | Check for Twitch streams every N minutes |
| `NUDGE_INTERVAL_HOURS` | int | no | `24` | Send engagement nudges every N hours |
| `MOTD_START_HOUR` | int | no | `5` | Hour to send message-of-the-day (UTC) |

---

### Economy & Banking

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `BANK_INTEREST_RATE_DAILY` | float | no | `0.001` | Daily interest rate (as decimal: 0.001 = 0.1% per day) |
| `BANK_INTEREST_MIN_BALANCE` | int | no | `100` | Minimum balance to earn interest |

### Interest Calculation (50-year projection):
```python
Daily: balance * (1 + BANK_INTEREST_RATE_DAILY)
Formula: final_balance = initial * (1 + rate)^days
Example: 100 Breeze Coins at 0.1%/day for 50 years = ~$1.65B
```python

---

### XP System

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `XP_BASE_AMOUNT` | int | no | `10` | Base XP per message |
| `XP_MESSAGE_BONUS` | int | no | `5` | Bonus XP for messages > 50 characters |
| `XP_MEDIA_BONUS` | int | no | `10` | Bonus XP for messages with attachments |

### XP Thresholds:

- Level 1: 0 XP
- Level 5: 1000 XP
- Level 10: 5000 XP
- Level 20: 20000 XP

---

### Twitch Integration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `TWITCH_CLIENT_ID` | string | conditional | none | Twitch app client ID (required if Twitch integration enabled) |
| `TWITCH_CLIENT_SECRET` | string | conditional | none | Twitch app client secret |
| `TWITCH_NOTIFY_CHANNEL_ID` | string | no | none | Discord channel for stream notifications |
| `TWITCH_ROLE_Z8PHYR_FAM` | string | no | none | Role ID to tag on specific streamer notifications |

---

### External APIs

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `OPENAI_API_KEY` | string | conditional | none | OpenAI API key (required if using OpenAI) |
| `STABILITY_API_KEY` | string | no | none | Stability AI key for image generation |
| `YOUTUBE_API_KEY` | string | no | none | YouTube API key for video lookups |
| `EMOTE_API_KEY` | string | no | none | Custom emoji API key |

---

### Moderation & Engagement

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `IMAGE_AUTO_MOVE_ENABLED` | bool | no | `false` | Auto-move images from general to memes channel |
| `GENERAL_CHANNEL_ID` | string | conditional | none | Channel to monitor for images (if auto-move enabled) |
| `MEMES_CHANNEL_ID` | string | conditional | none | Channel to move images to |
| `NUDGE_ENABLED` | bool | no | `false` | Enable engagement nudges for inactive users |
| `NUDGE_CHANNEL_ID` | string | conditional | none | Channel to send nudge messages |

---

### TDOS Configuration

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `TDOS_TENANT_ID` | string | no | `TENANT:BREEZE_CLUB` | Tenant identity for multi-server deployments |
| `TDOS_AGENT_SUBJECT_ID` | string | no | `AGENT:ABBY-DISCORD` | Agent identity (Abby) |
| `TDOS_MACHINE_SUBJECT_ID` | string | no | `MACHINE:TSERVER` | Machine identity from TDOS registry |
| `TDOS_EVENT_ID_PREFIX` | string | no | `EVT-ABBY` | Prefix for event IDs in TDOS telemetry |

---

### Logging & Observability

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `LOG_LEVEL` | enum | no | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `JSON_LOGS` | bool | no | `false` | Enable structured JSON logging (for parsing by monitoring systems) |
| `ABBY_SCHEDULER_VERBOSE` | bool | no | `false` | Enable verbose scheduler logging |
| `ABBY_SCHEDULER_SUMMARY_INTERVAL_MINUTES` | int | no | `60` | Emit scheduler summary every N minutes |

---

### Feature Flags

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `RAG_CONTEXT_ENABLED` | bool | no | `false` | Enable RAG context injection |
| `NUDGE_ENABLED` | bool | no | `false` | Enable user engagement nudges |
| `IMAGE_AUTO_MOVE_ENABLED` | bool | no | `false` | Auto-move images to memes channel |

---

### Security & Secrets

| Variable | Type | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `SALT` | string | **YES** (production) | none | Cryptographic salt for password hashing (min 32 characters) |

### Salt Generation (50-year safety):
```bash
## Generate strong salt
python -c "import secrets; print(secrets.token_hex(32))"

## Output: 9a8c7b6f5e4d3c2b1a0f9e8d7c6b5a4f (64 characters)
```python

---

## Validation & Health Checks

At startup, Abby validates configuration and logs warnings:

```python
❌ CRITICAL: OPENAI_API_KEY not set but LLM provider is OpenAI
⚠️  WARNING: MongoDB URI not configured - persistence will be unavailable
⚠️  WARNING: RAG enabled but Qdrant not configured
⚠️  WARNING: Working directory does not exist: <path>
```python

Critical errors prevent startup; warnings are logged but allow graceful degradation.

---

## Environment-Specific Profiles

### Local Development

```bash
LLM_PROVIDER=ollama
VECTOR_STORE=chroma
RAG_CONTEXT_ENABLED=false
JSON_LOGS=false
LOG_LEVEL=DEBUG
```python

### Staging

```bash
LLM_PROVIDER=openai
VECTOR_STORE=chroma
RAG_CONTEXT_ENABLED=true
JSON_LOGS=true
LOG_LEVEL=INFO
```python

### Production (100+ guilds, 50-year scale)

```bash
LLM_PROVIDER=openai
VECTOR_STORE=qdrant
RAG_CONTEXT_ENABLED=true
JSON_LOGS=true
LOG_LEVEL=WARNING
STORAGE_ROOT=/opt/abby/shared/storage
MAX_GLOBAL_STORAGE_MB=50000
OWNER_DAILY_LIMIT=9999
```python

---

## Rotation & 50-Year Maintenance

### Annual Review

- [ ] Audit all API keys (OpenAI, Stability, Twitch)
- [ ] Verify SALT hasn't been exposed
- [ ] Check storage quotas (are they still appropriate?)
- [ ] Review interest rates (economic balance check)
- [ ] Audit XP multipliers across levels

### 5-Year Reviews

- [ ] Re-evaluate storage infrastructure (50TB → 500TB?)
- [ ] Benchmark LLM providers (cost vs performance)
- [ ] Review interest rate projections (50-year model still valid?)
- [ ] Audit access controls (OWNER_USER_IDS, role limits)

### 10-Year Reviews

- [ ] Full database schema audit
- [ ] Archive old logs (compliance)
- [ ] Review configuration for deprecation
- [ ] Plan next-generation storage strategy

---

## Related Documents

- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) — API key management, rotation procedures
- [STARTUP_OPERATIONS_GUIDE.md](STARTUP_OPERATIONS_GUIDE.md) — Configuration validation at startup
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) — Runtime configuration tuning
