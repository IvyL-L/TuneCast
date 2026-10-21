"""Запуск TuneCast: мастер настройки при первом запуске, затем бот."""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BotCommand, LinkPreviewOptions
from rich.logging import RichHandler
from rich.panel import Panel

from . import __version__
from .config import APP_NAME, DATA, DESCRIPTION, is_configured, load_config
from .emoji import Emoji
from .handlers import PremiumWatcher, build_router
from .panel import Panel as PlayerPanel
from .setup import GREEN, console, run_wizard
from .spotify import Spotify
from .storage import Store

log = logging.getLogger("tunecast")


async def sync_emoji(bot: Bot, emoji: Emoji, panel: PlayerPanel, owner_id: int) -> None:
    """Создать паки эмодзи в фоне. Telegram ограничивает частоту, поэтому повторяем."""
    while True:
        try:
            before = dict(emoji.ids)
            await emoji.sync_packs(bot, owner_id)
            if emoji.ids != before and emoji.premium:
                await panel.redraw()
            return
        except TelegramRetryAfter as exc:
            log.info("Эмодзи: Telegram просит подождать %s с, продолжу сам", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 2)
        except Exception:
            log.exception("Эмодзи: не удалось создать паки, пока будут обычные эмодзи")
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

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="🎧 Плеер"),
            BotCommand(command="queue", description="📜 Очередь"),
            BotCommand(command="playlists", description="📚 Плейлисты"),
            BotCommand(command="devices", description="📱 Устройства"),
            BotCommand(command="emoji", description="✨ Свои эмодзи"),
            BotCommand(command="help", description="❓ Помощь"),
        ]
    )
    bot_me = await bot.get_me()
    console.print()
    console.print(
        Panel(
            f"[bold {GREEN}]{APP_NAME} работает[/]  ·  бот [bold]@{bot_me.username}[/]\n\n"
            f"Напиши боту [bold]/start[/]: https://t.me/{bot_me.username}\n"
            f"Трек в профиле: {'[green]включён[/]' if profile else '[dim]выключен[/]'}\n\n"
            "[dim]Бот работает, пока открыто это окно. Остановить: закрыть окно или Ctrl+C[/]",
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
    frozen = getattr(sys, "frozen", False)

    def pause() -> None:
        # Окно exe закрывается сразу после выхода — даём прочитать сообщение
        if frozen:
            try:
                input("Нажми Enter, чтобы закрыть окно…")
            except (EOFError, KeyboardInterrupt):
                pass

    try:
        console.print(f"[bold {GREEN}]{APP_NAME}[/] [dim]{__version__} · {DESCRIPTION}[/]")
        if "--setup" in args or not is_configured():
            try:
                run_wizard()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Настройка прервана.[/] Уже введённое сохранено, при следующем запуске "
                              "мастер продолжит с этими значениями.")
                pause()
                return
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        console.print("\n[dim]TuneCast остановлен[/]")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            if isinstance(exc.code, str):
                console.print(f"[red]{exc.code}[/]")
            pause()
        raise
    except Exception:
        console.print_exception()
        console.print("[red]TuneCast остановился из-за ошибки выше.[/] Если не получается разобраться, "
                      "создай issue на GitHub и приложи текст ошибки (без ключей!).")
        pause()
        sys.exit(1)
