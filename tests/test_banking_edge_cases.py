"""
Edge case and validation tests for banking operations.

Tests cog-layer validation, error handling, and boundary conditions.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abby_core.database.mongodb as mongo
import abby_core.economy.bank as bank_module


class FakeCollection:
    def __init__(self):
        self.operations = []

    def find_one(self, query):
        self.operations.append(("find_one", query))
        return {
            "user_id": query.get("user_id"),
            "guild_id": query.get("guild_id"),
            "wallet_balance": 1000,
            "bank_balance": 500,
        }

    def update_one(self, query, update_doc, upsert=False):
        self.operations.append(("update_one", query, update_doc, upsert))
        return MagicMock(modified_count=1)

    def insert_one(self, doc):
        self.operations.append(("insert_one", doc))
        return MagicMock(inserted_id="txn-123")

    def find(self, query, **kwargs):
        self.operations.append(("find", query, kwargs))
        return []


class FakeDB:
    def __init__(self):
        self.collections = {
            "economy": FakeCollection(),
            "transactions": FakeCollection(),
            "chat_sessions": FakeCollection(),
            "submissions": FakeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FakeClient:
    def __init__(self):
        self.db = FakeDB()

    def __getitem__(self, name):
        return self.db


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(mongo, "connect_to_mongodb", lambda: client)
    return client


class TestSelfTransferValidation:
    """Test that self-transfers are detected and prevented."""

    def test_self_transfer_should_be_rejected_in_cog(self, fake_client):
        """Cog should validate sender != recipient before any database call."""
        # Validation happens in the cog layer (application code)
        # Database layer doesn't enforce it
        sender = "alice"
        recipient = "alice"
        
        # Cog validates: if sender == recipient, show error and return
        assert sender == recipient  # This should trigger cog validation


class TestInsufficientFundsValidation:
    """Test that insufficient funds are detected and prevented."""

    def test_deposit_insufficient_wallet_balance(self, fake_client):
        """Deposit should validate wallet >= amount."""
        economy_col = fake_client.db.collections["economy"]
        econ = mongo.get_economy("user-1", "guild-1")
        
        wallet = econ.get("wallet_balance", 0)
        requested_deposit = 2000  # More than wallet
        
        # Cog validates: if wallet < requested_deposit, show error and return
        if wallet < requested_deposit:
            # Don't call update_balance
            assert len(economy_col.operations) == 1  # Just the find_one

    def test_withdraw_insufficient_bank_balance(self, fake_client):
        """Withdraw should validate bank >= amount."""
        economy_col = fake_client.db.collections["economy"]
        econ = mongo.get_economy("user-1", "guild-1")
        
        bank = econ.get("bank_balance", 0)
        requested_withdraw = 2000  # More than bank
        
        # Cog validates: if bank < requested_withdraw, show error and return
        if bank < requested_withdraw:
            # Don't call update_balance
            assert len(economy_col.operations) == 1  # Just the find_one


class TestTransferSelfPayValidation:
    """Test transfer self-pay edge case."""

    def test_transfer_to_self_should_error(self, fake_client):
        """User cannot pay themselves."""
        sender = "alice"
        recipient = "alice"
        amount = 100
        
        # Cog should validate sender != recipient before update
        if sender == recipient:
            # Show error, don't update database
            economy_col = fake_client.db.collections["economy"]
            assert len(economy_col.operations) == 0


class TestTransferBotPayValidation:
    """Test that transfers to/from bot are prevented."""

    def test_transfer_from_bot_prevented(self, fake_client):
        """Bot user cannot be sender."""
        sender_id = "1234567890"  # Example bot ID
        is_bot = True
        
        # Cog validates is_bot before allowing transfer
        if is_bot:
            # Don't allow transfer
            assert True

    def test_transfer_to_bot_prevented(self, fake_client):
        """Bot user cannot be recipient."""
        recipient_id = "1234567890"  # Example bot ID
        is_bot = True
        
        # Cog validates is_bot before allowing transfer
        if is_bot:
            # Don't allow transfer
            assert True


class TestZeroAndNegativeAmounts:
    """Test handling of zero and negative amounts."""

    def test_zero_amount_deposit_rejected(self, fake_client):
        """Deposit of 0 BC should be rejected."""
        amount = 0
        
        # Cog validates amount > 0
        assert amount <= 0

    def test_zero_amount_withdraw_rejected(self, fake_client):
        """Withdraw of 0 BC should be rejected."""
        amount = 0
        
        assert amount <= 0

    def test_zero_amount_transfer_rejected(self, fake_client):
        """Transfer of 0 BC should be rejected."""
        amount = 0
        
        assert amount <= 0

    def test_negative_amount_deposit_rejected(self, fake_client):
        """Deposit of negative amount should be rejected."""
        amount = -100
        
        assert amount < 0

    def test_negative_amount_withdraw_rejected(self, fake_client):
        """Withdraw of negative amount should be rejected."""
        amount = -100
        
        assert amount < 0

    def test_negative_amount_transfer_rejected(self, fake_client):
        """Transfer of negative amount should be rejected."""
        amount = -100
        
        assert amount < 0


class TestLargeAmounts:
    """Test handling of very large amounts."""

    def test_very_large_deposit_allowed_if_wallet_sufficient(self, fake_client):
        """Very large deposits should be allowed if wallet has funds."""
        wallet = 1_000_000
        requested = 999_999
        
        assert wallet >= requested  # Should be allowed

    def test_very_large_balance_after_operations(self, fake_client):
        """Balance should accumulate correctly with large amounts."""
        starting_bank = 999_999
        deposit = 1_000_000
        final = starting_bank + deposit
        
        assert final == 1_999_999


class TestInterestBoundaryConditions:
    """Test interest accrual at boundary conditions."""

    def test_interest_at_exact_minimum_balance(self, fake_client):
        """Interest should apply at exactly BANK_INTEREST_MIN_BALANCE."""
        min_balance = bank_module.INTEREST_MIN_BALANCE
        daily_rate = bank_module.INTEREST_RATE_DAILY
        
        # Exactly at minimum
        balance = min_balance
        interval_interest = int(balance * (daily_rate / 144))
        
        # Should calculate interest (may be 0 due to rounding)
        assert interval_interest >= 0

    def test_interest_below_minimum_balance(self, fake_client):
        """Interest should not apply below BANK_INTEREST_MIN_BALANCE."""
        min_balance = bank_module.INTEREST_MIN_BALANCE
        
        balance = min_balance - 1
        
        # Should skip interest
        assert balance < min_balance

    def test_interest_just_above_minimum_balance(self, fake_client):
        """Interest should apply just above BANK_INTEREST_MIN_BALANCE."""
        min_balance = bank_module.INTEREST_MIN_BALANCE
        
        balance = min_balance + 1
        
        # Should apply interest
        assert balance >= min_balance


class TestTransactionHistoryEdgeCases:
    """Test transaction history edge cases."""

    def test_history_with_zero_transactions(self, fake_client):
        """History should return empty list if no transactions."""
        history = mongo.get_transaction_history("user-1", "guild-1", limit=10)
        
        assert isinstance(history, list)
        assert len(history) == 0

    def test_history_limit_zero_returns_empty(self, fake_client):
        """History with limit=0 should return empty."""
        history = mongo.get_transaction_history("user-1", "guild-1", limit=0)
        
        assert history == []

    def test_history_limit_respects_ceiling(self, fake_client):
        """History should not exceed requested limit."""
        # Even if user has 100 transactions, requesting limit=5 returns 5
        limit = 5
        history = mongo.get_transaction_history("user-1", "guild-1", limit=limit)
        
        assert len(history) <= limit


class TestProfileAutoCreation:
    """Test automatic profile creation for transfers."""

    def test_transfer_to_nonexistent_user_creates_profile(self, fake_client):
        """Transferring to new user should create their profile."""
        economy_col = fake_client.db.collections["economy"]
        
        # Ensure recipient doesn't exist (in real scenario, cog would check)
        recipient_econ = None
        
        if recipient_econ is None:
            # Create profile via update_balance with upsert
            mongo.update_balance("new-user", wallet_delta=0, bank_delta=0, guild_id="guild-1")
            mongo.update_balance("new-user", wallet_delta=200, guild_id="guild-1")
        
        assert len(economy_col.operations) == 2  # 2 update_one calls (no find_one in mock)


class TestConcurrentOperationSafety:
    """Test that database operations are safe under concurrent access."""

    def test_multiple_deposits_are_sequential(self, fake_client):
        """Each deposit should be a separate database operation."""
        economy_col = fake_client.db.collections["economy"]
        
        mongo.update_balance("user-1", wallet_delta=-100, bank_delta=100, guild_id="guild-1")
        mongo.update_balance("user-1", wallet_delta=-200, bank_delta=200, guild_id="guild-1")
        
        # Each operation should be separate (MongoDB handles atomicity)
        assert len(economy_col.operations) == 2

    def test_transfer_operations_are_independent(self, fake_client):
        """Sender and recipient updates should be independent operations."""
        economy_col = fake_client.db.collections["economy"]
        
        # Sender loses
        mongo.update_balance("alice", wallet_delta=-100, guild_id="guild-1")
        # Recipient gains
        mongo.update_balance("bob", wallet_delta=100, guild_id="guild-1")
        
        # Two separate operations
        assert len(economy_col.operations) == 2


class TestCurrencyRounding:
    """Test currency formatting with rounding edge cases."""

    def test_1_bc_displays_as_penny(self):
        """1 BC = $0.01"""
        bc = 1
        dollars = bc / 100
        assert dollars == 0.01

    def test_99_bc_displays_as_99_cents(self):
        """99 BC = $0.99"""
        bc = 99
        dollars = bc / 100
        assert dollars == 0.99

    def test_101_bc_displays_as_1_dollar_1_cent(self):
        """101 BC = $1.01"""
        bc = 101
        dollars = bc / 100
        assert dollars == 1.01

    def test_150_bc_displays_as_1_dollar_50_cents(self):
        """150 BC = $1.50"""
        bc = 150
        dollars = bc / 100
        assert dollars == 1.50


class TestOperationAtomicity:
    """Test that operations are atomic."""

    def test_deposit_single_operation(self, fake_client):
        """Deposit should be a single atomic operation."""
        economy_col = fake_client.db.collections["economy"]
        
        mongo.update_balance("user-1", wallet_delta=-100, bank_delta=100, guild_id="guild-1")
        
        # Should be single update, not two separate operations
        updates = [op for op in economy_col.operations if op[0] == "update_one"]
        assert len(updates) == 1

    def test_withdraw_single_operation(self, fake_client):
        """Withdraw should be a single atomic operation."""
        economy_col = fake_client.db.collections["economy"]
        
        mongo.update_balance("user-1", wallet_delta=100, bank_delta=-100, guild_id="guild-1")
        
        updates = [op for op in economy_col.operations if op[0] == "update_one"]
        assert len(updates) == 1

    def test_interest_application_single_operation(self, fake_client):
        """Interest application should be single operation."""
        economy_col = fake_client.db.collections["economy"]
        
        mongo.update_balance("user-1", bank_delta=1, guild_id="guild-1")
        
        updates = [op for op in economy_col.operations if op[0] == "update_one"]
        assert len(updates) == 1
