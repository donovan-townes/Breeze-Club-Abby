# Abby Roadmap (Architecture-Aligned)

Purpose: anchor the backlog to explicit architectural intent. Issues are tracked in [ISSUES.md](../../ISSUES.md); this doc locks sequencing and rationale.

## Buckets

- **Platform Hardening (Correctness)** — multi-guild safety, economy integrity, telemetry accuracy. Issues: #8, #10, #12, #6, #16, #18.
- **Guild Value (Experience)** — features that make Abby worth having. Issues: #3, #7, #17, #20, #21, #22, #23.
- **Engagement Mechanics (Economy Extensions)** — optional loops once core is stable. Issues: #4, #5, #9, #18, #19.

## Execution Order

### Phase 1 — Hardening (must-lock)

- #8 Bank tenant-aware iteration
- #10 Image generation guild_id fix
- #12 Dashboard status accuracy
- #6 Banking system tests
- #16 Multi-guild isolation tests
- #18 Canonical economy vocabulary

### Phase 2 — Core Guild Value

- #3 Bank slash-command refactor
- #7 RAG integration completion
- #20 Peer kudos / tipping

### Phase 3 — Intelligence & Delight

- #21 Context-aware ambient messages
- #22 Passive listening & guild insights
- #17 Extended emoji game scheduling

### Phase 4 — Engagement Mechanics & Storefront

- #19 Purchase/store shim
- #9 Spending analytics
- #4 Interest & savings
- #5 Wallet transfers (if not finished earlier)

## Architectural Notes

- Abby remains the **guild portal**, not the platform kernel; core/adapter separation stays strict.
- Modes (see [ABBY_ROLE_AND_MODES](ABBY_ROLE_AND_MODES.md)): Interactive, Ambient, Insight, Economy. Every new feature must declare its mode and default toggle posture.
- Local LLM summarizer runs as an external job worker (TDOS Intelligence/Jobs); Abby consumes summaries, not raw transcripts.
- Guardrails stay in place: guild isolation, opt-in ambient/passive behaviors, cost caps, RAG relevance thresholds.

## Definition of Done per Phase

- **Phase 1**: All hardening issues closed; tests green; dashboards reflect live data; vocabulary unified.
- **Phase 2**: Slash bank live; RAG stable with fallbacks; tipping live with anti-abuse; contributor docs updated.
- **Phase 3**: Ambient and insights gated, configurable, and cost-bounded; telemetry proves no cross-guild leakage.
- **Phase 4**: Store/purchase and analytics loops available; economy mechanics framed as community appreciation, not currency.

## How to Use

- When opening PRs, cite the phase and bucket (e.g., "Phase 1 / Hardening / #8").
- If a feature crosses modes, document the default toggles and guardrails in its README or cog doc.
- Revisit this roadmap after each phase to confirm sequencing and add any newly discovered hardening gaps.
