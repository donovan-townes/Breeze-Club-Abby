"""
Database Collections Module

All database collections follow the CollectionModule foolproof pattern:
- Each collection has one dedicated module
- All required methods are enforced at import time (via __init_subclass__)
- Auto-registration with central registry
- Idempotent initialization

Collections (37/37 - 100% COMPLETE):
P0 (3):
- guild_configuration.py - Guild-specific settings and configuration
- chat_sessions.py - User conversation sessions
- economy.py - User balance tracking and transactions

P1 (3):
- users.py - User profiles (universal profile nexus - now supports social/creative accounts)
- xp.py - User XP and levels
- submissions.py - User-submitted content

P2 (6):
- rag_documents.py - RAG knowledge base
- content_delivery.py - Scheduled announcements
- system_state.py - System state management
- transactions.py - Transaction audit trail
- random_content_items.py - Random message content pool
- system_configuration.py - System-wide operator config

P3 (7):
- music_genres.py - Music genre data
- bot_settings.py - Bot configuration
- user_tasks.py - User tasks and goals
- system_changelog.py - System changelog and updates
- system_operations.py - System operation tracking
- operation_snapshots.py - Operation state snapshots
- generation_audit.py - LLM generation audit trail

P4 (15) - Utility & Tracking Collections:
- user_levels.py - Permanent level tracking (separate from seasonal XP)
- scheduler_jobs.py - Job scheduling with status/next_run tracking
- system_state_instances.py - Runtime state instances with versioning
- user_summary.py - Materialized user stats view for leaderboards
- economy_audit.py - Transaction audit trail
- user_privacy_settings.py - Privacy preferences and consent
- config_audit_log.py - Guild configuration change audit
- content_delivery_metrics.py - Delivery metrics with 90-day TTL
- content_delivery_dlq.py - Dead letter queue for failed deliveries
- canon_staging.py - Staged persona/lore changes awaiting approval
- canon_commits.py - Approved canon change history (immutable)
- book_frontmatter.py - Canonical book/frontmatter documents
- lore_documents.py - Canonical lore and worldbuilding
- persona_identity.py - Canonical persona definitions
- rag_metrics.py - RAG query metrics with 30-day TTL

P5 (3) - Engagement Collections:
- giveaways.py - Giveaway lifecycle and participation
- game_stats.py - Per-game performance stats
- memes.py - Meme assets and voting
"""

# Import all collections to trigger auto-registration
# Order matters - independent collections can be in any order

# P0 Collections
from abby_core.database.collections.guild_configuration import GuildConfiguration
from abby_core.database.collections.chat_sessions import ChatSessions
from abby_core.database.collections.economy import Economy

# P1 Collections
from abby_core.database.collections.users import Users
from abby_core.database.collections.xp import XP
from abby_core.database.collections.submissions import Submissions

# P2 Collections
from abby_core.database.collections.rag_documents import RAGDocuments
from abby_core.database.collections.content_delivery import ContentDelivery
from abby_core.database.collections.system_state import SystemState
from abby_core.database.collections.transactions import Transactions
from abby_core.database.collections.random_content_items import RandomContentItems
from abby_core.database.collections.system_configuration import SystemConfiguration

# P3 Collections
from abby_core.database.collections.music_genres import MusicGenres
from abby_core.database.collections.bot_settings import BotSettings
from abby_core.database.collections.user_tasks import UserTasks
from abby_core.database.collections.system_changelog import SystemChangelog
from abby_core.database.collections.system_operations import SystemOperations
from abby_core.database.collections.operation_snapshots import OperationSnapshots
from abby_core.database.collections.generation_audit import GenerationAudit

# P4 Collections - Utility & Tracking
from abby_core.database.collections.user_levels import UserLevels
from abby_core.database.collections.scheduler_jobs import SchedulerJobs
from abby_core.database.collections.system_state_instances import SystemStateInstances
from abby_core.database.collections.user_summary import UserSummary
from abby_core.database.collections.economy_audit import EconomyAudit
from abby_core.database.collections.user_privacy_settings import UserPrivacySettings
from abby_core.database.collections.config_audit_log import ConfigAuditLog
from abby_core.database.collections.content_delivery_metrics import ContentDeliveryMetrics
from abby_core.database.collections.content_delivery_dlq import ContentDeliveryDLQ
from abby_core.database.collections.canon_staging import CanonStaging
from abby_core.database.collections.canon_commits import CanonCommits
from abby_core.database.collections.book_frontmatter import BookFrontmatter
from abby_core.database.collections.lore_documents import LoreDocuments
from abby_core.database.collections.persona_identity import PersonaIdentity
from abby_core.database.collections.rag_metrics import RAGMetrics
from abby_core.database.collections.giveaways import Giveaways
from abby_core.database.collections.game_stats import GameStats
from abby_core.database.collections.memes import Memes

__all__ = [
    # P0
    "GuildConfiguration",
    "ChatSessions", 
    "Economy",
    # P1
    "Users",
    "XP",
    "Submissions",
    # P2
    "RAGDocuments",
    "ContentDelivery",
    "SystemState",
    "Transactions",
    "RandomContentItems",
    "SystemConfiguration",
    # P3
    "MusicGenres",
    "BotSettings",
    "UserTasks",
    "SystemChangelog",
    "SystemOperations",
    "OperationSnapshots",
    "GenerationAudit",
    # P4 - Utility & Tracking
    "UserLevels",
    "SchedulerJobs",
    "SystemStateInstances",
    "UserSummary",
    "EconomyAudit",
    "UserPrivacySettings",
    "ConfigAuditLog",
    "ContentDeliveryMetrics",
    "ContentDeliveryDLQ",
    "CanonStaging",
    "CanonCommits",
    "BookFrontmatter",
    "LoreDocuments",
    "PersonaIdentity",
    "RAGMetrics",
    "Giveaways",
    "GameStats",
    "Memes",
]
