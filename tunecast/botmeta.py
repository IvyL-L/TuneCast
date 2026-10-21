"""Bot command menu and profile texts in the selected language."""

from aiogram import Bot
from aiogram.types import BotCommand

from .i18n import LANGUAGES, lang, set_lang, t

COMMANDS = ("start", "queue", "playlists", "devices", "emoji", "language", "help")


async def set_commands(bot: Bot) -> None:
    """The command menu follows the language chosen in the bot."""
    await bot.set_my_commands([BotCommand(command=c, description=t(f"cmd.{c}")) for c in COMMANDS])


async def set_profile(bot: Bot) -> None:
    """Description shown before /start: English by default, Russian for Russian-language Telegram apps."""
    current = lang()
    try:
        for code in LANGUAGES:
            set_lang(code)
            language_code = None if code == "en" else code
            await bot.set_my_short_description(short_description=t("app.tagline"), language_code=language_code)
            await bot.set_my_description(description=t("bot.description"), language_code=language_code)
    finally:
        set_lang(current)
