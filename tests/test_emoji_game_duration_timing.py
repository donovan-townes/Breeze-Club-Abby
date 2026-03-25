import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


# --- Minimal stubs required to import games.py in isolation ---
discord_module = ModuleType("discord")


class _DummyColor:
    @staticmethod
    def blue():
        return 0

    @staticmethod
    def green():
        return 1


class _DummyEmbed:
    def __init__(self, title=None, description=None, color=None):
        self.title = title
        self.description = description
        self.color = color
        self.fields = []
        self.footer = None

    def add_field(self, name, value, inline=False):
        self.fields.append({"name": name, "value": value, "inline": inline})

    def set_footer(self, text=None):
        self.footer = SimpleNamespace(text=text)


class _DummyTextChannel:
    pass


class _DummyUser:
    def __init__(self, user_id=1, mention="@user", display_name="user"):
        self.id = user_id
        self.mention = mention
        self.display_name = display_name


setattr(discord_module, "Embed", _DummyEmbed)
setattr(discord_module, "Color", _DummyColor)
setattr(discord_module, "TextChannel", _DummyTextChannel)
setattr(discord_module, "User", _DummyUser)
setattr(discord_module, "Member", _DummyUser)
setattr(discord_module, "Message", object)
setattr(discord_module, "Interaction", object)
setattr(discord_module, "ButtonStyle", SimpleNamespace(primary=1, secondary=2))


app_commands_module = ModuleType("discord.app_commands")
setattr(app_commands_module, "command", lambda *args, **kwargs: (lambda func: func))
setattr(discord_module, "app_commands", app_commands_module)


class _DummyView:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.children = []

    def add_item(self, item):
        self.children.append(item)

    @classmethod
    def button(cls, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class _DummyButton:
    def __init__(self, style=None, emoji=None, custom_id=None):
        self.style = style
        self.emoji = emoji
        self.custom_id = custom_id
        self.callback = None
        self.disabled = False


ui_module = ModuleType("discord.ui")
setattr(ui_module, "View", _DummyView)
setattr(ui_module, "Button", _DummyButton)
setattr(ui_module, "button", lambda *args, **kwargs: (lambda func: func))
setattr(discord_module, "ui", ui_module)


commands_module = ModuleType("discord.ext.commands")


class _DummyCog:
    pass


setattr(commands_module, "Cog", _DummyCog)
setattr(commands_module, "Bot", object)


ext_module = ModuleType("discord.ext")
setattr(ext_module, "commands", commands_module)
setattr(ext_module, "tasks", ModuleType("discord.ext.tasks"))

existing_discord_module = sys.modules.setdefault("discord", discord_module)
if not hasattr(existing_discord_module, "ui"):
    setattr(existing_discord_module, "ui", ui_module)
if not hasattr(existing_discord_module, "app_commands"):
    setattr(existing_discord_module, "app_commands", app_commands_module)
if not hasattr(existing_discord_module, "ButtonStyle"):
    setattr(existing_discord_module, "ButtonStyle", SimpleNamespace(primary=1, secondary=2))
if not hasattr(existing_discord_module, "Embed"):
    setattr(existing_discord_module, "Embed", _DummyEmbed)
if not hasattr(existing_discord_module, "Color"):
    setattr(existing_discord_module, "Color", _DummyColor)
if not hasattr(existing_discord_module, "TextChannel"):
    setattr(existing_discord_module, "TextChannel", _DummyTextChannel)
if not hasattr(existing_discord_module, "User"):
    setattr(existing_discord_module, "User", _DummyUser)
if not hasattr(existing_discord_module, "Member"):
    setattr(existing_discord_module, "Member", _DummyUser)
if not hasattr(existing_discord_module, "Interaction"):
    setattr(existing_discord_module, "Interaction", object)

sys.modules.setdefault("discord.app_commands", app_commands_module)
sys.modules.setdefault("discord.ui", ui_module)
existing_ext_module = sys.modules.setdefault("discord.ext", ext_module)
if not hasattr(existing_ext_module, "commands"):
    setattr(existing_ext_module, "commands", commands_module)
if not hasattr(existing_ext_module, "tasks"):
    setattr(existing_ext_module, "tasks", ModuleType("discord.ext.tasks"))
sys.modules.setdefault("discord.ext.tasks", getattr(existing_ext_module, "tasks"))
sys.modules.setdefault("discord.ext.commands", commands_module)


logging_module = ModuleType("tdos_intelligence.observability.logging")
setattr(logging_module, "getLogger", lambda name: SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None))

observability_module = ModuleType("tdos_intelligence.observability")
setattr(observability_module, "logging", logging_module)

sys.modules.setdefault("tdos_intelligence.observability", observability_module)
sys.modules.setdefault("tdos_intelligence.observability.logging", logging_module)


discord_package = ModuleType("abby_core.discord")
config_module = ModuleType("abby_core.discord.config")


class _DummyBotConfig:
    def __init__(self):
        self.channels = SimpleNamespace(breeze_lounge=123)
        self.server_info = SimpleNamespace(guild_id=999)


setattr(config_module, "BotConfig", _DummyBotConfig)
setattr(discord_package, "config", config_module)

sys.modules.setdefault("abby_core.discord", discord_package)
sys.modules.setdefault("abby_core.discord.config", config_module)


xp_module = ModuleType("abby_core.economy.xp")
setattr(xp_module, "increment_xp", lambda *args, **kwargs: True)
sys.modules.setdefault("abby_core.economy.xp", xp_module)


xp_rewards_module = ModuleType("abby_core.discord.cogs.economy.xp_rewards")
setattr(xp_rewards_module, "current_xp_multiplier", lambda: (1, None))
sys.modules.setdefault("abby_core.discord.cogs.economy.xp_rewards", xp_rewards_module)


leveling_module = ModuleType("abby_core.economy.leveling")
setattr(leveling_module, "record_game_result", lambda *args, **kwargs: None)
sys.modules.setdefault("abby_core.economy.leveling", leveling_module)


guild_config_module = ModuleType("abby_core.database.collections.guild_configuration")
setattr(guild_config_module, "get_guild_config", lambda guild_id: {})
setattr(guild_config_module, "get_memory_settings", lambda guild_id: {})
setattr(guild_config_module, "set_memory_settings", lambda guild_id, data: True)
sys.modules.setdefault("abby_core.database.collections.guild_configuration", guild_config_module)


_GAMES_PATH = Path(__file__).resolve().parents[1] / "abby_core" / "discord" / "cogs" / "entertainment" / "games.py"
_GAMES_SPEC = importlib.util.spec_from_file_location("tests.games_under_test", _GAMES_PATH)
assert _GAMES_SPEC is not None and _GAMES_SPEC.loader is not None
games = importlib.util.module_from_spec(_GAMES_SPEC)
_GAMES_SPEC.loader.exec_module(games)


class _FakeMessage:
    def __init__(self, embed, view):
        self.embeds = [embed]
        self.view = view

    async def edit(self, embed=None, view=None):
        if embed is not None:
            self.embeds = [embed]
        if view is not None:
            self.view = view


class _FakeChannel(_DummyTextChannel):
    def __init__(self):
        self.guild = SimpleNamespace(id=123)
        self.sent = []

    async def send(self, content=None, embed=None, view=None, delete_after=None):
        self.sent.append({"content": content, "embed": embed, "view": view, "delete_after": delete_after})
        if embed is not None:
            return _FakeMessage(embed, view)
        return SimpleNamespace(delete=lambda: None)


class _FakeBot:
    pass


def test_scheduled_game_uses_full_duration_countdown_loop(monkeypatch):
    if not hasattr(games.config, "channels"):
        games.config.channels = SimpleNamespace()
    if not hasattr(games.config.channels, "breeze_lounge"):
        games.config.channels.breeze_lounge = 123
    if not hasattr(games.config, "server_info"):
        games.config.server_info = SimpleNamespace()
    if not hasattr(games.config.server_info, "guild_id"):
        games.config.server_info.guild_id = 999

    manager = games.GamesManager(_FakeBot())
    channel = _FakeChannel()

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(games.asyncio, "sleep", _fake_sleep)

    asyncio.run(manager._run_game(channel, starter=None, duration_minutes=15))

    assert sleep_calls, "expected countdown sleep calls"
    assert sleep_calls[0] == 5, "game should enter 5-second countdown loop first"
