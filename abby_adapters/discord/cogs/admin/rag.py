import sys
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands

# Core modules already on path via launch.py
from abby_core.rag import ingest as rag_ingest, query as rag_query
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


class RAGAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[RAG] RAG admin commands loaded")

    @app_commands.command(name="rag_ingest", description="Owner: Ingest text into RAG corpus")
    @app_commands.default_permissions(administrator=True)
    async def rag_ingest(self, interaction: discord.Interaction, source: str, title: str, text: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            guild_id = str(interaction.guild_id) if interaction.guild_id else None
            result = rag_ingest(
                source=source,
                title=title,
                text=text,
                user_id=None,  # None = global/guild-wide
                guild_id=guild_id,
                tags=[source]
            )
            await interaction.followup.send(f"Ingested {result['ingested_chunks']} chunks.", ephemeral=True)
        except Exception as exc:
            logger.error("[RAG] Ingest failed: %s", exc)
            await interaction.followup.send("Ingest failed. Check logs for details.", ephemeral=True)

    @app_commands.command(name="rag_query", description="Owner: Query RAG corpus")
    @app_commands.default_permissions(administrator=True)
    async def rag_query(self, interaction: discord.Interaction, text: str, top_k: int = 3):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            guild_id = str(interaction.guild_id) if interaction.guild_id else None
            result = rag_query(
                text=text,
                user_id=None,  # None = search guild-wide
                guild_id=guild_id,
                top_k=top_k
            )
            lines = []
            for item in result.get("results", []):
                snippet = item.get("text", "")
                meta = item.get("metadata", {})
                title = meta.get("title", "")
                source = meta.get("source", "")
                lines.append(f"**{title}** [{source}] {snippet[:200]}...")
            content = "\n".join(lines) if lines else "No matches."
            await interaction.followup.send(content, ephemeral=True)
        except Exception as exc:
            logger.error("[RAG] Query failed: %s", exc)
            await interaction.followup.send("Query failed. Check logs for details.", ephemeral=True)

    @app_commands.command(name="rag_stats", description="Owner: Show RAG corpus stats")
    @app_commands.default_permissions(administrator=True)
    async def rag_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            # Basic count from Mongo rag_documents
            from abby_core.database.mongodb import get_rag_documents_collection  # late import to avoid circular
            col = get_rag_documents_collection()
            count = col.count_documents({})
            await interaction.followup.send(f"RAG documents: {count}", ephemeral=True)
        except Exception as exc:
            logger.error("[RAG] Stats failed: %s", exc)
            await interaction.followup.send("Stats failed. Check logs for details.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RAGAdmin(bot))
