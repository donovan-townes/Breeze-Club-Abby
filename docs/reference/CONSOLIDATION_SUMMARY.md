# Documentation Consolidation Summary

**Status:** Pre-creation of missing documentation  
**Date:** January 31, 2026

This document tracks where key details currently live so they can be properly consolidated into the missing documentation.

## Details Inventory by Gap

### 1. Configuration Reference (all env vars, required vs optional, defaults)

### Current Locations:

- `abby_core/config/base.py` (APIConfig, DatabaseConfig, LLMConfig, RAGConfig, TimingConfig, PathConfig, StorageConfig, LoggingConfig, TelemetryConfig, MiscConfig, FeatureFlags)
- `.env.example` (comprehensive list of all vars with descriptions and groupings)
- `README.md` (partial config reference)
- `abby_core/config/channels.py` (ChannelMapping defaults)
- `abby_core/config/features.py` (FeatureFlags)
- `abby_core/config/utils.py` (getenv_bool, getenv_int, getenv_float helpers)

### Key Details to Consolidate:

- All environment variable names (ABBY_TOKEN, MONGODB_URI, OPENAI_API_KEY, QDRANT_HOST, etc.)
- Type (bool, int, string, optional)
- Default values (where applicable)
- Required vs optional status
- Purpose and use case for each
- Validation rules (ranges, enums)
- Example values

### Schema Groups:

- Discord Configuration
- Database Configuration
- LLM Configuration
- RAG Configuration
- Path Configuration
- Storage & Quotas
- Timing & Intervals
- Economy & Banking
- XP System
- Twitch Integration
- Telemetry (TDOS)
- Moderation & Engagement
- Feature Flags
- External APIs
- TDOS Configuration

---

### 2. Security and Secrets Handling (token storage, rotation, least privilege)

### Current Locations:

- `abby_core/security/encryption.py` (PBKDF2 + Fernet encryption implementation)
- `abby_core/interfaces/prompt_security.py` (PromptSecurityGate interface and StandardPromptSecurityGate)
- `docs/states/CONFIGURATION_STATE.md` (mentions SALT in config)
- `abby_core/discord/config.py` (DiscordBotInfo token validation)
- `.env.example` (API_KEY references)
- `abby_core/database/session_repository.py` (session security mentions)
- `abby_core/discord/cogs/user/privacy_panel.py` (user privacy/data management)

### Key Details to Consolidate:

- Token storage mechanism (environment variables, not hardcoded)
- Encryption scheme (Fernet with PBKDF2-derived key)
- SALT requirement and generation
- Prompt injection detection (InjectionSeverity levels: SAFE, SUSPICIOUS, BLOCKED)
- Protected fields: guild_name, user_name, channel_name
- Session encryption in MongoDB
- API key management (OpenAI, Stability, Twitch, Qdrant)
- Rotation procedures (where applicable)
- Least privilege patterns (owner_user_ids overrides, role-based access)
- Data sanitization in RAG context

### Security Boundaries:

- User data isolation (guild-scoped)
- Role-based quotas and overrides
- Admin access levels (owner, admin, moderator, member)
- Session-level isolation
- Transient vs persistent sensitive data

---

### 3. Observability Runbook (logs, metrics, alerts, DLQ triage)

### Current Locations:

- `abby_core/observability/logging.py` (StructuredJSONLHandler, log_startup_phase, JSONL format)
- `abby_core/observability/conversation_metrics.py` (ConversationMetrics class, state transition tracking)
- `abby_core/services/metrics_service.py` (MetricsService, transition/timing/error recording)
- `abby_core/discord/adapters/scheduler_bridge.py` (HeartbeatJobHandler)
- `docs/guides/STARTUP_OPERATIONS_GUIDE.md` (metrics to track, alerting rules, Grafana setup)
- `docs/states/LIFECYCLE_STATE.md` (audit trail details, DLQ diagnostics)
- `abby_core/services/dlq_service.py` (failure categorization: state_transition, validation, transient, unknown)
- `logs/abby.jsonl` (actual log output format)

### Key Details to Consolidate:

- Logging architecture (JSONL handler, structured format)
- Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Startup metrics (50-year baseline):
  - total_startup_time_seconds
  - phase_core_services_seconds (baseline: 0.0-0.5s)
  - phase_mongodb_seconds (baseline: 0.02-0.1s)
  - phase_scheduler_seconds (baseline: 0.0-0.1s)
  - phase_cogs_seconds (baseline: 1.5-3s)
  - phase_connection_seconds (baseline: 2-5s)
  - health_mongodb_status, health_storage_status, health_image_gen_status, health_scheduler_status
  - cog_count (should be 33), command_count (should be 8)
- Metrics tracked:
  - Generation time (LLM invocation)
  - Queue wait time
  - Delivery time
  - Total cycle time
  - Error rates by category
  - Retry rates
- Alerting rules:
  - CRITICAL (page immediately): startup_time > 20s, MongoDB DEGRADED, cog_count < 25
  - WARNING (investigate within 1h): connection_time > 10s, mongodb_time > 0.5s, startup_time > 15s
  - INFO (log for trending)
- DLQ triage workflow:
  - Failure categorization
  - Retry history tracking (last 3 attempts)
  - Diagnostics and remediation suggestions
- Grafana dashboard setup with Prometheus ingestion
- Key logs to watch (e.g., `[📝 announcement] CREATED`, `[⏰] Scheduler tick`)

---

### 4. Scheduler and Job Catalog (all scheduled jobs + ownership)

### Current Locations:

- `abby_core/services/scheduler.py` (SchedulerService, ScheduleConfig, job types)
- `abby_core/discord/adapters/scheduler_bridge.py` (job registration, job handlers)
- `abby_core/discord/adapters/scheduler_bridge.py` (guild job tick via SchedulerService)
- `abby_core/database/collections/scheduler_jobs.py` (scheduler_jobs collection schema)
- `abby_core/discord/cogs/system/job_handlers.py` (handler implementations, registry)

### Key Details to Consolidate:

- Scheduler architecture (platform-agnostic asyncio-based)
- Tick interval (default 60 seconds)
- Schedule types supported:
  - Interval: every N minutes (with optional jitter)
  - Daily: at specific time in timezone
  - Date-based: once at specific date/time
- All scheduled jobs with details:
  - heartbeat (interval: 1 min, scope: system)
  - xp_streaming (interval: configurable via XP_STREAM_INTERVAL_MINUTES, scope: system)
  - giveaway_check (interval: 1 min, scope: system)
  - nudge_check (interval: configurable via NUDGE_INTERVAL_HOURS, scope: system)
  - unified_content_dispatcher (interval: 1 min, scope: system) - generation → delivery → cleanup
  - dlq_retry (interval: varies, scope: system)
  - System jobs (from system config): announcements, maintenance, analytics/reporting
  - Guild jobs (from guild config): games.emoji, random_messages, motd, etc.
- Job claim/execution pattern (atomic with last_run_at tracking)
- Rollback on failure (transaction-like semantics)
- Job status: enabled/disabled
- Idempotency guarantees (same job won't run twice in overlapping ticks)
- Handler registry pattern (annotation-based: @register_job_handler)
- Error handling and retry logic

---

### 5. Adapter Contract Overview (Discord adapter boundaries and contracts)

### Current Locations:

- `abby_core/interfaces/tools.py` (IServerInfoTool, IUserInfoTool, IUserXPTool, IBotStatusTool)
- `abby_core/interfaces/output.py` (IOutputFormatter, IAnnouncementDelivery)
- `abby_core/interfaces/economy.py` (IEconomyService, IXPService, IEconomyAdapter)
- `abby_core/interfaces/llm.py` (ContextUser, Channel, Message, PlatformClient)
- `abby_core/interfaces/prompt_security.py` (PromptSecurityGate)
- `abby_core/discord/adapters/__init__.py` (Discord implementations)
- `abby_core/discord/adapters/scheduler_bridge.py` (job handlers)
- `abby_core/discord/adapters/economy.py` (BankCog)
- `abby_core/adapters/orchestrator_adapter.py` (OrchestratorAdapter)
- `abby_core/adapters/rag_adapter.py` (RAGAdapter)
- `tests/test_adapter_contracts.py` (contract validation tests)

### Key Details to Consolidate:

- Adapter pattern: platform-agnostic interfaces + Discord implementations
- Tool interfaces:
  - IServerInfoTool: server_info() → ServerInfo
  - IUserInfoTool: user_info(user_id) → UserInfo
  - IUserXPTool: user_xp(user_id) → UserXPInfo, increment_xp(user_id, amount)
  - IBotStatusTool: bot_status() → BotStatus
- Output interfaces:
  - IOutputFormatter: format_message(OutputMessage) → Discord Embed
  - IAnnouncementDelivery: deliver(guild_id, message) → success/failure
- Economy interfaces:
  - IEconomyService: get_balance, update_balance, deposit, withdraw, tip, transfer
  - IXPService: get_xp, increment_xp, get_level
  - IEconomyAdapter: combined interface for both
- Discord implementations:
  - DiscordServerInfoTool (from guild context)
  - DiscordUserXPTool (from xp service)
  - DiscordBotStatusTool (health check)
  - DiscordOutputFormatter (Embed building)
  - DiscordAnnouncementDelivery (message sending to channels)
- Adapter bridging:
  - OrchestratorAdapter: adds personality, guild context, economy integration
  - RAGAdapter: adds guild isolation, storage quotas, premium features
  - SchedulerBridge: job handlers for Discord
  - EconomyAdapter: BankCog for user-facing commands
- Factory pattern for adapter registration (EconomyAdapterFactory, ToolFactory)
- Contract validation tests

---

### 6. RAG Architecture and Data Lifecycle (Chroma/Qdrant, ingestion, cleanup)

### Current Locations:

- `abby_core/rag/handler.py` (ingest, query, delete, rebuild_chroma_from_mongodb, sync_check)
- `abby_core/rag/qdrant_client.py` (QdrantWrapper, vector operations)
- `abby_core/rag/chroma_client.py` (ChromaClient, ChromaDB persistence)
- `abby_core/rag/prepare.py` (prepare_rag_text, validate_prepared_text)
- `abby_core/rag/memory_formatter.py` (context formatting, token estimation)
- `abby_core/adapters/rag_adapter.py` (RAGAdapter, guild isolation, quota checks)
- `abby_core/discord/cogs/admin/rag.py` (Discord commands)
- `abby_core/ops/database/migrate_chroma_to_qdrant.py` (migration script)
- `docs/guides/QDRANT_MIGRATION_GUIDE.md` (comprehensive migration guide)

### Key Details to Consolidate:

- RAG architecture overview:
  - Provider abstraction (ChromaProvider vs QdrantProvider)
  - Guild-level isolation (guild_id scoping)
  - Ingestion → chunking → embedding → storage
  - Query → vector search → reranking → context injection
- Ingestion workflow:
  - Input validation (prepare_rag_text)
  - Document chunking (configurable chunk_size, chunk_overlap)
  - Embedding generation (EMBEDDING_MODEL: all-MiniLM-L6-v2)
  - Metadata tagging (document_type, scope, guild_id, user_id, tags)
  - Version tracking (idempotent via generate_document_id)
  - Storage quota enforcement
- Storage:
  - ChromaDB (development): persistent local directory (CHROMA_PERSIST_DIR)
  - Qdrant (production): scalable vector DB (QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY)
- Query workflow:
  - Text encoding
  - Vector similarity search (top_k configurable, default 3)
  - Result reranking
  - Discord formatting
- Cleanup:
  - TTL policies (auto-expire old documents)
  - Manual deletion (delete_document_id)
  - Guild deletion cascades
- Document types:
  - guidelines, policy, faq, documentation, weekly_summary, artist_bio, submission_rules, other
- Scopes:
  - community, gameplay, economy, moderation, announcements, canon_reference, other
- ChromaDB → Qdrant migration:
  - When to migrate (> 100 guilds, > 10k docs, < 100ms latency required)
  - Dry run validation (MIGRATE_DRY_RUN=true)
  - Atomic migration script
  - Performance benchmarks (73% faster queries, 7.5x higher throughput)
  - Rollback procedure (tar restore + code revert)

---

### 7. Test Strategy and Environments (unit vs integration, fixtures, CI expectations)

### Current Locations:

- `tests/conftest.py` (pytest configuration, fixtures, markers)
- `tests/README.md` (testing guide overview)
- `docs/architecture/INTENT_ARCHITECTURE.md` (testing strategy section)
- Various test files:
  - `test_state_management.py` (state tests)
  - `test_adapter_contracts.py` (contract validation)
  - `test_metrics_service.py` (metrics tests)
  - `test_unified_content_dispatcher.py` (integration tests)
  - `test_conversation_fsm.py` (FSM tests)
  - `test_scheduler_idempotency.py` (idempotency tests)
  - `test_dlq_integration.py` (DLQ tests)
  - etc.

### Key Details to Consolidate:

- Test environment setup:
  - Unit tests (no DB): mocked MongoDB, fixtures
  - Integration tests (requires pytest -m integration): real MongoDB
- Fixtures (from conftest.py):
  - mock_db: in-memory MongoDB replacement
  - reset_global_metrics: metric reset
  - clean_state_collections: state collection cleanup
  - mock_bot: Discord bot mock
- Pytest markers:
  - @pytest.mark.architecture - Architecture compliance tests
  - @pytest.mark.adapters - Adapter contract tests
  - @pytest.mark.state - State management tests
  - @pytest.mark.integration - Integration tests (requires real DB)
- Test execution patterns:
  - Run specific test: `pytest tests/test_name.py::TestClass::test_method -v`
  - Run by marker: `pytest -m architecture -v`
  - Run with coverage: `pytest --cov=abby_core --cov-report=term-missing`
  - Run async tests: `pytest -m asyncio`
- Dependencies:
  - pytest (core)
  - pytest-asyncio (async support)
  - pytest-mock (mocking)
  - mongomock (MongoDB mocking)
- CI/CD integration:
  - GitHub Actions workflow example
  - Install dependencies
  - Run architecture tests
  - Run integration tests (if available)
  - Verify zero architecture violations (lint_layers.py)
- Test coverage expectations
- Mock patterns (AsyncMock, MagicMock, patch)

---

### 8. Incident Response and Rollback (how to recover, what to check first)

### Current Locations:

- `abby_core/discord/cogs/admin/operator_panel.py` (OperatorPanel with health checks, XP reset, rollback)
- `abby_core/system/system_operations.py` (multi-phase operation framework with rollback)
- `abby_core/system/season_reset_operations.py` (XP reset operations with snapshot/rollback)
- `docs/guides/QDRANT_MIGRATION_GUIDE.md` (rollback procedure)
- `logs/abby.jsonl` (error logs, event logs)
- `shared/logs/events.jsonl` (TDOS events with ERROR type)
- `abby_core/services/dlq_service.py` (failure diagnostics, retry history)
- `docs/states/LIFECYCLE_STATE.md` (DLQ diagnostics section)

### Key Details to Consolidate:

- Platform health checks:
  - MongoDB status (OK, DEGRADED, DOWN)
  - Storage status (OK, DISABLED)
  - Image generation status (OK, DISABLED)
  - Scheduler status (OK, DEGRADED)
  - Ollama availability
  - OpenAI connectivity
- Error categorization (from DLQService):
  - state_transition: violation of state machine invariants
  - validation: failed effects validation
  - transient: network/temporary (retry-able)
  - unknown: unclassified
- Multi-phase operation framework:
  - Phase A: Freeze intent (create_xp_season_reset)
  - Phase B: Snapshot anchor (snapshot_before_xp_reset)
  - Phase C: Apply mutation (apply_xp_season_reset)
  - Phase D: Update summaries (recompute_summaries_after_reset)
  - Phase E: Announce (via delivery job)
- Rollback procedure:
  - Check operation status in MongoDB `system_operations`
  - Snapshot exists in `operation_snapshots`
  - Restore data from snapshot
  - Mark operation as ROLLED_BACK
  - Invalidate affected caches (user_summary, guild_summary)
- Failure recovery:
  - Dry run first (-dry-run flag)
  - Check logs (shared/logs/events.jsonl for errors)
  - Verify snapshot integrity
  - Atomic rollback with transaction semantics
  - Re-run operation after fix
- What to check first (triage):
  1. Platform health status (operator_panel → System > Health)
  2. Recent errors (logs/abby.jsonl, search for ERROR level)
  3. DLQ service (check failure count and categories)
  4. Scheduler status (heartbeat cadence, long-running jobs)
  5. MongoDB health (ping, collection sizes)
  6. In-flight operations (system_operations collection)
- Common issues and resolutions:
  - MongoDB unavailable → restart MongoDB, check connection string
  - Ollama unavailable → restart Ollama, or fallback to OpenAI
  - OpenAI API key invalid → update OPENAI_API_KEY, retry
  - Scheduler stuck → restart bot (graceful shutdown + restart)
  - Operation timeout → increase timeout, mark as failed, retry

---

## Consolidation Task List

Before creating missing documentation:

- [ ] **Configuration reference:** Consolidate all env vars into single authoritative document
- [ ] **Security guide:** Extract encryption, token handling, sanitization patterns
- [ ] **Observability runbook:** Extract metrics, logging, alerting from scattered sources
- [ ] **Scheduler catalog:** Generate full list of jobs with ownership and schedule details
- [ ] **Adapter contracts:** Consolidate interface definitions and implementation patterns
- [ ] **RAG guide:** Extract lifecycle from handler, migration, and adapter code
- [ ] **Test guide:** Extract infrastructure, fixtures, and CI patterns
- [ ] **Incident response:** Extract multi-phase operations, triage procedures, rollback patterns

---

## Next Steps

Ready to create missing documentation with all details consolidated:

1. guides/CONFIGURATION_REFERENCE.md
2. guides/SECURITY_GUIDE.md
3. guides/OBSERVABILITY_RUNBOOK.md
4. guides/SCHEDULER_JOBS_CATALOG.md
5. architecture/ADAPTER_CONTRACTS.md
6. guides/RAG_GUIDE.md
7. guides/TEST_STRATEGY.md
8. guides/INCIDENT_RESPONSE.md
