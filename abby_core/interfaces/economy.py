"""
Adapter Interfaces for Economy Subsystem

Defines contracts that all economy adapters (Discord, Web, CLI, etc.) must implement.
This ensures consistent functionality across platforms while allowing platform-specific UI.

Interfaces cover:
- IEconomyService: Core banking/wallet operations
- IXPService: Experience and leveling operations
- IEconomyAdapter: Full adapter contract combining both services
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Balance:
    """User balance representation."""
    wallet: int
    bank: int
    total: int
    
    def __post_init__(self):
        if self.total != (self.wallet + self.bank):
            raise ValueError("Total must equal wallet + bank")


@dataclass
class Transaction:
    """Financial transaction record."""
    user_id: str
    amount: int
    transaction_type: str  # 'deposit', 'withdraw', 'interest', 'tip'
    timestamp: str
    guild_id: Optional[str] = None
    recipient_id: Optional[str] = None
    description: Optional[str] = None


@dataclass
class UserXP:
    """User experience and leveling info."""
    user_id: str
    xp: int
    level: int
    xp_for_next_level: int  # XP needed to reach next level
    progress_percentage: float  # 0.0-100.0


@dataclass
class UserSummary:
    """Complete user economy summary."""
    user_id: str
    guild_id: str
    balance: Balance
    xp_info: UserXP
    level_up_message: Optional[str] = None


# ============================================================================
# ECONOMY SERVICE INTERFACE
# ============================================================================

class IEconomyService(ABC):
    """
    Core economy service contract.
    
    All adapters must implement these methods to provide banking functionality.
    The service handles business logic independent of platform.
    """

    @abstractmethod
    def get_balance(self, user_id: str, guild_id: str) -> Balance:
        """
        Get user balance.
        
        Args:
            user_id: Discord user ID or equivalent user identifier
            guild_id: Guild/server ID where balance applies
            
        Returns:
            Balance object with wallet, bank, and total
            
        Raises:
            ValueError: If user_id or guild_id is invalid
        """
        pass

    @abstractmethod
    def update_balance(
        self,
        user_id: str,
        wallet_amount: Optional[int] = None,
        bank_amount: Optional[int] = None,
        guild_id: Optional[str] = None,
    ) -> Balance:
        """
        Update user balance.
        
        Args:
            user_id: User identifier
            wallet_amount: New wallet amount (if provided)
            bank_amount: New bank amount (if provided)
            guild_id: Guild ID (optional if using default)
            
        Returns:
            Updated Balance object
            
        Raises:
            ValueError: If amounts are negative or invalid
        """
        pass

    @abstractmethod
    def deposit(
        self,
        user_id: str,
        amount: int,
        guild_id: str,
        description: Optional[str] = None,
    ) -> Balance:
        """
        Deposit from wallet to bank.
        
        Args:
            user_id: User making deposit
            amount: Amount to deposit
            guild_id: Guild context
            description: Optional transaction description
            
        Returns:
            Updated Balance object
            
        Raises:
            ValueError: If amount is invalid or wallet has insufficient funds
        """
        pass

    @abstractmethod
    def withdraw(
        self,
        user_id: str,
        amount: int,
        guild_id: str,
        description: Optional[str] = None,
    ) -> Balance:
        """
        Withdraw from bank to wallet.
        
        Args:
            user_id: User making withdrawal
            amount: Amount to withdraw
            guild_id: Guild context
            description: Optional transaction description
            
        Returns:
            Updated Balance object
            
        Raises:
            ValueError: If amount is invalid or bank has insufficient funds
        """
        pass

    @abstractmethod
    def tip(
        self,
        sender_id: str,
        recipient_id: str,
        amount: int,
        guild_id: str,
    ) -> Dict[str, Balance]:
        """
        Transfer funds from sender's wallet to recipient's wallet.
        
        Args:
            sender_id: User sending tip
            recipient_id: User receiving tip
            amount: Amount to tip
            guild_id: Guild context
            
        Returns:
            Dictionary with 'sender' and 'recipient' Balance objects
            
        Raises:
            ValueError: If amount is invalid, users are same, or insufficient funds
        """
        pass

    @abstractmethod
    def calculate_interest(self, balance: int) -> int:
        """
        Calculate interest for a bank balance.
        
        Formula: interest = balance * daily_rate, prorated by time interval
        
        Args:
            balance: Current bank balance
            
        Returns:
            Interest amount (rounded to int)
        """
        pass

    @abstractmethod
    def apply_interest(self, user_id: str, guild_id: str) -> Balance:
        """
        Apply daily interest to user's bank balance.
        
        Args:
            user_id: User receiving interest
            guild_id: Guild context
            
        Returns:
            Updated Balance object with interest applied
        """
        pass

    @abstractmethod
    def process_interest_cycle(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process interest cycle for all users in guild.
        
        Args:
            guild_id: Process only this guild (if None, process all)
            
        Returns:
            Statistics dict: {
                'users_processed': int,
                'total_interest_distributed': int,
                'timestamp': str,
                'guild_id': str or None
            }
        """
        pass

    @abstractmethod
    def check_daily_cooldown(self, user_id: str) -> bool:
        """
        Check if user's daily interest claim is ready.
        
        Args:
            user_id: User to check
            
        Returns:
            True if user has not claimed today, False if on cooldown
        """
        pass

    @abstractmethod
    def list_economies(self, guild_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all active economies.
        
        Args:
            guild_id: Filter by guild (if None, list all)
            
        Returns:
            List of economy info dicts
        """
        pass


# ============================================================================
# XP SERVICE INTERFACE
# ============================================================================

class IXPService(ABC):
    """
    XP and leveling service contract.
    
    All adapters must implement these methods to provide leveling functionality.
    """

    @abstractmethod
    def get_xp(self, user_id: str, guild_id: Optional[str] = None) -> UserXP:
        """
        Get user XP info.
        
        Args:
            user_id: User identifier
            guild_id: Optional guild context
            
        Returns:
            UserXP object with xp, level, and progress info
        """
        pass

    @abstractmethod
    def increment_xp(
        self,
        user_id: str,
        amount: int,
        guild_id: Optional[str] = None,
    ) -> UserXP:
        """
        Increment user XP.
        
        Args:
            user_id: User gaining XP
            amount: XP to add
            guild_id: Optional guild context
            
        Returns:
            Updated UserXP object
            
        Raises:
            ValueError: If amount is negative
        """
        pass

    @abstractmethod
    def get_level(self, user_id: str, guild_id: Optional[str] = None) -> int:
        """
        Get user's current level.
        
        Args:
            user_id: User identifier
            guild_id: Optional guild context
            
        Returns:
            Current level
        """
        pass


# ============================================================================
# COMBINED ADAPTER INTERFACE
# ============================================================================

class IEconomyAdapter(IEconomyService, IXPService):
    """
    Complete economy adapter contract.
    
    Combines IEconomyService and IXPService.
    Adapters must implement all methods from both interfaces.
    
    Usage Pattern:
    ```python
    class DiscordEconomyAdapter(IEconomyAdapter):
        def __init__(self):
            self.banking = BankingService()
            self.xp = XPService()
            
        def get_balance(self, user_id: str, guild_id: str) -> Balance:
            return self.banking.get_balance(user_id, guild_id)
            
        def get_xp(self, user_id: str, guild_id: Optional[str] = None) -> UserXP:
            return self.xp.get_xp(user_id, guild_id)
        
        # ... implement all other methods ...
    ```
    """
    
    @abstractmethod
    def get_user_summary(self, user_id: str, guild_id: str) -> UserSummary:
        """
        Get complete user economy summary.
        
        Args:
            user_id: User identifier
            guild_id: Guild context
            
        Returns:
            UserSummary with balance, XP, level info
        """
        pass


# ============================================================================
# ADAPTER FACTORY
# ============================================================================

class EconomyAdapterFactory:
    """
    Factory for creating economy adapters.
    
    Usage:
    ```python
    from abby_core.interfaces.economy import EconomyAdapterFactory
    from abby_core.economy import BankingService
    from abby_core.economy import get_xp, get_level, increment_xp
    
    adapter = EconomyAdapterFactory.create_core_adapter()
    balance = adapter.get_balance(user_id="123", guild_id="456")
    ```
    """
    
    _adapters = {}
    
    @classmethod
    def register(cls, name: str, adapter_class):
        """Register an adapter implementation."""
        cls._adapters[name] = adapter_class
    
    @classmethod
    def get(cls, name: str = "core") -> IEconomyAdapter:
        """Get registered adapter."""
        if name not in cls._adapters:
            raise ValueError(f"Adapter '{name}' not registered")
        return cls._adapters[name]()
    
    @classmethod
    def list_adapters(cls) -> List[str]:
        """List all registered adapters."""
        return list(cls._adapters.keys())
