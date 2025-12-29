# Moderation & Qdrant Migration

This document outlines configuration and commands for moderation/engagement tuning and a path to migrate embeddings from Chroma to Qdrant.

## Moderation

- Image auto-move: Set `IMAGE_AUTO_MOVE_ENABLED=true`, `GENERAL_CHANNEL_ID=<channel_id>`, `MEMES_CHANNEL_ID=<channel_id>`.
- The cog in `handlers/moderation.py` moves image attachments from General to Memes with a friendly note.

## Nudges

- Enable periodic nudges by setting `NUDGE_ENABLED=true`.
- Configure `NUDGE_CHANNEL_ID=<channel_id>` and `NUDGE_INTERVAL_HOURS=24`.

## Twitch Commands

- `/twitch_notify enable:true channel:#breeze-tv` to enable live notifications (Manage Guild required).
- `/twitch_link @User twitch_handle` to link a Discord user to a Twitch username.

Environment:

- `TWITCH_NOTIFY_CHANNEL_ID`, `TWITCH_POLL_MINUTES`, `TWITCH_ROLE_Z8PHYR_FAM` for mentions.

## Qdrant Migration

Install dependencies: `qdrant-client`, `chromadb`, `sentence-transformers`.

Configure:

- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY` (optional).
- `CHROMA_PERSIST_DIR` for Chroma storage.

Run migration:

```
python scripts/migrate_chroma_to_qdrant.py <collection_name> <vector_size>
```

Use `MIGRATE_DRY_RUN=true` to preview without writing.
