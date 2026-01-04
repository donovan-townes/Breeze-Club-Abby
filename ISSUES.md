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
- Status: ✅ scan implemented (tenant-aware iterator via `list_economies()`); interest logic hook pending; coverage added and passing in tests/test_economy_scoping.py
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
- Status: ✅ heartbeat now uses live Mongo counts; Ollama latency still TODO; dashboard count filters validated via tests/test_economy_scoping.py (passing)
- References: [abby_adapters/discord/main.py](abby_adapters/discord/main.py)

#### Issue #3: Refactor Bank Cog to Modern Slash Commands

- Scope: replace legacy prefix commands with slash commands and modern embeds
- Acceptance:
  - Slash commands for balance/deposit/withdraw/history
  - Embed UI with progress bars, guild-scoped economy
  - Robust errors and tests for all operations
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py), [abby_adapters/discord/cogs/economy](abby_adapters/discord/cogs/economy)

#### Issue #7: Complete RAG Integration for Chatbot

- Scope: finish RAG retrieval + prompt injection with safe fallbacks
- Acceptance:
  - Relevant docs with metadata injected into prompts
  - Graceful fallback when RAG unavailable
  - Configurable relevance threshold
  - Docs updated in RAG guide
- References: [abby_adapters/discord/cogs/creative/chatbot.py](abby_adapters/discord/cogs/creative/chatbot.py), [abby_core/rag/handler.py](abby_core/rag/handler.py)

#### Issue #20: Peer Kudos / Breeze Coin Tipping

- Scope: allow users to tip Breeze Coins with anti-abuse controls
- Acceptance:
  - `/tip @user amount [reason]` with validation and cooldowns
  - Per-user budgets; moderation override and refund path
  - Transactions logged as `tip/reward`; optional public thank-you
  - Tests for budgets, logging, and double-spend prevention
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py), [abby_core/database/schemas.py](abby_core/database/schemas.py), [abby_adapters/discord/cogs/economy/xp_gain.py](abby_adapters/discord/cogs/economy/xp_gain.py)

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
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py), [abby_adapters/discord/cogs/economy/xp_gain.py](abby_adapters/discord/cogs/economy/xp_gain.py)

#### Issue #5: Implement Wallet-to-Wallet Transactions

- `/pay @user amount` with balance validation, limits, cooldown
- Transactions recorded for sender and recipient
- References: [abby_core/economy/bank.py](abby_core/economy/bank.py)

#### Issue #6: Banking System Tests

- Unit tests for `get_economy()`, `update_balance()`
- Integration tests for deposit/withdraw, interest, transfers, history
- Target 80%+ coverage of economy module
- Status: 🟡 partial — new scoping + dashboard helper tests added in `tests/test_economy_scoping.py` (all passing in dev); integration suite pending

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
