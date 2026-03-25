"""Adapter interfaces for abby_core subsystems.

Defines contracts that all platform-specific adapters must implement.
Ensures consistent functionality across Discord, Web, CLI, and other platforms.
"""

from .economy import (
    IEconomyService,
    IXPService,
    IEconomyAdapter,
    Balance,
    Transaction,
    UserXP,
    UserSummary,
    EconomyAdapterFactory,
)

__all__ = [
    "IEconomyService",
    "IXPService",
    "IEconomyAdapter",
    "Balance",
    "Transaction",
    "UserXP",
    "UserSummary",
    "EconomyAdapterFactory",
]
