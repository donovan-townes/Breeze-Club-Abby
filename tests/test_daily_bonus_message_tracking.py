import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType


discord_module = ModuleType("discord")
setattr(discord_module, "Reaction", object)
setattr(discord_module, "User", object)
setattr(discord_module, "Member", object)
setattr(discord_module, "Message", object)
setattr(discord_module, "Guild", object)
setattr(discord_module, "TextChannel", object)
setattr(discord_module, "Thread", object)
setattr(discord_module, "VoiceState", object)
setattr(discord_module, "HTTPException", Exception)
setattr(discord_module, "Forbidden", Exception)
setattr(discord_module, "NotFound", Exception)

commands_module = ModuleType("discord.ext.commands")


class _DummyCog:
    @staticmethod
    def listener(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


setattr(commands_module, "Cog", _DummyCog)
setattr(commands_module, "Bot", object)
setattr(commands_module, "Context", object)
setattr(commands_module, "command", lambda *args, **kwargs: (lambda func: func))

ext_module = ModuleType("discord.ext")
setattr(ext_module, "commands", commands_module)

sys.modules.setdefault("discord", discord_module)
sys.modules.setdefault("discord.ext", ext_module)
sys.modules.setdefault("discord.ext.commands", commands_module)

holidays_module = ModuleType("holidays")
setattr(holidays_module, "country_holidays", lambda country: {})
sys.modules.setdefault("holidays", holidays_module)

discord_package = ModuleType("abby_core.discord")
config_module = ModuleType("abby_core.discord.config")


class _DummyBotConfig:
    def __init__(self):
        self.channels = SimpleNamespace(xp_channel=None, xp_abby_chat=None, abby_chat=None)
        self.emojis = SimpleNamespace(leaf_heart="<a:test_leaf_heart:1>")
        self.timing = SimpleNamespace(
            xp_message_cooldown_seconds=60,
            xp_attachment_cooldown_seconds=60,
        )


setattr(config_module, "BotConfig", _DummyBotConfig)
setattr(discord_package, "config", config_module)

sys.modules.setdefault("abby_core.discord", discord_package)
sys.modules.setdefault("abby_core.discord.config", config_module)

from abby_core.database.collections import guild_configuration


_XP_REWARDS_PATH = Path(__file__).resolve().parents[1] / "abby_core" / "discord" / "cogs" / "economy" / "xp_rewards.py"
_XP_REWARDS_SPEC = importlib.util.spec_from_file_location("tests.xp_rewards_under_test", _XP_REWARDS_PATH)
assert _XP_REWARDS_SPEC is not None and _XP_REWARDS_SPEC.loader is not None
xp_rewards = importlib.util.module_from_spec(_XP_REWARDS_SPEC)
_XP_REWARDS_SPEC.loader.exec_module(xp_rewards)


class _FakeUpdateResult:
    def __init__(self, matched_count=1, modified_count=1):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _FakeCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, query, update_doc, upsert=False):
        self.calls.append((query, update_doc, upsert))
        return _FakeUpdateResult(matched_count=1, modified_count=1)


class _FakeChannel:
    def __init__(self):
        self.sent_messages = []

    async def send(self, message):
        self.sent_messages.append(message)


class _FakeBot:
    def __init__(self):
        self.user = SimpleNamespace(id=999999, name="AbbyBot")
        self.guilds = []

    def get_guild(self, guild_id):
        return None


def test_store_daily_bonus_message_queries_legacy_and_current_guild_id_types(monkeypatch):
    fake_collection = _FakeCollection()
    monkeypatch.setattr(guild_configuration, "get_collection", lambda: fake_collection)

    ok = guild_configuration.store_daily_bonus_message(123, 456, datetime.now(timezone.utc))

    assert ok is True
    assert len(fake_collection.calls) == 1

    query, update_doc, upsert = fake_collection.calls[0]
    assert upsert is False
    assert query == {"guild_id": {"$in": ["123", 123]}}
    assert update_doc["$set"]["channels.xp.daily_bonus_current_message_id"] == 456


def test_handle_reaction_refreshes_stale_message_id_from_guild_config(monkeypatch):
    manager = xp_rewards.XPRewardManager(_FakeBot())
    guild = SimpleNamespace(id=123)
    channel = _FakeChannel()
    message = SimpleNamespace(
        id=222,
        guild=guild,
        author=SimpleNamespace(name="Abby", id=111),
        content="Here is the daily bonus message, react to earn +10 EXP!",
        channel=channel,
    )
    reaction = SimpleNamespace(emoji="❤️", message=message)
    user = SimpleNamespace(id=444, name="Tester", mention="@Tester")

    manager.daily_bonus_message_ids[guild.id] = 111

    monkeypatch.setattr(
        xp_rewards,
        "get_guild_config",
        lambda guild_id: {"channels": {"xp": {"daily_bonus_current_message_id": 222}}},
    )
    monkeypatch.setattr(xp_rewards, "ensure_user_from_discord", lambda user_obj, guild_obj: str(user_obj.id))
    monkeypatch.setattr(xp_rewards, "increment_xp", lambda user_id, amount, guild_id: False)
    monkeypatch.setattr(manager, "_has_used_daily_bonus_today", lambda user_id: False)
    monkeypatch.setattr(manager, "_record_daily_bonus_usage", lambda user_id: True)

    asyncio.run(manager.handle_reaction(reaction, user))

    assert manager.daily_bonus_message_ids[guild.id] == 222
    assert len(channel.sent_messages) == 1
    assert "earned +10 EXP" in channel.sent_messages[0]