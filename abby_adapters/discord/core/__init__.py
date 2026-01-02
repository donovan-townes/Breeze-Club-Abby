"""
Core infrastructure components for the Discord bot.

This module contains essential bot infrastructure that supports
the overall functionality and doesn't fit into feature-specific cogs.

Components:
- loader: Dynamic cog and command discovery/loading system
- (api: External API routing - currently disabled, kept for reference)
"""

from .loader import CommandHandler

__all__ = ["CommandHandler"]
