"""TuneCast entry point: the setup wizard on first run, then the bot."""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import LinkPreviewOptions
from rich.logging import RichHandler
from rich.panel import Panel

from . import __version__
from .botmeta import set_commands, set_profile
from .config import APP_NAME, DATA, is_configured, load_config, reload_settings
from .emoji import Emoji
from .handlers import PremiumWatcher, build_router
from .i18n import t
from .panel import Panel as PlayerPanel
from .setup import GREEN, console, run_wizard
from .spotify import Spotify
from .storage import Store

log = logging.getLogger("tunecast")


async def sync_emoji(bot: Bot, emoji: Emoji, panel: PlayerPanel, owner_id: int) -> None:
    """Create the emoji packs in the background. Telegram rate-limits this, so keep retrying."""
    while True:
        try:
            before = dict(emoji.ids)
            await emoji.sync_packs(bot, owner_id)
            if emoji.ids != before and emoji.premium:
                await panel.redraw()
            return
        except TelegramRetryAfter as exc:
            log.info("Emoji: Telegram asks to wait %s s, will continue automatically", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 2)
        except Exception:
            log.exception("Emoji: could not create the packs, regular emoji will be used for now")
            return


async def run_bot() -> None:
    cfg = load_config()
    store = Store(DATA / "state.json")

    sp = Spotify(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_redirect_uri, DATA / "spotify_token.json")
    await sp.ensure_auth()
    me = await sp.me()
    log.info("Spotify: %s", me.get("display_name") or me.get("id"))

    profile = None
    if cfg.profile_enabled:
        from .profile_music import ProfileMusic

        profile = ProfileMusic(
            cfg.tg_api_id, cfg.tg_api_hash, str(DATA / "telegram_user"), store,
            cfg.profile_clear_after, cfg.profile_clear_on_exit,
        )
        if not await profile.start():
            profile = None

    bot = Bot(
        cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview=LinkPreviewOptions(is_disabled=True)),
    )
    emoji = Emoji(store)
    panel = PlayerPanel(
        bot, sp, store, emoji, cfg.poll_interval, cfg.panel_refresh, on_playback=profile.update if profile else None
    )

    dp = Dispatcher(sp=sp, panel=panel, emoji=emoji)
    watcher = PremiumWatcher(emoji, panel)
    dp.message.outer_middleware(watcher)
    dp.callback_query.outer_middleware(watcher)
    dp.include_router(build_router(cfg.allowed_ids))

    await set_commands(bot)
    await set_profile(bot)
    bot_me = await bot.get_me()
    console.print()
    console.print(
        Panel(
            f"[bold {GREEN}]{t('run.title', app=APP_NAME)}[/]  ·  {t('run.bot')} [bold]@{bot_me.username}[/]\n\n"
            f"{t('run.write_start')}: https://t.me/{bot_me.username}\n"
            f"{t('run.profile')}: {'[green]' + t('run.on') + '[/]' if profile else '[dim]' + t('run.off') + '[/]'}\n\n"
            f"[dim]{t('run.hint')}[/]",
            border_style=GREEN,
            padding=(1, 2),
        )
    )

    tasks = [
        asyncio.create_task(panel.run()),
        asyncio.create_task(sync_emoji(bot, emoji, panel, min(cfg.allowed_ids))),
    ]
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        for task in tasks:
            task.cancel()
        if profile:
            await profile.stop()
        await sp.close()
        await bot.session.close()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(console=console, show_path=False, markup=False, rich_tracebacks=True)],
    )
    for name in ("aiogram.event", "aiogram.dispatcher", "httpx", "telethon"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    if sys.platform == "win32":
        os.system(f"title {APP_NAME}")
    args = set(sys.argv[1:])
    if "--version" in args:
        print(f"{APP_NAME} {__version__}")
        return
    setup_logging()
    reload_settings()  # picks up the saved language
    frozen = getattr(sys, "frozen", False)

    def pause() -> None:
        # The exe window closes right after exit — give the user a chance to read the message
        if frozen:
            try:
                input(t("run.press_enter"))
            except (EOFError, KeyboardInterrupt):
                pass

    try:
        console.print(f"[bold {GREEN}]{APP_NAME}[/] [dim]{__version__} · {t('app.tagline')}[/]")
        if "--setup" in args or not is_configured():
            try:
                run_wizard()
            except (EOFError, KeyboardInterrupt):
                console.print(f"\n[yellow]{t('run.setup_interrupted')}[/]")
                pause()
                return
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        console.print(f"\n[dim]{t('run.stopped')}[/]")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            if isinstance(exc.code, str):
                console.print(f"[red]{exc.code}[/]")
            pause()
        raise
    except Exception:
        console.print_exception()
        console.print(f"[red]{t('run.crashed')}[/]")
        pause()
        sys.exit(1)
