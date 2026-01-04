# Abby Role & Modes

Abby is a **guild interface application**: a personable portal into Breeze guild systems. She is not the platform kernel, a surveillance agent, or an unbounded AI oracle.

## Positioning

- Purpose: creative assistant, community guide, light analyst, and economy steward for guilds.
- Scope: operates only through adapter surfaces (Discord today); core logic stays adapter-agnostic.
- Boundaries: opts into memory and RAG per guild; never acts as background surveillance; costs are bounded by quotas and schedules.

## Operational Modes (config-level gates)

- **Interactive Mode** — Slash commands, replies, guidance, RAG chat. Runs on explicit user intent.
- **Ambient Mode** — Opt-in emoji games and ambient prompts; scheduled, rate-limited, and non-intrusive.
- **Insight Mode** — Summaries, mod reports, guild health/status. Uses summarization outputs, not raw logs.
- **Economy Mode** — Banking, tipping, rewards, and mechanics framed as community appreciation (not money).

Each mode should be toggleable per guild and channel where applicable. Default posture: conservative (off) unless explicitly enabled by guild configuration.

## Guardrails

- **Guild isolation first**: data access and jobs are guild-scoped; cross-guild leakage is a defect.
- **Consent & opt-in**: passive listening and ambient behaviors require explicit enablement.
- **Cost controls**: message caps, cadence limits, RAG relevance thresholds, and summary compression windows stay in place.
- **Contextual assistance**: memory shapes tone/relevance; RAG supplies guild knowledge; Abby avoids asserting user facts as authority.
- **Async by default**: heavy work (summaries, ingestion) runs as jobs to keep interaction latency low.

## Local LLM Summarizer Placement

- Lives outside Abby and TDOS Memory as a **TDOS Intelligence/Jobs worker**.
- Abby queues summarization jobs; worker returns summaries (not raw text); summaries feed memory/RAG pipelines.
- Keeps Abby responsive, cost-bounded, and adapter-agnostic.

## Who Should Read This

- Maintainers deciding where new capabilities belong.
- Contributors adding features: ensure they fit a mode, respect guardrails, and stay within the portal role.
