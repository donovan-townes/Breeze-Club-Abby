from datetime import datetime

from abby_core.database.collections import guild_configuration


class _FakeResult:
    def __init__(self, matched_count=1):
        self.matched_count = matched_count


class _FakeCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, query, update_doc):
        self.calls.append((query, update_doc))
        return _FakeResult(matched_count=1)


def test_update_guild_config_avoids_metadata_path_conflict(monkeypatch):
    fake_collection = _FakeCollection()
    monkeypatch.setattr(guild_configuration, "get_collection", lambda: fake_collection)

    ok = guild_configuration.update_guild_config(123, {"metadata": {"description": "hello"}})

    assert ok is True
    assert len(fake_collection.calls) == 1

    _, update_doc = fake_collection.calls[0]
    set_doc = update_doc["$set"]

    assert "metadata.updated_at" not in set_doc
    assert set_doc["metadata"]["description"] == "hello"
    assert isinstance(set_doc["metadata"]["updated_at"], datetime)


def test_update_guild_config_sets_metadata_updated_at_for_non_metadata_updates(monkeypatch):
    fake_collection = _FakeCollection()
    monkeypatch.setattr(guild_configuration, "get_collection", lambda: fake_collection)

    ok = guild_configuration.update_guild_config(123, {"timezone": "UTC"})

    assert ok is True
    assert len(fake_collection.calls) == 1

    _, update_doc = fake_collection.calls[0]
    set_doc = update_doc["$set"]

    assert set_doc["timezone"] == "UTC"
    assert isinstance(set_doc["metadata.updated_at"], datetime)
