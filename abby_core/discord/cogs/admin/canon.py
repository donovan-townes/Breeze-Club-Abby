import discord
from discord import app_commands
from discord.ext import commands

from abby_core.personality import canon_service
from abby_core.personality.schema import CanonArtifact, CanonOriginType, CanonStatus, CanonType
from abby_core.observability.logging import logging
from abby_core.discord.config import config

logger = logging.getLogger(__name__)


def _has_role_id(member: discord.Member, role_id: int) -> bool:
    """Check if member has a role by ID."""
    if role_id == 0:
        return False
    return any(role.id == role_id for role in getattr(member, "roles", []))


# Artifact metadata for dropdown options
ARTIFACTS = {
    "book": {
        "Book of the Breeze": {
            "sections": ["front_matter", "chapter", "appendix"],
        }
    },
    "lore": {
        "domains": [
            ("season", "Seasonal themes and cycles"),
            ("world", "World-building and geography"),
            ("location", "Places and settings"),
            ("culture", "Traditions and society"),
            ("concept", "Abstract ideas and themes"),
        ],
        "topics": {
            "season": ["winter", "spring", "summer", "autumn"],
            "world": ["breeze", "lands", "nature"],
            "location": ["gathering_place", "village", "forest"],
            "culture": ["tradition", "ritual", "celebration"],
            "concept": ["quietness", "warmth", "connection"],
        },
    },
    "persona": {
        "Abby": {
            "slots": [
                ("voice", "How Abby sounds and communicates"),
                ("values", "What she prioritizes and cares about"),
                ("boundaries", "What she won't do or discuss"),
                ("worldview", "How she interprets events and meaning"),
                ("narration_style", "How she writes long-form content"),
                ("prohibitions", "Hard stops and never-dos"),
            ],
            "scopes": [
                ("global", "Applies everywhere"),
                ("book", "Book writing context only"),
                ("moderation", "Community moderation context"),
            ],
        },
    },
}


class CanonArtifactNameSelect(discord.ui.Select):
    """Dropdown for selecting artifact name."""
    def __init__(self, canon_type: CanonType):
        self.canon_type = canon_type
        
        # Build options based on canon_type
        options = []
        if canon_type == CanonType.BOOK:
            for book_name in ARTIFACTS["book"].keys():
                options.append(discord.SelectOption(label=book_name, value=book_name))
        elif canon_type == CanonType.LORE:
            options.append(discord.SelectOption(label="World Lore", value="world_lore"))
        elif canon_type == CanonType.PERSONA:
            for persona in ARTIFACTS["persona"].keys():
                options.append(discord.SelectOption(label=persona, value=persona.lower()))
        else:
            options.append(discord.SelectOption(label="General", value="general"))
        
        super().__init__(
            placeholder="Select artifact name...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        artifact_name = self.values[0]
        # Store in view
        view: CanonArtifactFlow = self.view  # type: ignore
        view.artifact_name = artifact_name
        
        # Prevent re-selection of artifact name (avoids duplicate selectors)
        self.disabled = True
        
        # Route based on canon type
        if self.canon_type == CanonType.BOOK:
            # Books need section selector
            view.show_section_selector()
            await interaction.response.edit_message(view=view)
        elif self.canon_type == CanonType.LORE:
            # Lore needs domain selector
            view.show_domain_selector()
            await interaction.response.edit_message(view=view)
        elif self.canon_type == CanonType.PERSONA:
            # Persona needs slot selector
            view.show_persona_slot_selector()
            await interaction.response.edit_message(view=view)
        else:
            # Default: skip to modal
            artifact = CanonArtifact(
                artifact_type=self.canon_type.value,
                name=artifact_name,
            )
            modal = CanonSubmitModal(canon_type=self.canon_type, artifact=artifact)
            await interaction.response.send_modal(modal)


class CanonArtifactSectionSelect(discord.ui.Select):
    """Dropdown for selecting section within artifact."""
    def __init__(self, artifact_name: str):
        options = [
            discord.SelectOption(label="Front Matter", value="front_matter", emoji="📖"),
            discord.SelectOption(label="Chapter", value="chapter", emoji="📄"),
            discord.SelectOption(label="Appendix", value="appendix", emoji="📋"),
        ]
        super().__init__(
            placeholder="Select section...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )
        self.artifact_name = artifact_name

    async def callback(self, interaction: discord.Interaction):
        section = self.values[0]
        view: CanonArtifactFlow = self.view  # type: ignore
        
        # Safety check
        if not view.artifact_name:
            await interaction.response.send_message("❌ No artifact selected.", ephemeral=True)
            return
        
        # Create artifact and show modal
        artifact = CanonArtifact(
            artifact_type=view.canon_type.value,
            name=view.artifact_name,
            section=section,
        )
        modal = CanonSubmitModal(canon_type=view.canon_type, artifact=artifact)
        await interaction.response.send_modal(modal)


class CanonLoreDomainSelect(discord.ui.Select):
    """Dropdown for selecting lore domain."""
    def __init__(self):
        options = [
            discord.SelectOption(label=domain.replace("_", " ").title(), value=domain, description=desc)
            for domain, desc in ARTIFACTS["lore"]["domains"]
        ]
        super().__init__(
            placeholder="Select lore domain...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        domain = self.values[0]
        view: CanonArtifactFlow = self.view  # type: ignore
        view.lore_domain = domain
        
        # Disable this selector
        self.disabled = True
        
        # Show topic selector
        view.show_topic_selector(domain)
        await interaction.response.edit_message(view=view)


class CanonLoreTopicSelect(discord.ui.Select):
    """Dropdown for selecting lore topic within domain."""
    def __init__(self, domain: str):
        topics = ARTIFACTS["lore"]["topics"].get(domain, [])
        options = [
            discord.SelectOption(label=topic.replace("_", " ").title(), value=topic)
            for topic in topics
        ]
        # Add "other" option
        options.append(discord.SelectOption(label="Other (specify in title)", value="other"))
        
        super().__init__(
            placeholder=f"Select {domain} topic...",
            min_values=1,
            max_values=1,
            options=options,
            row=2
        )
        self.domain = domain

    async def callback(self, interaction: discord.Interaction):
        topic = self.values[0]
        view: CanonArtifactFlow = self.view  # type: ignore
        
        # Create artifact and show modal
        artifact = CanonArtifact(
            artifact_type="lore",
            name="Lore",  # Generic name for lore
            domain=view.lore_domain,
            topic=topic if topic != "other" else None,
        )
        modal = CanonSubmitModal(canon_type=CanonType.LORE, artifact=artifact)
        await interaction.response.send_modal(modal)


class CanonPersonaScopeSelect(discord.ui.Select):
    """Dropdown for selecting persona scope."""
    def __init__(self, persona_name: str):
        persona_key = persona_name.title()
        scopes = ARTIFACTS["persona"][persona_key]["scopes"]
        options = [
            discord.SelectOption(label=scope.title(), value=scope, description=desc)
            for scope, desc in scopes
        ]
        
        super().__init__(
            placeholder="Select scope...",
            min_values=1,
            max_values=1,
            options=options,
            row=2
        )
        self.persona_name = persona_key

    async def callback(self, interaction: discord.Interaction):
        scope = self.values[0]
        view: CanonArtifactFlow = self.view  # type: ignore
        
        # Safety check
        if not view.persona_slot:
            await interaction.response.send_message("❌ No persona slot selected.", ephemeral=True)
            return
        
        # Create artifact and show persona-specific modal
        artifact = CanonArtifact(
            artifact_type="persona",
            name=(view.artifact_name.title() if view.artifact_name else self.persona_name),
            topic=view.persona_slot,
            domain=scope,
        )
        # Auto-generate title based on slot + scope
        auto_title = f"Persona · {view.persona_slot.replace('_', ' ').title()} · {scope.title()}"
        modal = PersonaSubmitModal(artifact=artifact, auto_title=auto_title)
        await interaction.response.send_modal(modal)


class CanonPersonaSlotSelect(discord.ui.Select):
    """Dropdown for selecting persona identity slot."""
    def __init__(self, persona_name: str):
        # Capitalize for ARTIFACTS lookup (dropdown uses lowercase value)
        persona_key = persona_name.title()
        slots = ARTIFACTS["persona"][persona_key]["slots"]
        options = [
            discord.SelectOption(label=slot.replace("_", " ").title(), value=slot, description=desc)
            for slot, desc in slots
        ]
        
        super().__init__(
            placeholder="Select identity slot...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )
        # Store capitalized version for artifact creation
        self.persona_name = persona_key

    async def callback(self, interaction: discord.Interaction):
        slot = self.values[0]
        view: CanonArtifactFlow = self.view  # type: ignore
        view.persona_slot = slot
        
        # Disable this selector
        self.disabled = True
        
        # Show scope selector
        view.show_persona_scope_selector()
        await interaction.response.edit_message(view=view)


class CanonArtifactFlow(discord.ui.View):
    """Multi-step artifact selection flow."""
    def __init__(self, canon_type: CanonType):
        super().__init__(timeout=180)
        self.canon_type = canon_type
        self.artifact_name: str | None = None
        self.lore_domain: str | None = None
        self.persona_slot: str | None = None
        
        # Start with appropriate first selector based on type
        if canon_type == CanonType.LORE:
            # Lore doesn't need artifact name, go straight to domain
            self.add_item(CanonLoreDomainSelect())
        else:
            self.add_item(CanonArtifactNameSelect(canon_type))
    
    def show_section_selector(self):
        """Add section selector after book name is chosen."""
        if not self.artifact_name:
            return
        # Avoid adding duplicate section selector
        for child in self.children:
            if isinstance(child, CanonArtifactSectionSelect):
                return
        self.add_item(CanonArtifactSectionSelect(self.artifact_name))
    
    def show_domain_selector(self):
        """Add domain selector for lore."""
        # Avoid adding duplicate
        for child in self.children:
            if isinstance(child, CanonLoreDomainSelect):
                return
        self.add_item(CanonLoreDomainSelect())
    
    def show_topic_selector(self, domain: str):
        """Add topic selector for lore after domain is chosen."""
        # Avoid adding duplicate
        for child in self.children:
            if isinstance(child, CanonLoreTopicSelect):
                return
        self.add_item(CanonLoreTopicSelect(domain))
    
    def show_persona_slot_selector(self):
        """Add slot selector for persona."""
        if not self.artifact_name:
            return
        # Avoid adding duplicate
        for child in self.children:
            if isinstance(child, CanonPersonaSlotSelect):
                return
        self.add_item(CanonPersonaSlotSelect(self.artifact_name))
    
    def show_persona_scope_selector(self):
        """Add scope selector for persona after slot is chosen."""
        if not self.artifact_name:
            return
        # Avoid adding duplicate
        for child in self.children:
            if isinstance(child, CanonPersonaScopeSelect):
                return
        self.add_item(CanonPersonaScopeSelect(self.artifact_name))


class CanonTypeSelect(discord.ui.Select):
    """Dropdown for selecting canon document type."""
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Book",
                value="book",
                description="Book content (chapters, front matter, appendix)",
                emoji="📖"
            ),
            discord.SelectOption(
                label="Lore",
                value="lore",
                description="World-building and narrative lore",
                emoji="🌍"
            ),
            discord.SelectOption(
                label="Persona",
                value="persona",
                description="Core identity and character definition",
                emoji="🎭"
            ),
            discord.SelectOption(
                label="Appendix",
                value="appendix",
                description="Supplementary reference material",
                emoji="📋"
            ),
        ]
        super().__init__(
            placeholder="Select canon document type...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        canon_type = CanonType(self.values[0])
        
        # Show artifact flow
        embed = discord.Embed(
            title=f"📝 Submit {canon_type.value.replace('_', ' ').title()}",
            description="Select the artifact this document belongs to:",
            color=discord.Color.blue(),
        )
        view = CanonArtifactFlow(canon_type=canon_type)
        await interaction.response.edit_message(embed=embed, view=view)


class CanonTypeSelectView(discord.ui.View):
    """View containing the canon type dropdown."""
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(CanonTypeSelect())


class PersonaSubmitModal(discord.ui.Modal, title="Edit Persona Identity"):
    """Persona-specific modal without title field (auto-generated)."""
    def __init__(self, artifact: CanonArtifact, auto_title: str):
        super().__init__()
        self.artifact = artifact
        self.auto_title = auto_title

        self.content_input = discord.ui.TextInput(
            label="Identity Definition",
            placeholder="Define this aspect of Abby's persona...",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=4000,
        )
        
        # Optional part label for multi-part submissions
        self.part_label_input = discord.ui.TextInput(
            label="Part Label (optional)",
            placeholder="e.g., 'Part 1' - for splitting long definitions",
            min_length=1,
            max_length=50,
            required=False,
        )

        self.add_item(self.content_input)
        self.add_item(self.part_label_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            source_ref = {
                "platform": "discord",
                "channel_id": str(interaction.channel_id) if interaction.channel_id else None,
                "message_id": str(interaction.message.id) if interaction.message else None,
                "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
            }

            staged = canon_service.stage_document(
                title=self.auto_title,  # Auto-generated, not user input
                canon_type=CanonType.PERSONA,
                artifact=self.artifact,
                content=str(self.content_input.value),
                part_label=str(self.part_label_input.value).strip() if self.part_label_input.value else None,
                submitted_by=str(interaction.user.id),
                origin_type=CanonOriginType.DISCORD,
                source_ref=source_ref,
            )

            embed = discord.Embed(
                title="✅ Persona identity staged",
                description=f"**{staged['title']}**",
                color=discord.Color.green(),
            )
            embed.add_field(name="Staging ID", value=f"`{staged['_id']}`", inline=False)
            embed.add_field(name="Slot", value=self.artifact.topic or "N/A", inline=True)
            embed.add_field(name="Scope", value=self.artifact.domain or "global", inline=True)
            if staged.get("part_label"):
                embed.add_field(name="Part", value=staged["part_label"], inline=True)
            embed.add_field(name="Canonical ID Preview", value=f"`{staged['target_id_preview']}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as exc:
            logger.error("[CANON] Persona submit failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Failed to stage: {exc}", ephemeral=True)


class CanonSubmitModal(discord.ui.Modal, title="Submit Canon Document"):
    def __init__(self, canon_type: CanonType, artifact: CanonArtifact):
        super().__init__()
        self.canon_type = canon_type
        self.artifact = artifact

        self.title_input = discord.ui.TextInput(
            label="Piece Title",
            placeholder="Reader-facing title (e.g. \"The First Wind\").",
            min_length=3,
            max_length=200,
        )
        
        # Optional part label for multi-part submissions
        self.part_label_input = discord.ui.TextInput(
            label="Part Label (optional)",
            placeholder="e.g., 'Part 1', '1/3', 'Section A' - for splitting long content",
            min_length=1,
            max_length=50,
            required=False,
        )
        
        # Show chapter/entry field only for books with sections
        if canon_type == CanonType.BOOK and artifact.section:
            self.chapter_input = discord.ui.TextInput(
                label="Chapter / Entry",
                placeholder="Internal identifier (e.g. prologue, chapter_1). This does not need to be poetic.",
                min_length=1,
                max_length=100,
                required=False,
            )
            self.add_item(self.chapter_input)
        else:
            self.chapter_input = None
        
        self.content_input = discord.ui.TextInput(
            label="Content",
            placeholder="Paste markdown/plaintext...",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=4000,  # Discord modal limit
        )

        self.add_item(self.title_input)
        self.add_item(self.part_label_input)
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # Update artifact with chapter if provided
            artifact = self.artifact
            if self.chapter_input and self.chapter_input.value:
                artifact.chapter = str(self.chapter_input.value).strip()
            
            source_ref = {
                "platform": "discord",
                "channel_id": str(interaction.channel_id) if interaction.channel_id else None,
                "message_id": str(interaction.message.id) if interaction.message else None,
                "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
            }

            staged = canon_service.stage_document(
                title=str(self.title_input.value),
                canon_type=self.canon_type,
                artifact=artifact,
                content=str(self.content_input.value),
                part_label=str(self.part_label_input.value).strip() if self.part_label_input.value else None,
                submitted_by=str(interaction.user.id),
                origin_type=CanonOriginType.DISCORD,
                source_ref=source_ref,
            )

            embed = discord.Embed(
                title="✅ Canon submission staged",
                description=f"**{staged['title']}**",
                color=discord.Color.green(),
            )
            embed.add_field(name="Staging ID", value=f"`{staged['_id']}`", inline=False)
            embed.add_field(name="Type", value=self.canon_type.value, inline=True)
            embed.add_field(name="Artifact", value=artifact.name, inline=True)
            if staged.get("part_label"):
                embed.add_field(name="Part", value=staged["part_label"], inline=True)
            embed.add_field(name="Canonical ID Preview", value=f"`{staged['target_id_preview']}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as exc:
            logger.error("[CANON] Submit failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Failed to stage: {exc}", ephemeral=True)


class CanonReviewButton(discord.ui.Button):
    """Button for viewing a staged document."""
    def __init__(self, staging_id: str, title: str, row: int = 0):
        super().__init__(
            label=f"View: {title[:30]}...",
            style=discord.ButtonStyle.primary,
            row=row
        )
        self.staging_id = staging_id

    async def callback(self, interaction: discord.Interaction):
        from typing import cast, Any
        cog = cast(Any, cast(commands.Bot, interaction.client).get_cog("CanonCommands"))
        if not cog:
            await interaction.response.send_message("❌ Canon system unavailable.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        doc = canon_service.get_staging_document(self.staging_id)
        if not doc:
            await interaction.followup.send("❌ Document not found.", ephemeral=True)
            return
        
        # Show full content in embed
        content = doc.get("content", "")
        # Discord embed description limit is 4096
        if len(content) > 3800:
            content = content[:3800] + "\n\n... *(truncated)*"
        
        embed = discord.Embed(
            title=f"📄 {doc['title']}",
            description=content,
            color=discord.Color.teal(),
        )
        embed.add_field(name="Type", value=doc['canon_type'], inline=True)
        embed.add_field(name="Status", value=doc.get("status"), inline=True)
        embed.add_field(name="Submitted", value=str(doc.get("submitted_at"))[:19], inline=True)
        
        # Show part label if present
        if doc.get("part_label"):
            embed.add_field(name="Part", value=doc["part_label"], inline=True)
        
        # Show artifact metadata if present
        if "artifact" in doc:
            artifact = doc["artifact"]
            artifact_parts = [artifact.get("name", "N/A")]
            if artifact.get("section"):
                artifact_parts.append(f"→ {artifact['section']}")
            if artifact.get("chapter"):
                artifact_parts.append(f"→ {artifact['chapter']}")
            embed.add_field(name="Artifact", value=" ".join(artifact_parts), inline=False)
        
        embed.add_field(name="Staging ID", value=f"`{doc.get('_id')}`", inline=False)
        embed.add_field(name="Target ID Preview", value=f"`{doc.get('target_id_preview', 'N/A')}`", inline=False)
        embed.set_footer(text="⚠️ Review carefully before approving. Canonization is permanent.")
        
        view = CanonApprovalView(self.staging_id, cog)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class CanonReviewListView(discord.ui.View):
    """View showing list of staged documents with view buttons."""
    def __init__(self, staged_docs: list):
        super().__init__(timeout=300)
        # Add up to 5 buttons per row, max 25 buttons total (Discord limit)
        for idx, doc in enumerate(staged_docs[:25]):
            row = idx // 5
            btn = CanonReviewButton(
                staging_id=doc["_id"],
                title=doc["title"],
                row=row
            )
            self.add_item(btn)


class ConfirmApprovalView(discord.ui.View):
    """Confirmation dialog for canon approval."""
    def __init__(self, staging_id: str, cog: "CanonCommands"):
        super().__init__(timeout=60)
        self.staging_id = staging_id
        self.cog = cog

    @discord.ui.button(label="✅ Confirm Canonization", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = self.cog._approve_staged(self.staging_id, interaction.user.id)
            embed = discord.Embed(
                title="✅ Canonized",
                description=f"**{result['canonical_id']}** v{result['version']}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Collection", value=result['canonical_collection'], inline=True)
            embed.add_field(name="Checksum", value=f"`{result['checksum'][:16]}...`", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
            # Disable all buttons after approval
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True  # type: ignore[attr-defined]
            # Try to edit original message to disable buttons, but don't fail if message is gone
            try:
                if interaction.message:
                    await interaction.message.edit(view=self)
            except discord.NotFound:
                pass  # Message already deleted or ephemeral message expired
        except Exception as exc:
            logger.error("[CANON] Approval failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Approval failed: {exc}", ephemeral=True)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Approval cancelled.", ephemeral=True)
        # Disable all buttons
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True  # type: ignore[attr-defined]
        # Try to edit original message to disable buttons, but don't fail if message is gone
        try:
            if interaction.message:
                await interaction.message.edit(view=self)
        except discord.NotFound:
            pass  # Message already deleted or ephemeral message expired


class CanonApprovalView(discord.ui.View):
    """View with Approve/Reject/Back buttons after viewing document."""
    def __init__(self, staging_id: str, cog: "CanonCommands"):
        super().__init__(timeout=300)
        self.staging_id = staging_id
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.cog._is_canon_editor(interaction.user):
            await interaction.response.send_message("❌ CANON_EDITOR role required.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, row=0)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show confirmation dialog
        doc = canon_service.get_staging_document(self.staging_id)
        if not doc:
            await interaction.response.send_message("❌ Document not found.", ephemeral=True)
            return
        
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Canonization",
            description=(
                f"**{doc['title']}** ({doc['canon_type']})\n\n"
                "This will permanently canonize this document.\n"
                "This action cannot be undone without creating a new revision.\n\n"
                "Are you sure you want to proceed?"
            ),
            color=discord.Color.orange(),
        )
        confirm_view = ConfirmApprovalView(self.staging_id, self.cog)
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="🛑 Reject", style=discord.ButtonStyle.danger, row=0)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            canon_service.reject_document(self.staging_id, str(interaction.user.id))
            embed = discord.Embed(
                title="🛑 Document Rejected",
                description=f"Staging ID: `{self.staging_id}`",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            # Disable all buttons after rejection
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True  # type: ignore[attr-defined]
            # Try to edit original message to disable buttons, but don't fail if message is gone
            try:
                if interaction.message:
                    await interaction.message.edit(view=self)
            except discord.NotFound:
                pass  # Message already deleted or ephemeral message expired
        except Exception as exc:
            logger.error("[CANON] Rejection failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Rejection failed: {exc}", ephemeral=True)

    @discord.ui.button(label="◀️ Back to Queue", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Re-fetch queue and show
        staged = canon_service.list_staged_documents(
            statuses=[CanonStatus.STAGED, CanonStatus.REVIEWED],
            limit=10,
        )
        if not staged:
            await interaction.followup.send("📭 Review queue is now empty.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📑 Canon Review Queue",
            description=f"Found {len(staged)} document(s) pending review.\nClick a button below to view details.",
            color=discord.Color.blurple(),
        )
        for doc in staged:
            embed.add_field(
                name=f"{doc['title']} ({doc['canon_type']})",
                value=(
                    f"**ID:** `{doc['_id']}`\n"
                    f"**Status:** {doc['status']}\n"
                    f"**By:** <@{doc.get('submitted_by')}>"
                ),
                inline=False,
            )
        view = CanonReviewListView(staged)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class CanonCommands(commands.Cog):
    """Canon staging and approval commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_canon_editor(self, user: discord.abc.User) -> bool:
        if isinstance(user, discord.Member):
            return _has_role_id(user, config.roles.canon_editor) or user.guild_permissions.administrator
        return False

    def _can_submit(self, user: discord.abc.User) -> bool:
        if isinstance(user, discord.Member):
            if _has_role_id(user, config.roles.canon_editor) or user.guild_permissions.administrator:
                return True
            return _has_role_id(user, config.roles.trusted_contributor)
        return False

    def _approve_staged(self, staging_id: str, approver_id: int):
        return canon_service.approve_document(staging_id, str(approver_id))

    @app_commands.command(name="canon", description="Canon document staging and approval system")
    @app_commands.describe(action="Choose an action")
    @app_commands.choices(action=[
        app_commands.Choice(name="submit", value="submit"),
        app_commands.Choice(name="review", value="review"),
    ])
    async def canon_command(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
    ):
        """Canon staging system with fully interactive UI (no typing required)."""
        
        if action.value == "submit":
            if not self._can_submit(interaction.user):
                await interaction.response.send_message(
                    "❌ You lack permission to submit canon documents.\n"
                    "Required role: TRUSTED_CONTRIBUTOR or CANON_EDITOR",
                    ephemeral=True
                )
                return
            
            # Show type selection dropdown
            view = CanonTypeSelectView()
            embed = discord.Embed(
                title="📝 Submit Canon Document",
                description="Select the type of document you want to submit:",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        if action.value == "review":
            if not self._is_canon_editor(interaction.user):
                await interaction.response.send_message(
                    "❌ CANON_EDITOR role required to review documents.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True, thinking=True)
            staged = canon_service.list_staged_documents(
                statuses=[CanonStatus.STAGED, CanonStatus.REVIEWED],
                limit=10,
            )
            
            if not staged:
                await interaction.followup.send("📭 No documents in the review queue.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📑 Canon Review Queue",
                description=f"Found {len(staged)} document(s) pending review.\nClick a button below to view details.",
                color=discord.Color.blurple(),
            )
            
            for doc in staged:
                embed.add_field(
                    name=f"{doc['title']} ({doc['canon_type']})",
                    value=(
                        f"**ID:** `{doc['_id']}`\n"
                        f"**Status:** {doc['status']}\n"
                        f"**By:** <@{doc.get('submitted_by')}>"
                    ),
                    inline=False,
                )
            
            view = CanonReviewListView(staged)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(CanonCommands(bot))
