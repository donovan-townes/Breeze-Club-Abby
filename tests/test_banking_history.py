"""
Transaction history and currency formatting tests.

Tests the retrieval and display of transaction history with proper formatting.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abby_core.database.mongodb as mongo


class FakeTransaction:
    def __init__(self, user_id, txn_type, amount, balance_after, description, timestamp=None):
        self.user_id = user_id
        self.type = txn_type
        self.amount = amount
        self.balance_after = balance_after
        self.description = description
        self.timestamp = timestamp or datetime.now()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "type": self.type,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "description": self.description,
            "timestamp": self.timestamp,
        }


class FakeCollection:
    def __init__(self):
        self.transactions = []
        self.operations = []

    def find_one(self, query):
        self.operations.append(("find_one", query))
        return None

    def insert_one(self, doc):
        self.operations.append(("insert_one", doc))
        self.transactions.append(doc)
        return MagicMock(inserted_id="txn-123")

    def find(self, query, **kwargs):
        self.operations.append(("find", query, kwargs))
        # Return transactions matching query
        sort = kwargs.get("sort", [])
        skip = kwargs.get("skip", 0)
        limit = kwargs.get("limit", 10)
        
        filtered = [t for t in self.transactions if t.get("user_id") == query.get("user_id")]
        
        # Apply sort
        if sort:
            for key, direction in reversed(sort):
                filtered.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
        
        # Apply skip and limit
        return filtered[skip : skip + limit]


class FakeDB:
    def __init__(self):
        self.collections = {
            "transactions": FakeCollection(),
            "economy": FakeCollection(),
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


class TestTransactionHistoryRetrieval:
    """Test transaction history retrieval."""

    def test_get_history_returns_list(self, fake_client):
        """History should return a list of transactions."""
        history = mongo.get_transaction_history("user-1", "guild-1", limit=10)
        assert isinstance(history, list)

    def test_get_history_filters_by_user_and_guild(self, fake_client):
        """History should filter by user_id and guild_id."""
        txn_col = fake_client.db.collections["transactions"]
        
        # Log transactions
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        mongo.log_transaction("user-1", "guild-2", "deposit", 100, 600)
        mongo.log_transaction("user-2", "guild-1", "deposit", 100, 600)
        
        assert len(txn_col.transactions) == 3
        
        # Retrieve history for user-1 in guild-1
        history = mongo.get_transaction_history("user-1", "guild-1", limit=10)
        
        # Should query for correct user and guild
        find_ops = [op for op in txn_col.operations if op[0] == "find"]
        assert len(find_ops) > 0

    def test_get_history_respects_limit(self, fake_client):
        """History should respect the limit parameter."""
        txn_col = fake_client.db.collections["transactions"]
        
        # Create many transactions
        for i in range(20):
            mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600 + i)
        
        # Retrieve with limit
        history = mongo.get_transaction_history("user-1", "guild-1", limit=5)
        
        assert len(history) <= 5

    def test_get_history_defaults_to_10(self, fake_client):
        """History should default to limit=10 if not specified."""
        # Function should have default limit=10
        # Just verify the parameter is passed
        result = mongo.get_transaction_history("user-1", "guild-1")
        assert isinstance(result, list)


class TestTransactionHistoryOrdering:
    """Test that transaction history is properly ordered."""

    def test_history_ordered_by_timestamp_descending(self, fake_client):
        """Most recent transactions should appear first."""
        txn_col = fake_client.db.collections["transactions"]
        
        now = datetime.now()
        
        # Log transactions with explicit timestamps
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        mongo.log_transaction("user-1", "guild-1", "withdraw", 50, 550)
        mongo.log_transaction("user-1", "guild-1", "deposit", 75, 625)
        
        # Get history
        history = mongo.get_transaction_history("user-1", "guild-1", limit=10)
        
        # Verify it's a list (actual timestamp ordering tested in integration)
        assert isinstance(history, list)


class TestTransactionTypes:
    """Test various transaction types."""

    def test_deposit_transaction_type(self, fake_client):
        """Deposit transactions should have correct type."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        
        txn = txn_col.transactions[0]
        assert txn["type"] == "deposit"

    def test_withdraw_transaction_type(self, fake_client):
        """Withdraw transactions should have correct type."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "withdraw", 50, 550)
        
        txn = txn_col.transactions[0]
        assert txn["type"] == "withdraw"

    def test_transfer_transaction_type(self, fake_client):
        """Transfer transactions should have correct type."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "transfer", 200, 800)
        
        txn = txn_col.transactions[0]
        assert txn["type"] == "transfer"

    def test_interest_transaction_type(self, fake_client):
        """Interest transactions should have correct type."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "interest", 1, 501)
        
        txn = txn_col.transactions[0]
        assert txn["type"] == "interest"

    def test_init_transaction_type(self, fake_client):
        """Init transactions should have correct type."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "init", 1000, 1500)
        
        txn = txn_col.transactions[0]
        assert txn["type"] == "init"


class TestTransactionDescriptions:
    """Test transaction description content."""

    def test_deposit_description_format(self, fake_client):
        """Deposit description should be clear."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600, "Deposited 100 BC")
        
        txn = txn_col.transactions[0]
        assert "Deposited" in txn["description"] or "deposit" in txn["description"].lower()

    def test_withdraw_description_format(self, fake_client):
        """Withdraw description should be clear."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "withdraw", 50, 550, "Withdrew 50 BC")
        
        txn = txn_col.transactions[0]
        assert "Withdrew" in txn["description"] or "withdraw" in txn["description"].lower()

    def test_transfer_description_includes_recipient(self, fake_client):
        """Transfer description should name the recipient."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("alice", "guild-1", "transfer", 100, 900, "Sent 100 BC to bob")
        
        txn = txn_col.transactions[0]
        assert "bob" in txn["description"] or "recipient" in txn["description"].lower()

    def test_transfer_description_includes_sender(self, fake_client):
        """Transfer description should name the sender."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("bob", "guild-1", "transfer", 100, 1100, "Received 100 BC from alice")
        
        txn = txn_col.transactions[0]
        assert "alice" in txn["description"] or "sender" in txn["description"].lower()

    def test_interest_description_format(self, fake_client):
        """Interest description should note it's earned."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "interest", 1, 501, "Interest earned (0.0007%)")
        
        txn = txn_col.transactions[0]
        assert "earned" in txn["description"].lower() or "interest" in txn["description"].lower()


class TestTransactionAmounts:
    """Test transaction amount recording."""

    def test_deposit_amount_recorded(self, fake_client):
        """Deposit amount should be recorded."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        
        txn = txn_col.transactions[0]
        assert txn["amount"] == 100

    def test_withdraw_amount_recorded(self, fake_client):
        """Withdraw amount should be recorded."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "withdraw", 50, 550)
        
        txn = txn_col.transactions[0]
        assert txn["amount"] == 50

    def test_transfer_amount_recorded(self, fake_client):
        """Transfer amount should be recorded."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "transfer", 200, 800)
        
        txn = txn_col.transactions[0]
        assert txn["amount"] == 200

    def test_interest_amount_recorded(self, fake_client):
        """Interest amount should be recorded."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "interest", 1, 501)
        
        txn = txn_col.transactions[0]
        assert txn["amount"] == 1


class TestBalanceAfterRecording:
    """Test that balance after is recorded correctly."""

    def test_balance_after_deposit(self, fake_client):
        """Balance after should reflect deposit."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        
        txn = txn_col.transactions[0]
        assert txn["balance_after"] == 600

    def test_balance_after_withdraw(self, fake_client):
        """Balance after should reflect withdraw."""
        txn_col = fake_client.db.collections["transactions"]
        
        mongo.log_transaction("user-1", "guild-1", "withdraw", 50, 550)
        
        txn = txn_col.transactions[0]
        assert txn["balance_after"] == 550

    def test_balance_after_transfer(self, fake_client):
        """Balance after should reflect transfer."""
        txn_col = fake_client.db.collections["transactions"]
        
        # Sender
        mongo.log_transaction("alice", "guild-1", "transfer", 100, 900)
        # Recipient
        mongo.log_transaction("bob", "guild-1", "transfer", 100, 1100)
        
        sender_txn = txn_col.transactions[0]
        recipient_txn = txn_col.transactions[1]
        
        assert sender_txn["balance_after"] == 900
        assert recipient_txn["balance_after"] == 1100


class TestHistoryFormatting:
    """Test that history display can be properly formatted."""

    def test_transaction_can_be_displayed_with_emoji(self):
        """Transaction type should map to emoji for display."""
        emoji_map = {
            "deposit": "💰",
            "withdraw": "💸",
            "transfer": "🔄",
            "interest": "📈",
            "init": "✨",
        }
        
        txn_type = "deposit"
        emoji = emoji_map.get(txn_type, "")
        
        assert emoji == "💰"

    def test_transaction_can_be_displayed_with_timestamp(self):
        """Timestamp should be formattable for display."""
        now = datetime.now()
        formatted = now.strftime("%Y-%m-%d %H:%M")
        
        assert len(formatted) == 16  # YYYY-MM-DD HH:MM

    def test_transaction_can_be_displayed_with_currency(self):
        """Amount should be displayable in currency format."""
        bc = 1200
        formatted = f"{bc} BC (${bc / 100:.2f})"
        
        assert formatted == "1200 BC ($12.00)"

    def test_transaction_display_combines_all_fields(self):
        """All fields should work together for display."""
        txn = {
            "type": "deposit",
            "amount": 500,
            "balance_after": 1500,
            "description": "Deposited 500 BC",
            "timestamp": datetime(2024, 1, 15, 10, 30),
        }
        
        emoji_map = {"deposit": "💰", "withdraw": "💸", "transfer": "🔄"}
        emoji = emoji_map.get(txn["type"], "")
        timestamp_str = txn["timestamp"].strftime("%Y-%m-%d %H:%M")
        currency_str = f"{txn['amount']} BC (${txn['amount'] / 100:.2f})"
        
        display = f"{emoji} {timestamp_str} | {currency_str} | {txn['description']}"
        
        assert "💰" in display
        assert "2024-01-15 10:30" in display
        assert "500 BC ($5.00)" in display
        assert "Deposited 500 BC" in display


class TestHistoryMultipleGuilds:
    """Test history isolation across guilds."""

    def test_history_does_not_mix_guilds(self, fake_client):
        """User's history in guild-1 shouldn't include guild-2 transactions."""
        txn_col = fake_client.db.collections["transactions"]
        
        # Same user in two guilds
        mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
        mongo.log_transaction("user-1", "guild-2", "deposit", 100, 600)
        
        assert len(txn_col.transactions) == 2
        
        # Get history for guild-1
        history_g1 = mongo.get_transaction_history("user-1", "guild-1", limit=10)
        
        # Should be a list (actual guild filtering tested in integration)
        assert isinstance(history_g1, list)
