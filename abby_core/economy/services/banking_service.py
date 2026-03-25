"""Banking service - platform-agnostic banking logic.

This module provides all banking operations (balance queries, interest calculations,
transactions) without any Discord dependencies. It can be used by any adapter 
(Discord cog, web API, CLI, etc.)

Pure service layer with no platform-specific imports.
"""

import os
import datetime
from typing import Dict, Any, Optional
from abby_core.database.mongodb import (
    get_economy,
    update_balance,
    list_economies,
    log_transaction,
)
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

# Interest configuration
INTEREST_RATE_DAILY = float(os.getenv("BANK_INTEREST_RATE_DAILY", "0.001"))  # 0.1% daily default
INTEREST_MIN_BALANCE = int(os.getenv("BANK_INTEREST_MIN_BALANCE", "100"))  # Min 100 BC to earn interest


class BankingService:
    """Service for banking operations.

    Responsibilities:
    - Balance queries and updates
    - Interest calculations and application
    - Transaction logging
    - Economy listing

    Pure service layer with no platform dependencies.
    Can be used by Discord adapter, web API, CLI, etc.
    """

    def __init__(self):
        """Initialize banking service with configured interest rates."""
        self.interest_rate = INTEREST_RATE_DAILY
        self.min_interest_balance = INTEREST_MIN_BALANCE

    def get_balance(
        self, user_id: int, guild_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get user's balance (wallet + bank).

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional, for guild-scoped economy)

        Returns:
            dict: {
                "wallet": int,
                "bank": int,
                "total": int,
            }
        """
        economy = get_economy(str(user_id), str(guild_id) if guild_id else None)
        if not economy:
            return {"wallet": 0, "bank": 0, "total": 0}

        wallet = economy.get("wallet_balance", economy.get("wallet", 0))
        bank = economy.get("bank_balance", economy.get("bank", 0))

        return {"wallet": wallet, "bank": bank, "total": wallet + bank}

    def update_balance(
        self,
        user_id: int,
        wallet_delta: int = 0,
        bank_delta: int = 0,
        guild_id: Optional[int] = None,
        reason: str = "",
    ) -> bool:
        """Update user's balance and log transaction.

        Args:
            user_id: Discord user ID
            wallet_delta: Amount to add/subtract from wallet
            bank_delta: Amount to add/subtract from bank
            guild_id: Discord guild ID (optional)
            reason: Transaction reason for logging

        Returns:
            bool: Success/failure
        """
        try:
            success = update_balance(
                str(user_id),
                wallet_delta=wallet_delta,
                bank_delta=bank_delta,
                guild_id=str(guild_id) if guild_id else None,
            )
            if success and (wallet_delta != 0 or bank_delta != 0):
                # Log transaction
                new_balance_data = self.get_balance(user_id, guild_id)
                log_transaction(
                    str(user_id),
                    str(guild_id) if guild_id else None,
                    "transfer" if wallet_delta != 0 and bank_delta != 0 else (
                        "withdrawal" if bank_delta < 0 else "deposit"
                    ),
                    abs(wallet_delta or bank_delta),
                    new_balance_data["total"],
                    reason,
                )
            return success
        except Exception as e:
            logger.error(f"[🏦] Failed to update balance for user {user_id}: {e}")
            return False

    def deposit(self, user_id: int, amount: int, guild_id: Optional[int] = None) -> bool:
        """Deposit from wallet to bank.

        Args:
            user_id: Discord user ID
            amount: Amount to deposit
            guild_id: Discord guild ID (optional)

        Returns:
            bool: Success/failure
        """
        balance = self.get_balance(user_id, guild_id)
        if balance["wallet"] < amount:
            logger.warning(
                f"[🏦] User {user_id} insufficient wallet ({balance['wallet']}) for deposit {amount}"
            )
            return False

        return self.update_balance(
            user_id,
            wallet_delta=-amount,
            bank_delta=amount,
            guild_id=guild_id,
            reason=f"Deposit {amount} BC to bank",
        )

    def withdraw(self, user_id: int, amount: int, guild_id: Optional[int] = None) -> bool:
        """Withdraw from bank to wallet.

        Args:
            user_id: Discord user ID
            amount: Amount to withdraw
            guild_id: Discord guild ID (optional)

        Returns:
            bool: Success/failure
        """
        balance = self.get_balance(user_id, guild_id)
        if balance["bank"] < amount:
            logger.warning(
                f"[🏦] User {user_id} insufficient bank ({balance['bank']}) for withdrawal {amount}"
            )
            return False

        return self.update_balance(
            user_id,
            wallet_delta=amount,
            bank_delta=-amount,
            guild_id=guild_id,
            reason=f"Withdraw {amount} BC from bank",
        )

    def calculate_interest(self, bank_balance: float) -> float:
        """Calculate interest for a balance.

        Args:
            bank_balance: Current bank balance

        Returns:
            float: Interest amount (prorated for 10-minute interval)
        """
        if bank_balance < self.min_interest_balance:
            return 0.0

        # Prorated for 10-minute interval: daily_rate / 144 (144 = 24*60/10)
        interval_rate = self.interest_rate / 144
        interest = bank_balance * interval_rate
        return interest

    def apply_interest(self, user_id: int, guild_id: Optional[int] = None) -> float:
        """Apply daily interest to user's bank balance.

        Called by scheduled job every 10 minutes.
        Calculates prorated interest and adds to bank balance.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)

        Returns:
            float: Interest amount applied
        """
        balance = self.get_balance(user_id, guild_id)
        bank_balance = balance["bank"]

        if bank_balance < self.min_interest_balance:
            return 0.0

        interest = self.calculate_interest(bank_balance)
        if interest > 0:
            interval_rate = self.interest_rate / 144
            self.update_balance(
                user_id,
                bank_delta=int(interest),
                guild_id=guild_id,
                reason=f"Interest earned ({interval_rate*100:.4f}%)",
            )
            return interest
        return 0.0

    def process_interest_cycle(self, log: bool = True) -> Dict[str, int]:
        """Process interest for all users (called by scheduled job).

        Returns:
            dict: {
                "processed": number of accounts processed,
                "interest_paid": total interest paid out
            }
        """
        try:
            processed = 0
            interest_paid = 0

            for econ in list_economies():
                user_id = econ.get("user_id")
                guild_id = econ.get("guild_id")
                if not user_id:
                    continue

                interest = self.apply_interest(int(user_id), int(guild_id) if guild_id else None)
                if interest > 0:
                    interest_paid += int(interest)

                processed += 1

            if log:
                logger.info(
                    f"[🏦] Interest cycle: processed {processed} accounts, paid {interest_paid} BC total"
                )
            return {"processed": processed, "interest_paid": interest_paid}

        except Exception as e:
            logger.error(f"[🏦] Interest cycle failed: {e}")
            return {"processed": 0, "interest_paid": 0}

    def list_economies(self) -> list:
        """List all economies.

        Returns:
            list: Economy documents from database
        """
        return list(list_economies())

    def check_daily_cooldown(self, user_id: int) -> bool:
        """Check if user can claim daily rewards (24h cooldown).

        Args:
            user_id: Discord user ID

        Returns:
            bool: True if cooldown has expired, False if still on cooldown
        """
        economy = get_economy(str(user_id))
        if not economy:
            return True

        last_daily = economy.get("last_daily")
        if not last_daily:
            return True

        # Check if 24 hours have passed
        if datetime.datetime.utcnow() - last_daily < datetime.timedelta(hours=24):
            return False

        return True


# Singleton instance for convenience
_banking_service: Optional[BankingService] = None


def get_banking_service() -> BankingService:
    """Get banking service singleton.

    Returns:
        BankingService: Singleton instance
    """
    global _banking_service
    if _banking_service is None:
        _banking_service = BankingService()
    return _banking_service
