"""
Test suite for economy scoping.
"""
import pytest

def test_economy_scoping():
    pass


class FakeResult:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self):
        self.find_calls = []
        self.update_calls = []
        self.count_calls = []

    def find_one(self, query):
        self.find_calls.append(query)
        # Return doc using canonical fields; include legacy for fallback validation
        return {
            "user_id": query.get("user_id"),
            "guild_id": query.get("guild_id"),
            "wallet_balance": 10,
            "bank_balance": 20,
            "wallet": 10,
            "bank": 20,
        }

    def update_one(self, query, update_doc, upsert=False):
        self.update_calls.append((query, update_doc, upsert))
        return FakeResult(1)

    def count_documents(self, *args, **kwargs):
        # Normalize filter regardless of positional/keyword usage
        query = args[0] if args else kwargs.get("filter")
        normalized_kwargs = dict(kwargs)
        if query is not None and "filter" not in normalized_kwargs:
            normalized_kwargs["filter"] = query

        self.count_calls.append((args, normalized_kwargs))
        return 0


class FakeDB:
    def __init__(self):
        self.collections = {
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


def test_update_balance_uses_canonical_fields(fake_client):
    collection = fake_client.db.collections["economy"]

    mongo.update_balance("user-1", wallet_delta=5, bank_delta=-2, guild_id="guild-1")

    assert len(collection.update_calls) == 1
    query, update_doc, upsert = collection.update_calls[0]
    assert query == {"user_id": "user-1", "guild_id": "guild-1"}
    assert update_doc["$inc"]["wallet_balance"] == 5
    assert update_doc["$inc"]["bank_balance"] == -2
    assert upsert is True


def test_get_economy_scopes_guild(fake_client):
    collection = fake_client.db.collections["economy"]
    doc = mongo.get_economy("user-2", guild_id="guild-2")

    assert collection.find_calls[0] == {"user_id": "user-2", "guild_id": "guild-2"}
    assert doc is not None
    assert doc["guild_id"] == "guild-2"
    assert doc.get("wallet_balance") == 10
    assert doc.get("bank_balance") == 20


def test_list_economies_filters_guild(fake_client):
    collection = fake_client.db.collections["economy"]

    # Inject documents into the fake find cursor by mocking find
    docs = [
        {"user_id": "u1", "guild_id": "g1"},
        {"user_id": "u2", "guild_id": "g1"},
    ]

    def fake_find(query, batch_size=None):
        collection.find_calls.append(query)
        for d in docs:
            if query.get("guild_id") is None or d.get("guild_id") == query.get("guild_id"):
                yield d

    collection.find = fake_find

    results = list(mongo.list_economies(guild_id="g1"))
    assert collection.find_calls[0] == {"guild_id": "g1"}
    assert results == docs


def test_get_level_accepts_guild(monkeypatch):
    calls = []

    def fake_get_xp(user_id, guild_id=None):
        calls.append((user_id, guild_id))
        return {"user_id": user_id, "guild_id": guild_id, "level": 3}

    monkeypatch.setattr(xp_mod, "get_xp", fake_get_xp)
    level = xp_mod.get_level("u123", guild_id="g123")

    assert level == 3
    assert calls == [("u123", "g123")]


def test_dashboard_counts_use_status_filters(fake_client):
    sessions = fake_client.db.collections["chat_sessions"]
    submissions = fake_client.db.collections["submissions"]

    _ = mongo.get_active_sessions_count()
    _ = mongo.get_pending_submissions_count()

    # count_documents was called once each; kwargs hold the filter
    assert sessions.count_calls[0][1].get("filter") == {"status": {"$in": ["active", "open"]}}
    assert submissions.count_calls[0][1].get("filter") == {"status": {"$in": ["submitted", "pending"]}}
