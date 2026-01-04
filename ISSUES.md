Abby issue backlog organized by priority. Issues #1 and #2 remain for historical completeness. See [docs/architecture/ROADMAP.md](docs/architecture/ROADMAP.md) for phase sequencing and [docs/architecture/ABBY_ROLE_AND_MODES.md](docs/architecture/ABBY_ROLE_AND_MODES.md) for the portal posture.

---

## Completed

### Issue #1: Create PyPI Package for TDOS Memory ✅

- Status: done; published to PyPI and added to requirements
- Notes: deploy script supports `-Install`; docs live in [tdos_memory_package/PYPI_PUBLISHING_GUIDE.md](tdos_memory_package/PYPI_PUBLISHING_GUIDE.md)

### Issue #2: Create TDOS Memory Development Documentation ✅

- Status: done; integration/versioning/troubleshooting docs published
- Notes: see [docs/tdos-memory/](docs/tdos-memory) for details

---

## Active Backlog (ordered)

### High Priority

#### Issue #8: Fix Bank Tenant-Aware Iteration

- Scope: implement guild-scoped iteration for `bank_update()` so periodic rewards/interest cover all tenants without performance hits
- Acceptance:
  - `bank_update()` iterates across guilds and users efficiently (pagination or batching if needed)
  - Interest/rewards applied per guild
  - Tests cover the scheduled task behavior
- Status: ✅ complete; tenant-aware iterator via `list_economies()`, interest applied every 10min (0.1% daily prorated), logged per transaction
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py)

#### Issue #10: Resolve Image Generation Guild ID Parameter

- Scope: add optional `guild_id` to `get_level()` and propagate to image generation
- Acceptance:
  - `abby_core/economy/xp.py::get_level()` accepts `guild_id`
  - Call in image generation passes `guild_id`
  - Tests verify guild-scoped level checks
- Status: ✅ implemented; guild_id now wired through images quota path; validated in tests/test_economy_scoping.py (passing)
- References: [abby_core/economy/xp.py](abby_core/economy/xp.py), [abby_adapters/discord/cogs/.../images.py](abby_adapters/discord)

#### Issue #12: Update Dashboard Status Commands

- Scope: surface live metrics in status output without blocking the event loop
- Acceptance:
  - `get_active_sessions()` reads from MongoDB
  - `get_pending_submissions()` reads moderation queue
  - Optional Ollama latency check
  - Status refreshes every 5 minutes asynchronously
- Status: ✅ complete; heartbeat uses live Mongo counts + Ollama latency probe (2s timeout, /api/tags endpoint)
- References: [abby_adapters/discord/main.py](abby_adapters/discord/main.py)

#### Issue #3: Refactor Bank Cog to Modern Slash Commands

- Scope: replace legacy prefix commands with slash commands and modern embeds
- Acceptance:
  - Slash commands for balance/deposit/withdraw/history
  - Embed UI with progress bars, guild-scoped economy
  - Robust errors and tests for all operations
- Status: ✅ complete; slash commands live with currency formatting (100 BC = $1.00), transaction logging, and history retrieval
- References: [abby_adapters/discord/cogs/economy/bank.py](abby_adapters/discord/cogs/economy/bank.py)

#### Issue #7: Complete RAG Integration for Chatbot

- Scope: finish RAG retrieval + prompt injection with safe fallbacks
- Acceptance:
  - Relevant docs with metadata injected into prompts
  - Graceful fallback when RAG unavailable
  - Configurable relevance threshold
  - Docs updated in RAG guide
- References: [abby_adapters/discord/cogs/creative/chatbot.py](abby_adapters/discord/cogs/creative/chatbot.py), [abby_core/rag/handler.py](abby_core/rag/handler.py)

#### Issue #20: Peer Kudos / Breeze Coin Tipping ✅

**Status**: COMPLETED

- Scope: allow users to tip Breeze Coins with anti-abuse controls
- Acceptance:
  - ✅ `/tip @user amount [reason] [public]` with validation and daily budgets
  - ✅ Per-user daily budgets (1,000 BC); 24-hour reset cycle
  - ✅ Transactions logged as `tip` type; optional public thank-you
  - ✅ Tests for budgets, logging, self-tip prevention, and edge cases
  - ✅ Comprehensive documentation in [TIPPING_GUIDE.md](docs/features/TIPPING_GUIDE.md)
- Implementation:
  - Schema: Added `tip_budget_used` and `tip_budget_reset` fields to EconomySchema
  - Database: Added `get_tip_budget_remaining()`, `reset_tip_budget_if_needed()`, `increment_tip_budget_used()` helpers
  - Command: `/tip` command in [bank.py](abby_adapters/discord/cogs/economy/bank.py) with full validation
  - Tests: [test_tipping.py](tests/test_tipping.py) with 20+ test cases covering all scenarios
- References: [abby_core/database/schemas.py](abby_core/database/schemas.py), [abby_core/database/mongodb.py](abby_core/database/mongodb.py), [abby_adapters/discord/cogs/economy/bank.py](abby_adapters/discord/cogs/economy/bank.py), [tests/test_tipping.py](tests/test_tipping.py)

#### Issue #17: Extend Daily Emoji Game Windows and Duration

- Scope: schedule multiple daily emoji games with longer durations and safe restarts
- Acceptance:
  - Config supports at least two daily start times per guild/time zone
  - Duration configurable (default 5+ minutes) with aligned countdown messaging
  - Scheduler prevents overlap; coexists with manual `/game emoji`
  - XP rewards avoid duplicate payouts
- References: [abby_adapters/discord/cogs/entertainment/games.py](abby_adapters/discord/cogs/entertainment/games.py), [abby_adapters/discord/config.py](abby_adapters/discord/config.py)

---

### Medium Priority

#### Issue #4: Implement Interest & Savings Features

- Interest accrues on deposits (configurable cadence and rate)
- Background task applies interest; transaction log records type/timestamp/amount
- Guild-specific rates; command to view history
- Status: ✅ interest implemented; 0.1% daily (prorated per 10min), min 100 BC balance, logged as transactions
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py), [abby_adapters/discord/cogs/economy/bank.py](abby_adapters/discord/cogs/economy/bank.py)

#### Issue #5: Implement Wallet-to-Wallet Transactions

- `/pay @user amount` with balance validation, limits, cooldown
- Transactions recorded for sender and recipient
- Status: ✅ complete; `/pay` command with validation, auto-profile creation, logged as transfer for both parties
- References: [abby_adapters/discord/cogs/economy/bank.py](abby_adapters/discord/cogs/economy/bank.py)

#### Issue #6: Banking System Tests

- Unit tests for `get_economy()`, `update_balance()`
- Integration tests for deposit/withdraw, interest, transfers, history
- Target 80%+ coverage of economy module
- Status: ✅ complete — comprehensive test suite in three files:
  - `tests/test_banking_integration.py`: 14 test classes (100+ tests) covering deposit/withdraw, transfers, interest, history, guild scoping, edge cases, canonical fields
  - `tests/test_banking_edge_cases.py`: 14 test classes (50+ tests) covering validation logic, boundary conditions, concurrency, atomicity
  - `tests/test_banking_history.py`: 11 test classes (40+ tests) covering transaction history retrieval, filtering, types, formatting, multi-guild isolation
  - Total: 39 test classes, 100+ test methods validating all banking operations (Issues #3, #4, #5)
- References: [tests/test_banking_integration.py](tests/test_banking_integration.py), [tests/test_banking_edge_cases.py](tests/test_banking_edge_cases.py), [tests/test_banking_history.py](tests/test_banking_history.py), [docs/BANKING_TEST_SUITE.md](docs/BANKING_TEST_SUITE.md)

#### Issue #9: Implement Budget/Spending Analytics

- `/stats spending` for users; admin economy health view
- Weekly/monthly reports and inflation/deflation monitoring

#### Issue #18: Canonical Breeze Economy Vocabulary and Conversion

- Single source for currency labels and conversion (Breeze Coins ↔ Leaf Dollars)
- Consistent field names `wallet_balance`, `bank_balance`, `transactions`
- Embeds/commands show consistent naming; purchases recorded with metadata
- Contributor note documents currency model

#### Issue #19: Purchase Incentives and Store Shim

- Configurable per-guild catalog; slash commands to list/buy items
- Purchases deduct correct currency, log `purchase` transaction, handle insufficient funds
- Admin toggle to enable/disable store without redeploy; tests for success/failure logging

#### Issue #21: Context-Aware Ambient Messages via RAG

- Scheduled ambient messages with per-guild/channel toggles and frequency caps
- Prompt builder uses recent topics + RAG snippets; hides vector DB details
- Runtime controls (`ambient on/off`) and telemetry of used documents
- Tests for toggles and prompt assembly without external calls

#### Issue #22: Passive Listening and Guild Insights

- Background summaries of channel activity with opt-in/out controls
- Stores summaries with guild/channel tags; posts metrics to mod channel
- Cost controls (message caps, cached embeddings); tests for opt-out and storage paths

#### Issue #23: Behavioral Rewards for Channel Hygiene and Creativity

- Configurable rules per guild/channel to award coins/XP on good behavior
- Hooks into message/reaction events; logs rule fired and channel
- Admin commands to view/edit/pause rules; tests for rule matching and cooldowns

#### Issue #11: Implement YouTube URL Handling

- Detect YouTube URLs; fetch title/channel/duration; rich embed with preview
- Playlist support; optional YouTube API usage

#### Issue #13: Create Contribution Workflow Documentation

- Add `docs/getting-started/DEVELOPER_SETUP.md` (env setup, TDOS Memory install, Mongo, env vars)
- Add `docs/contributing/ARCHITECTURE_GUIDELINES.md` (core vs adapter decision tree, examples, anti-patterns)
- Update CONTRIBUTING.md with workflow, testing, style, pre-commit hooks

#### Issue #14: Add Pre-Commit Hooks for Code Quality

- `.pre-commit-config.yaml` with black, flake8, isort, mypy
- Docs and CI reuse the same checks

#### Issue #15: Expand Unit Test Coverage

- Targets: economy 80%+, database 75%+, llm 70%+ (excluding external calls)
- All tests pass locally; CI runs on PRs

#### Issue #16: Add Integration Tests for Multi-Guild Scenarios

- Verify isolation for memory, economy, settings
- Ensure cross-guild transfers/config leaks are prevented; add tests in `test_guild_isolation.py`
