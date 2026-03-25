import sys
from pathlib import Path
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

# Use Abby RAG adapter instead of direct TDOS imports
from abby_core.adapters import get_rag_adapter, RAGContext
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)

# Document types (canonical identifiers) - What kind of artifact is this?
DOC_TYPES = [
    "guidelines",         # Norms, expectations, conduct
    "policy",             # Enforcement, consequences, authority
    "faq",                # Q&A style reference
    "documentation",      # How-to, systems, features, tips
    "weekly_summary",     # Time-based recap
    "artist_bio",         # Profile / identity
    "submission_rules",   # Intake processes
    "other"
]

# Scope - Where or when is this used? (Runtime retrieval context)
SCOPES = [
    "community",          # Social behavior, culture, conduct
    "rules",              # Enforcement-adjacent, authoritative
    "submissions",        # Intake, demos, applications
    "documentation",      # Feature usage, commands
    "recap",              # Summaries, ambient info
    "other"
]


class RAGIngestModal(discord.ui.Modal, title="Ingest RAG Document"):
    """Modal for clean RAG document ingestion with structured fields."""
    
    doc_title = discord.ui.TextInput(
        label="Document Title",
        placeholder="e.g., Breeze Club Guidelines, Label Submission Rules",
        required=True,
        max_length=200
    )
    
    doc_body = discord.ui.TextInput(
        label="Content (paste your text here)",
        placeholder="Paste your document text here. It will be automatically cleaned and formatted.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )
    
    doc_tags = discord.ui.TextInput(
        label="Tags (comma-separated, optional)",
        placeholder="e.g., rules, important, community",
        required=False,
        max_length=200,
        style=discord.TextStyle.short
    )
    
    # Store document_type and scope to pass to callback
    document_type: str = "other"
    scope: str = "other"
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            guild_id = str(interaction.guild_id or "")
            user_id = str(interaction.user.id)
            
            # Parse tags
            tags = []
            if self.doc_tags.value:
                tags = [t.strip() for t in self.doc_tags.value.split(",") if t.strip()]
            
            # Create RAG context
            rag = get_rag_adapter()
            context = RAGContext(
                guild_id=guild_id,
                user_id=user_id,
                is_premium=False  # TODO: Check premium status
            )
            
            # Prepare metadata
            metadata = {
                "tags": tags,
                "scope": self.scope,
                "version": 1
            }
            
            # Ingest document via adapter
            result = await rag.ingest_document(
                content=self.doc_body.value,
                title=self.doc_title.value.strip(),
                context=context,
                document_type=self.document_type,
                metadata=metadata
            )
            
            # Check success
            if not result.get("success"):
                error_embed = discord.Embed(
                    title="❌ Ingestion Failed",
                    description=f"```{result.get('error', 'Unknown error')[:500]}```",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Success embed
            embed = discord.Embed(
                title="✅ Document Ingested",
                description=f"**{self.doc_title.value}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Document ID", value=f"`{result.get('document_id', 'N/A')}`", inline=False)
            embed.add_field(name="Type", value=self.document_type, inline=True)
            embed.add_field(name="Scope", value=self.scope, inline=True)
            embed.add_field(name="Chunks", value=str(result.get('chunks_created', 0)), inline=True)
            
            if tags:
                embed.add_field(name="Tags", value=", ".join(tags), inline=False)
            embed.set_footer(text=f"Guild: {guild_id or 'Global'}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as exc:
            logger.error("[RAG] Ingest failed: %s", exc, exc_info=True)
            
            error_embed = discord.Embed(
                title="❌ Ingestion Failed",
                description=f"```{str(exc)[:500]}```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)


class RAGAdmin(commands.Cog):
    """
    RAG document management for Discord.
    
    Commands:
        /rag ingest  - Ingest document with source/scope selection
        /rag list    - List documents in current guild
        /rag delete  - Delete documents by title or source
        /rag query   - Test RAG retrieval
        /rag stats   - Show corpus stats
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("[RAG] RAG admin commands ready")

    @app_commands.command(name="rag", description="RAG document management")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        action="Action to perform",
        query="Search query (for query action) or Document ID (for delete action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="ingest", value="ingest"),
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="delete", value="delete"),
        app_commands.Choice(name="query", value="query"),
        app_commands.Choice(name="stats", value="stats"),
    ])
    async def rag_command(
        self, 
        interaction: discord.Interaction, 
        action: app_commands.Choice[str],
        query: Optional[str] = None
    ):
        """Unified RAG management command."""
        
        if action.value == "ingest":
            # Ingest always uses the multi-step modal UI
            await self._ingest_flow(interaction)
            return
        
        elif action.value == "list":
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                guild_id = str(interaction.guild_id or "")
                user_id = str(interaction.user.id)
                
                # Create RAG context and adapter
                rag = get_rag_adapter()
                context = RAGContext(
                    guild_id=guild_id,
                    user_id=user_id,
                    is_premium=False
                )
                
                # List documents via adapter
                docs = await rag.list_documents(context, limit=25)
                
                if not docs:
                    await interaction.followup.send("📭 No documents found.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="📚 RAG Documents",
                    description=f"Found {len(docs)} document(s)",
                    color=discord.Color.blue()
                )
                
                for doc in docs[:10]:
                    value = (
                        f"**ID:** `{doc['document_id']}`\n"
                        f"**Type:** {doc['document_type']}\n"
                        f"**Scope:** {doc['scope']}\n"
                        f"**Chunks:** {doc['chunk_count']}\n"
                        f"**Version:** v{doc['version']}"
                    )
                    if doc.get('tags'):
                        value += f"\n**Tags:** {', '.join(doc['tags'])}"
                    
                    embed.add_field(
                        name=doc['title'],
                        value=value,
                        inline=False
                    )
                
                if len(docs) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(docs)} documents")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as exc:
                logger.error("[RAG] List failed: %s", exc, exc_info=True)
                await interaction.followup.send(f"❌ Failed: {exc}", ephemeral=True)
        
        elif action.value == "delete":
            if not query:
                await interaction.response.send_message(
                    "❌ Must provide `query` parameter with document ID to delete.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                guild_id = str(interaction.guild_id or "")
                user_id = str(interaction.user.id)
                
                # Create RAG context and adapter
                rag = get_rag_adapter()
                context = RAGContext(
                    guild_id=guild_id,
                    user_id=user_id,
                    is_premium=False
                )
                
                # Delete document via adapter (includes ownership check)
                result = await rag.delete_document(
                    document_id=query,  # query param = document_id for delete
                    context=context
                )
                
                if not result.get("success"):
                    await interaction.followup.send(
                        f"❌ Delete failed: {result.get('error', 'Unknown error')}",
                        ephemeral=True
                    )
                    return
                
                embed = discord.Embed(
                    title="🗑️ Document Deleted",
                    description=f"Successfully deleted `{query}`",
                    color=discord.Color.orange()
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as exc:
                logger.error("[RAG] Delete failed: %s", exc, exc_info=True)
                await interaction.followup.send(f"❌ Failed: {exc}", ephemeral=True)
        
        elif action.value == "query":
            if not query:
                await interaction.response.send_message(
                    "❌ Must provide `query` parameter with search text.\n\n**Example:** `/rag query what are the conduct rules?`",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                guild_id = str(interaction.guild_id or "")
                user_id = str(interaction.user.id)
                
                # Create RAG context and adapter
                rag = get_rag_adapter()
                context = RAGContext(
                    guild_id=guild_id,
                    user_id=user_id,
                    is_premium=False
                )
                
                # Query via adapter (automatic guild isolation)
                result = await rag.query(
                    query=query,
                    context=context,
                    top_k=5
                )
                
                embed = discord.Embed(
                    title="🔍 RAG Query Results",
                    description=f"Query: *{query[:100]}*",
                    color=discord.Color.purple()
                )
                
                # RAGResult has .results attribute
                results = result.results if hasattr(result, 'results') else []
                if not results:
                    embed.add_field(name="No Matches", value="Try different search terms.", inline=False)
                else:
                    for idx, item in enumerate(results[:5], 1):
                        # Get text content from result
                        text_content = item.get("text", "") or item.get("content", "")
                        snippet = text_content[:200] if text_content else "(empty)"
                        meta = item.get("metadata", {})
                        
                        if not meta:
                            continue
                        
                        doc_id = meta.get("document_id", "Unknown")
                        doc_type = meta.get("document_type", "unknown")
                        chunk_index = meta.get("chunk_index", "?")
                        
                        embed.add_field(
                            name=f"{idx}. {doc_id}",
                            value=f"*{doc_type} | chunk {chunk_index}*\n{snippet}...",
                            inline=False
                        )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as exc:
                logger.error("[RAG] Query failed: %s", exc, exc_info=True)
                await interaction.followup.send(f"❌ Failed: {exc}", ephemeral=True)
        
        elif action.value == "stats":
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                from abby_core.database.mongodb import get_rag_documents_collection
                col = get_rag_documents_collection()
                
                guild_id = str(interaction.guild_id or "")
                
                total = col.count_documents({})
                guild_count = col.count_documents({"guild_id": guild_id}) if guild_id else 0
                
                # Count unique document_ids
                pipeline = [
                    {"$group": {"_id": "$document_id"}},
                    {"$count": "total"}
                ]
                unique_result = list(col.aggregate(pipeline))
                unique_docs = unique_result[0]["total"] if unique_result else 0
                
                embed = discord.Embed(
                    title="📊 RAG Corpus Stats",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Total Chunks", value=str(total), inline=True)
                embed.add_field(name="Unique Documents", value=str(unique_docs), inline=True)
                if guild_id:
                    embed.add_field(name="This Guild Chunks", value=str(guild_count), inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as exc:
                logger.error("[RAG] Stats failed: %s", exc, exc_info=True)
                await interaction.followup.send(f"❌ Failed: {exc}", ephemeral=True)
    
    async def _ingest_flow(self, interaction: discord.Interaction):
        """Multi-step ingest flow with document type and scope selection."""
        
        # Step 1: Select document type
        type_select = discord.ui.Select(
            placeholder="Select document type...",
            options=[
                discord.SelectOption(label="Guidelines", value="guidelines", description="Norms, expectations, conduct"),
                discord.SelectOption(label="Policy", value="policy", description="Enforcement, consequences, authority"),
                discord.SelectOption(label="FAQ", value="faq", description="Q&A style reference"),
                discord.SelectOption(label="Documentation", value="documentation", description="How-to, features, tips"),
                discord.SelectOption(label="Weekly Summary", value="weekly_summary", description="Time-based recap"),
                discord.SelectOption(label="Artist Bio", value="artist_bio", description="Biographies / profiles"),
                discord.SelectOption(label="Submission Rules", value="submission_rules", description="Intake processes"),
                discord.SelectOption(label="Other", value="other", description="Other document type"),
            ],
            min_values=1,
            max_values=1
        )
        
        # Cancel button for step 1
        cancel_button_1 = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        
        async def cancel_callback_1(interaction: discord.Interaction):
            await interaction.response.edit_message(content="❌ RAG ingest cancelled.", view=None, embed=None)
        
        cancel_button_1.callback = cancel_callback_1
        
        async def type_callback(interaction: discord.Interaction):
            selected_type = type_select.values[0]
            
            # Step 2: Select scope (with document type shown)
            scope_select = discord.ui.Select(
                placeholder="Select document scope...",
                options=[
                    discord.SelectOption(label="Community", value="community", description="Social behavior, culture, conduct"),
                    discord.SelectOption(label="Rules", value="rules", description="Enforcement-adjacent, authoritative"),
                    discord.SelectOption(label="Submissions", value="submissions", description="Intake, demos, applications"),
                    discord.SelectOption(label="Documentation", value="documentation", description="Feature usage, commands"),
                    discord.SelectOption(label="Recap", value="recap", description="Summaries, ambient info"),
                    discord.SelectOption(label="Other", value="other", description="Other scope"),
                ],
                min_values=1,
                max_values=1
            )
            
            # Cancel button for step 2
            cancel_button_2 = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            
            async def cancel_callback_2(interaction: discord.Interaction):
                await interaction.response.edit_message(content="❌ RAG ingest cancelled.", view=None, embed=None)
            
            cancel_button_2.callback = cancel_callback_2
            
            async def scope_callback(interaction: discord.Interaction):
                selected_scope = scope_select.values[0]
                
                # Create modal with pre-filled document_type/scope
                modal = RAGIngestModal()
                modal.document_type = selected_type
                modal.scope = selected_scope
                
                # Send modal directly (must be the first response action)
                await interaction.response.send_modal(modal)
                
                # Can't edit message after sending modal, so we'll update it in the modal's on_submit
            
            scope_select.callback = scope_callback
            scope_view = discord.ui.View()
            scope_view.add_item(scope_select)
            scope_view.add_item(cancel_button_2)
            
            # Edit the same message to show step 2
            await interaction.response.edit_message(
                content=f"**RAG Document Ingest**\n\n**Document Type:** {selected_type}\n\nStep 2: Select the document scope:",
                view=scope_view
            )
        
        type_select.callback = type_callback
        type_view = discord.ui.View()
        type_view.add_item(type_select)
        type_view.add_item(cancel_button_1)
        
        await interaction.response.send_message(
            "**RAG Document Ingest**\n\nStep 1: Select the document type:",
            view=type_view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RAGAdmin(bot))


