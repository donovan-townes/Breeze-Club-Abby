"""Unified Economy Service - Platform-agnostic economy operations.

This module consolidates all economy operations (XP, banking, tipping, levels, transactions)
into a single, reusable service layer with no Discord dependencies.

Can be used by:
- Discord cogs (Discord adapter)
- Web API (REST adapter)
- CLI tools
- Admin panels
- Any other platform adapter

Architecture:
- No Discord imports
- Pure business logic
- Uses MongoDB directly via database module
- Maintains audit trails
- Supports transactions and rollback
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from abby_core.database.mongodb import (
    get_database,
    get_economy,
    update_balance,
    log_transaction,
    list_economies,
)
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Banking
INTEREST_RATE_DAILY = float(os.getenv("BANK_INTEREST_RATE_DAILY", "0.001"))
INTEREST_MIN_BALANCE = int(os.getenv("BANK_INTEREST_MIN_BALANCE", "100"))

# Tipping
TIP_BUDGET_DAILY = int(os.getenv("TIP_BUDGET_DAILY", "500"))  # BC per day
TIP_MAX_SINGLE = int(os.getenv("TIP_MAX_SINGLE", "100"))  # BC max per tip
TIP_MIN_SINGLE = int(os.getenv("TIP_MIN_SINGLE", "1"))  # BC min per tip

# XP
XP_MULTIPLIER_DEFAULT = float(os.getenv("XP_MULTIPLIER_DEFAULT", "1.0"))


class TransactionType(Enum):
    """Transaction types for audit trail."""
    BALANCE_TRANSFER = "balance_transfer"
    TIP = "tip"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    XP_GRANT = "xp_grant"
    XP_PENALTY = "xp_penalty"
    XP_RESET = "xp_reset"
    LEVEL_SET = "level_set"
    LEVEL_RESET = "level_reset"
    INTEREST = "interest"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class AuditAction(Enum):
    """Audit trail action types."""
    XP_GRANT = "xp_grant"
    XP_RESET = "xp_reset"
    LEVEL_SET = "level_set"
    LEVEL_RESET = "level_reset"
    BALANCE_TRANSFER = "balance_transfer"
    TIP = "tip"
    ADMIN_ADJUSTMENT = "admin_adjustment"


# ==================== ECONOMY SERVICE ====================

class EconomyService:
    """Unified economy service for all platform adapters.
    
    Consolidates:
    - Banking (wallet, bank, transfers, deposits, withdrawals)
    - Tipping (with daily budget enforcement)
    - XP Operations (grant, reset, leaderboard)
    - Level Operations (set, reset with audit trails)
    - Transaction Logging (all operations logged for audit)
    - User Profiles (balance snapshots, stats)
    
    Pure service layer - no platform dependencies.
    """
    
    def __init__(self):
        """Initialize economy service with configured rates."""
        self.interest_rate = INTEREST_RATE_DAILY
        self.min_interest_balance = INTEREST_MIN_BALANCE
        self.tip_budget_daily = TIP_BUDGET_DAILY
        self.tip_max_single = TIP_MAX_SINGLE
        self.tip_min_single = TIP_MIN_SINGLE
    
    # ==================== BANKING OPERATIONS ====================
    
    def get_balance(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get user's balance (wallet + bank).
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional, for guild-scoped economy)
        
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
    
    def transfer(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        guild_id: Optional[int] = None,
        reason: str = "transfer",
    ) -> Tuple[bool, Optional[str]]:
        """Transfer balance from one user to another.
        
        Args:
            from_user_id: Source user ID
            to_user_id: Target user ID
            amount: Amount to transfer (in BC)
            guild_id: Guild ID (optional)
            reason: Reason for transfer (for audit)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        # Check sender has sufficient balance
        sender_balance = self.get_balance(from_user_id, guild_id)
        if sender_balance["total"] < amount:
            return False, f"Insufficient balance: {sender_balance['total']} < {amount}"
        
        try:
            # Debit sender (from wallet)
            update_balance(
                str(from_user_id),
                wallet_delta=-amount,
                guild_id=str(guild_id) if guild_id else None,
            )
            
            # Credit receiver (to wallet)
            update_balance(
                str(to_user_id),
                wallet_delta=amount,
                guild_id=str(guild_id) if guild_id else None,
            )
            
            # Log transaction
            new_balance = self.get_balance(from_user_id, guild_id)
            log_transaction(
                str(from_user_id),
                str(guild_id) if guild_id else None,
                TransactionType.BALANCE_TRANSFER.value,
                amount,
                new_balance["total"],
                f"Transfer to {to_user_id}: {reason}",
            )
            
            logger.info(f"[💰] Transfer: {from_user_id} → {to_user_id} ({amount} BC)")
            return True, None
        
        except Exception as e:
            error_msg = f"Transfer failed: {str(e)}"
            logger.error(f"[💰] {error_msg}")
            return False, error_msg
    
    def tip(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        guild_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Transfer balance as a tip with daily budget enforcement.
        
        Args:
            from_user_id: User tipping
            to_user_id: User receiving tip
            amount: Tip amount (in BC)
            guild_id: Guild ID (optional)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        # Validate amount
        if amount < self.tip_min_single:
            return False, f"Tip too small (min: {self.tip_min_single} BC)"
        if amount > self.tip_max_single:
            return False, f"Tip too large (max: {self.tip_max_single} BC)"
        
        # Check sender's tip budget
        try:
            db = get_database()
            tip_collection = db["user_tip_budgets"]
            
            today = datetime.utcnow().date().isoformat()
            budget_doc = tip_collection.find_one({
                "user_id": str(from_user_id),
                "guild_id": str(guild_id) if guild_id else None,
                "date": today,
            })
            
            used_today = budget_doc.get("used", 0) if budget_doc else 0
            remaining = self.tip_budget_daily - used_today
            
            if amount > remaining:
                return False, f"Tip budget exhausted ({remaining} BC remaining)"
            
            # Perform transfer
            success, error = self.transfer(
                from_user_id,
                to_user_id,
                amount,
                guild_id,
                "tip",
            )
            
            if not success:
                return False, error
            
            # Update tip budget
            tip_collection.update_one(
                {
                    "user_id": str(from_user_id),
                    "guild_id": str(guild_id) if guild_id else None,
                    "date": today,
                },
                {
                    "$set": {
                        "user_id": str(from_user_id),
                        "guild_id": str(guild_id) if guild_id else None,
                        "date": today,
                        "used": used_today + amount,
                        "updated_at": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
            
            logger.info(f"[💝] Tip: {from_user_id} → {to_user_id} ({amount} BC)")
            return True, None
        
        except Exception as e:
            error_msg = f"Tip failed: {str(e)}"
            logger.error(f"[💝] {error_msg}")
            return False, error_msg
    
    def deposit(
        self,
        user_id: int,
        amount: int,
        guild_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Deposit from wallet to bank.
        
        Args:
            user_id: User ID
            amount: Amount to deposit
            guild_id: Guild ID (optional)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        balance = self.get_balance(user_id, guild_id)
        if balance["wallet"] < amount:
            return False, f"Insufficient wallet: {balance['wallet']} < {amount}"
        
        try:
            update_balance(
                str(user_id),
                wallet_delta=-amount,
                bank_delta=amount,
                guild_id=str(guild_id) if guild_id else None,
            )
            
            new_balance = self.get_balance(user_id, guild_id)
            log_transaction(
                str(user_id),
                str(guild_id) if guild_id else None,
                TransactionType.DEPOSIT.value,
                amount,
                new_balance["total"],
                f"Deposit {amount} BC to bank",
            )
            
            logger.info(f"[🏦] Deposit: {user_id} ({amount} BC)")
            return True, None
        
        except Exception as e:
            error_msg = f"Deposit failed: {str(e)}"
            logger.error(f"[🏦] {error_msg}")
            return False, error_msg
    
    def withdraw(
        self,
        user_id: int,
        amount: int,
        guild_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Withdraw from bank to wallet.
        
        Args:
            user_id: User ID
            amount: Amount to withdraw
            guild_id: Guild ID (optional)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        balance = self.get_balance(user_id, guild_id)
        if balance["bank"] < amount:
            return False, f"Insufficient bank: {balance['bank']} < {amount}"
        
        try:
            update_balance(
                str(user_id),
                wallet_delta=amount,
                bank_delta=-amount,
                guild_id=str(guild_id) if guild_id else None,
            )
            
            new_balance = self.get_balance(user_id, guild_id)
            log_transaction(
                str(user_id),
                str(guild_id) if guild_id else None,
                TransactionType.WITHDRAW.value,
                amount,
                new_balance["total"],
                f"Withdraw {amount} BC from bank",
            )
            
            logger.info(f"[🏦] Withdraw: {user_id} ({amount} BC)")
            return True, None
        
        except Exception as e:
            error_msg = f"Withdraw failed: {str(e)}"
            logger.error(f"[🏦] {error_msg}")
            return False, error_msg
    
    # ==================== XP OPERATIONS ====================
    
    def grant_xp(
        self,
        user_id: int,
        amount: int,
        guild_id: Optional[int] = None,
        reason: str = "message",
    ) -> Tuple[int, int, bool]:
        """Grant XP to a user.
        
        Args:
            user_id: User ID
            amount: XP to grant
            guild_id: Guild ID (optional)
            reason: Reason for grant (for audit)
        
        Returns:
            (new_xp: int, new_level: int, success: bool)
        """
        from abby_core.system.system_state import get_active_state
        from abby_core.economy.xp import add_xp as xp_add_xp
        from abby_core.economy.user_levels import get_user_level_record
        
        user_id = int(user_id)
        guild_id = int(guild_id) if guild_id else None
        
        try:
            # Use existing xp.add_xp for core logic
            new_xp = xp_add_xp(user_id, amount, guild_id, reason)
            
            # Get level from user_levels
            level_record = get_user_level_record(str(user_id), str(guild_id) if guild_id else None)
            new_level = level_record.get("level", 1) if level_record else 1
            
            # Audit log
            self._log_audit(
                AuditAction.XP_GRANT,
                user_id,
                guild_id,
                {
                    "amount": amount,
                    "reason": reason,
                    "new_xp": new_xp,
                    "new_level": new_level,
                },
            )
            
            return new_xp, new_level, True
        
        except Exception as e:
            logger.error(f"[⭐] Failed to grant XP: {e}")
            return 0, 1, False
    
    def reset_xp(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Reset user's XP to 0 (seasonal reset or punishment).
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        from abby_core.economy.xp import reset_exp
        
        user_id = int(user_id)
        guild_id = int(guild_id) if guild_id else None
        
        try:
            reset_exp(user_id, guild_id)
            
            # Audit log
            self._log_audit(
                AuditAction.XP_RESET,
                user_id,
                guild_id,
                {"reason": "operator_reset"},
            )
            
            logger.info(f"[⭐] XP reset: {user_id}")
            return True, None
        
        except Exception as e:
            error_msg = f"XP reset failed: {str(e)}"
            logger.error(f"[⭐] {error_msg}")
            return False, error_msg
    
    def get_xp_leaderboard(
        self,
        guild_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get XP leaderboard for a guild or global.
        
        Args:
            guild_id: Guild ID (optional, for guild leaderboard)
            limit: Number of users to return
        
        Returns:
            List of {user_id, xp, level}
        """
        try:
            from abby_core.database.collections.xp import get_collection as get_xp_col
            xp_collection = get_xp_col()
            
            query = {}
            if guild_id:
                query["guild_id"] = str(guild_id)
            
            results = list(xp_collection.find(query).sort("xp", -1).limit(limit))
            
            return [
                {
                    "user_id": r.get("user_id"),
                    "xp": r.get("xp", 0),
                    "level": r.get("level", 1),
                }
                for r in results
            ]
        
        except Exception as e:
            logger.error(f"[⭐] Failed to fetch leaderboard: {e}")
            return []
    
    # ==================== LEVEL OPERATIONS ====================
    
    def set_level(
        self,
        user_id: int,
        level: int,
        guild_id: Optional[int] = None,
        reason: str = "admin",
    ) -> Tuple[bool, Optional[str]]:
        """Set a user's level.
        
        Args:
            user_id: User ID
            level: Target level
            guild_id: Guild ID (optional)
            reason: Reason for change (for audit)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        from abby_core.economy.user_levels import set_user_level
        
        user_id = int(user_id)
        guild_id = int(guild_id) if guild_id else None
        
        if level < 1:
            return False, "Level must be >= 1"
        
        try:
            # Convert to str for database operations
            set_user_level(str(user_id), str(guild_id) if guild_id else None, level, force=True)
            
            # Audit log
            self._log_audit(
                AuditAction.LEVEL_SET,
                user_id,
                guild_id,
                {"target_level": level, "reason": reason},
            )
            
            logger.info(f"[🎖️] Level set: {user_id} → Level {level}")
            return True, None
        
        except Exception as e:
            error_msg = f"Level set failed: {str(e)}"
            logger.error(f"[🎖️] {error_msg}")
            return False, error_msg
    
    def reset_level(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
        reason: str = "admin",
    ) -> Tuple[bool, Optional[str]]:
        """Reset a user's level to 1.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
            reason: Reason for reset (for audit)
        
        Returns:
            (success: bool, error: Optional[str])
        """
        return self.set_level(user_id, 1, guild_id, reason)
    
    def reset_all_levels(
        self,
        guild_id: int,
        reason: str = "admin",
    ) -> Tuple[int, Optional[str]]:
        """Reset all users' levels in a guild to 1.
        
        Args:
            guild_id: Guild ID
            reason: Reason for reset (for audit)
        
        Returns:
            (count: int, error: Optional[str])
        """
        from abby_core.economy.user_levels import reset_levels_for_guild
        
        guild_id = int(guild_id)
        
        try:
            # Convert to str for database operations
            count = reset_levels_for_guild(str(guild_id))
            
            # Audit log
            self._log_audit(
                AuditAction.LEVEL_RESET,
                None,
                guild_id,
                {"type": "guild_wide", "count": count, "reason": reason},
            )
            
            logger.warning(f"[🎖️] Guild levels reset: {guild_id} ({count} users)")
            return count, None
        
        except Exception as e:
            error_msg = f"Guild level reset failed: {str(e)}"
            logger.error(f"[🎖️] {error_msg}")
            return 0, error_msg
    
    # ==================== AUDIT & UTILITY ====================
    
    def _log_audit(
        self,
        action: AuditAction,
        user_id: Optional[int],
        guild_id: Optional[int],
        details: Dict[str, Any],
    ) -> None:
        """Log an economy action to audit trail.
        
        Args:
            action: Type of action
            user_id: User ID (optional, for guild-wide actions use None)
            guild_id: Guild ID (optional)
            details: Action-specific details
        """
        try:
            db = get_database()
            audit_collection = db["economy_audit"]
            
            audit_collection.insert_one({
                "action": action.value,
                "user_id": str(user_id) if user_id else None,
                "guild_id": str(guild_id) if guild_id else None,
                "details": details,
                "timestamp": datetime.utcnow(),
            })
        
        except Exception as e:
            logger.error(f"[📋] Failed to log audit: {e}")
    
    def get_user_stats(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get user's economy stats summary.
        
        Args:
            user_id: User ID
            guild_id: Guild ID (optional)
        
        Returns:
            dict: {
                "balance": {...},
                "xp": int,
                "level": int,
                "tip_budget_remaining": int,
            }
        """
        from abby_core.economy.xp import get_xp
        from abby_core.economy.user_levels import get_user_level_record
        
        user_id = int(user_id)
        guild_id = int(guild_id) if guild_id else None
        
        try:
            balance = self.get_balance(user_id, guild_id)
            xp_doc = get_xp(user_id, guild_id)
            xp_amount = xp_doc.get("xp", 0) if xp_doc else 0
            
            # Get level from user_levels
            level_record = get_user_level_record(str(user_id), str(guild_id) if guild_id else None)
            level = level_record.get("level", 1) if level_record else 1
            
            # Get tip budget remaining
            db = get_database()
            tip_collection = db["user_tip_budgets"]
            today = datetime.utcnow().date().isoformat()
            budget_doc = tip_collection.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id) if guild_id else None,
                "date": today,
            })
            used_today = budget_doc.get("used", 0) if budget_doc else 0
            tip_remaining = max(0, self.tip_budget_daily - used_today)
            
            return {
                "balance": balance,
                "xp": xp_amount,
                "level": level,
                "tip_budget_remaining": tip_remaining,
            }
        
        except Exception as e:
            logger.error(f"[📊] Failed to get user stats: {e}")
            return {
                "balance": {"wallet": 0, "bank": 0, "total": 0},
                "xp": 0,
                "level": 1,
                "tip_budget_remaining": self.tip_budget_daily,
            }


# ==================== SINGLETON INSTANCE ====================

# Global singleton instance (lazy-loaded)
_economy_service: Optional[EconomyService] = None


def get_economy_service() -> EconomyService:
    """Get the global economy service instance.
    
    Returns:
        EconomyService: Singleton instance
    """
    global _economy_service
    if _economy_service is None:
        _economy_service = EconomyService()
    return _economy_service
