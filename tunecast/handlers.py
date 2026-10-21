import asyncio
import logging
import re
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, TelegramObject

from . import ui
from .botmeta import set_commands
from .config import save_settings
from .emoji import KEYS, Emoji
from .i18n import LANGUAGES, set_lang, t
from .panel import Panel, rich
from .spotify import NoActiveDevice, PremiumRequired, Spotify, SpotifyError

log = logging.getLogger(__name__)

LINK_RE = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-z-]+/)?|spotify:)(track|album|playlist|artist)[/:]([A-Za-z0-9]{22})"
)


class LRU(OrderedDict):
    def __init__(self, size: int):
        super().__init__()
        self.size = size

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > self.size:
            self.popitem(last=False)


searches: LRU = LRU(50)  # message_id -> search query
track_names: LRU = LRU(500)  # track_id -> "Title — Artist"
emoji_waiting: dict[int, str] = {}  # chat_id -> icon key we are waiting an emoji for


class PremiumWatcher(BaseMiddleware):
    """Tracks whether the owner has Telegram Premium and switches emoji accordingly."""

    def __init__(self, emoji: Emoji, panel: Panel):
        self.emoji = emoji
        self.panel = panel

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and self.emoji.set_premium(user.is_premium):
            asyncio.create_task(self.panel.redraw())
        return await handler(event, data)


async def alert(cb: CallbackQuery, exc: SpotifyError) -> None:
    log.warning("Spotify: %s", exc)
    await cb.answer(t("t.spotify_error", msg=exc.message)[:200], show_alert=True)


async def send(message: Message, html: str) -> Message:
    return await message.bot.send_rich_message(message.chat.id, rich_message=rich(html))


async def run_action(cb: CallbackQuery, sp: Spotify, panel: Panel, action: Callable[[], Awaitable[None]]) -> bool:
    """Run a Spotify command. If no device is active, pick one."""
    try:
        try:
            await action()
            return True
        except NoActiveDevice:
            devices = [d for d in await sp.devices() if d.get("id") and not d.get("is_restricted")]
            if not devices:
                await cb.answer(t("t.no_devices"), show_alert=True)
                return False
            if len(devices) > 1:
                await cb.answer(t("t.pick_device"))
                if panel.message_id:
                    await panel.show("devices")
                else:
                    await panel.send_new(cb.message.chat.id, "devices")
                return False
            await sp.transfer(devices[0]["id"], play=False)
            await asyncio.sleep(1)
            await action()
            return True
    except PremiumRequired:
        await cb.answer(t("t.premium"), show_alert=True)
    except NoActiveDevice:
        await cb.answer(t("t.device_silent"), show_alert=True)
    except SpotifyError as exc:
        await alert(cb, exc)
    return False


def remember_tracks(items: list[dict]) -> None:
    for track in items:
        if track and track.get("id"):
            track_names[track["id"]] = f"{track['name']} — {ui.artists(track)}"


def build_router(allowed_ids: frozenset[int]) -> Router:
    router = Router()
    router.message.filter(F.from_user.id.in_(allowed_ids))
    router.callback_query.filter(F.from_user.id.in_(allowed_ids))

    # ---------- commands ----------

    async def open_panel(message: Message, panel: Panel, view: str) -> None:
        try:
            await panel.send_new(message.chat.id, view)
        except SpotifyError as exc:
            await message.answer(t("t.spotify_error", msg=exc.message))
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    @router.message(CommandStart())
    @router.message(Command("player"))
    async def cmd_start(message: Message, panel: Panel):
        await open_panel(message, panel, "player")

    @router.message(Command("queue"))
    async def cmd_queue(message: Message, panel: Panel):
        await open_panel(message, panel, "queue")

    @router.message(Command("playlists"))
    async def cmd_playlists(message: Message, panel: Panel):
        panel.playlist_page = 0
        await open_panel(message, panel, "playlists")

    @router.message(Command("devices"))
    async def cmd_devices(message: Message, panel: Panel):
        await open_panel(message, panel, "devices")

    @router.message(Command("help"))
    async def cmd_help(message: Message, emoji: Emoji):
        await send(message, ui.help_view(emoji))

    @router.message(Command("emoji"))
    async def cmd_emoji(message: Message, emoji: Emoji):
        emoji_waiting.pop(message.chat.id, None)
        await send(message, ui.emoji_view(emoji, KEYS))

    @router.message(Command("language", "lang"))
    async def cmd_language(message: Message, emoji: Emoji):
        await send(message, ui.language_view(emoji))
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    # ---------- emoji replacement ----------

    @router.message(lambda m: m.chat.id in emoji_waiting)
    async def on_emoji(message: Message, emoji: Emoji, panel: Panel):
        key = emoji_waiting.pop(message.chat.id)
        custom = next((ent for ent in message.entities or [] if ent.type == "custom_emoji"), None)
        text = message.text or ""
        if custom:
            emoji.set_override(key, custom.custom_emoji_id, custom.extract_from(text))
        elif text.strip() and len(text.strip()) <= 8:
            emoji.set_override(key, None, text.strip())
        else:
            await message.answer(t("emoji.not_emoji"))
            return
        await send(message, ui.emoji_view(emoji, KEYS))
        await panel.redraw()

    # ---------- text: a link or a search ----------

    @router.message(F.text & ~F.text.startswith("/"))
    async def on_text(message: Message, sp: Spotify, emoji: Emoji):
        text = message.text.strip()
        try:
            found = LINK_RE.search(text)
            if found:
                await send_link_card(message, sp, emoji, found.group(1), found.group(2))
                return
            result = await sp.search_tracks(text)
            remember_tracks(result.get("items") or [])
            sent = await send(message, ui.search_view(emoji, text, result, 0))
            searches[sent.message_id] = text
        except SpotifyError as exc:
            await message.answer(t("t.spotify_error", msg=exc.message))

    async def send_link_card(message: Message, sp: Spotify, emoji: Emoji, kind: str, item_id: str) -> None:
        if kind == "track":
            track = await sp.track(item_id)
            remember_tracks([track])
            html = ui.track_card(emoji, track)
        else:
            obj = await getattr(sp, kind)(item_id)
            html = ui.context_card(emoji, kind, obj, closable=True)
        await send(message, html)

    # ---------- player buttons ----------

    @router.callback_query(F.data.startswith("p:"))
    async def cb_player(cb: CallbackQuery, sp: Spotify, panel: Panel):
        parts = cb.data.split(":")
        name = parts[1]

        if name == "refresh":
            await cb.answer(t("t.refreshed"))
            await panel.show("player", cb.message)
            return

        try:
            pb = await sp.playback() if name in ("toggle", "shuffle", "repeat", "vol") else panel.pb
        except SpotifyError as exc:
            await alert(cb, exc)
            return
        toast = ""

        async def action():
            nonlocal toast
            if name == "toggle":
                if pb and pb.get("is_playing"):
                    await sp.pause()
                    toast = t("t.paused")
                else:
                    await sp.play()
                    toast = t("t.playing")
            elif name == "next":
                await sp.next()
                toast = t("t.next")
            elif name == "prev":
                await sp.previous()
                toast = t("t.prev")
            elif name == "shuffle":
                state = not (pb or {}).get("shuffle_state")
                await sp.shuffle(state)
                toast = t("t.shuffle_on") if state else t("t.shuffle_off")
            elif name == "repeat":
                state = ui.REPEAT_NEXT.get((pb or {}).get("repeat_state", "off"), "off")
                await sp.repeat(state)
                toast = t(f"t.repeat_{state}")
            elif name == "vol":
                current = ((pb or {}).get("device") or {}).get("volume_percent")
                if current is None:
                    raise SpotifyError(0, t("t.no_volume"))
                volume = max(0, min(100, current + int(parts[2])))
                await sp.volume(volume)
                toast = t("t.volume", v=volume)

        if not await run_action(cb, sp, panel, action):
            return
        await cb.answer(toast)
        await asyncio.sleep(0.6)  # Spotify applies commands with a delay
        await panel.show(panel.view if panel.view in ("player", "queue") else "player", cb.message)
        panel.refresh_soon()

    # ---------- panel navigation ----------

    @router.callback_query(F.data.startswith("v:"))
    async def cb_view(cb: CallbackQuery, panel: Panel):
        parts = cb.data.split(":")
        try:
            if parts[1] == "new":
                await panel.send_new(cb.message.chat.id)
            elif parts[1] == "player":
                await panel.show("player", cb.message)
            elif parts[1] == "queue":
                await panel.show("queue", cb.message)
            elif parts[1] == "dev":
                await panel.show("devices", cb.message)
            elif parts[1] == "pl":
                await panel.show("playlists", cb.message, page=int(parts[2]))
            await cb.answer()
        except SpotifyError as exc:
            await alert(cb, exc)

    @router.callback_query(F.data.startswith("pl:"))
    async def cb_playlist(cb: CallbackQuery, panel: Panel):
        try:
            await panel.show("playlist", cb.message, playlist_id=cb.data[3:])
            await cb.answer()
        except SpotifyError as exc:
            await alert(cb, exc)

    # ---------- playing playlists, albums, artists ----------

    @router.callback_query(F.data.startswith("c:"))
    async def cb_context(cb: CallbackQuery, sp: Spotify, panel: Panel):
        _, mode, kind, item_id = cb.data.split(":", 3)
        shuffle = mode == "s"

        async def action():
            await sp.shuffle(shuffle)
            await sp.play(context_uri=f"spotify:{kind}:{item_id}")

        if not await run_action(cb, sp, panel, action):
            return
        await cb.answer(t("t.shuffled") if shuffle else t("t.go"))
        await after_play(cb, panel)

    @router.callback_query(F.data == "lk")
    async def cb_liked(cb: CallbackQuery, sp: Spotify, panel: Panel):
        try:
            tracks = await sp.liked_tracks(50)
        except SpotifyError as exc:
            await alert(cb, exc)
            return
        uris = [x["uri"] for x in tracks if x.get("uri") and not x.get("is_local")]
        if not uris:
            await cb.answer(t("t.liked_empty"), show_alert=True)
            return
        if not await run_action(cb, sp, panel, lambda: sp.play(uris=uris)):
            return
        await cb.answer(t("t.liked_playing"))
        await after_play(cb, panel)

    async def after_play(cb: CallbackQuery, panel: Panel) -> None:
        await asyncio.sleep(0.8)
        # The button could be on the panel or on a separate card from a link
        if cb.message.message_id == panel.message_id:
            await panel.show("player", cb.message)
        elif panel.message_id:
            await panel.show("player")
        panel.refresh_soon()

    # ---------- devices ----------

    @router.callback_query(F.data.startswith("dev:"))
    async def cb_device(cb: CallbackQuery, sp: Spotify, panel: Panel):
        try:
            await sp.transfer(cb.data[4:], play=True)
        except SpotifyError as exc:
            await alert(cb, exc)
            return
        await cb.answer(t("t.switching"))
        await asyncio.sleep(1.2)
        await panel.show("player", cb.message)
        panel.refresh_soon()

    # ---------- search and tracks ----------

    @router.callback_query(F.data.startswith("s:"))
    async def cb_search(cb: CallbackQuery, sp: Spotify, emoji: Emoji):
        parts = cb.data.split(":")
        if parts[1] == "x":
            emoji_waiting.pop(cb.message.chat.id, None)
            try:
                await cb.message.delete()
            except TelegramBadRequest:
                pass
            await cb.answer()
            return
        query = searches.get(cb.message.message_id)
        if not query:
            await cb.answer(t("t.search_expired"), show_alert=True)
            return
        offset = int(parts[2])
        try:
            result = await sp.search_tracks(query, offset=offset)
        except SpotifyError as exc:
            await alert(cb, exc)
            return
        remember_tracks(result.get("items") or [])
        await cb.message.edit_text(rich_message=rich(ui.search_view(emoji, query, result, offset)))
        await cb.answer()

    @router.callback_query(F.data.startswith("t:"))
    async def cb_track(cb: CallbackQuery, sp: Spotify, panel: Panel):
        _, mode, track_id = cb.data.split(":", 2)
        uri = f"spotify:track:{track_id}"
        name = track_names.get(track_id, t("t.track"))

        if mode == "add":
            if not await run_action(cb, sp, panel, lambda: sp.add_to_queue(uri)):
                return
            await cb.answer(t("t.queued", name=name)[:200])
            if panel.view == "queue":
                await asyncio.sleep(0.6)
                await panel.show("queue")
        else:
            if not await run_action(cb, sp, panel, lambda: sp.play(uris=[uri])):
                return
            await cb.answer(f"▶️ {name}"[:200])
            await asyncio.sleep(0.8)
            if panel.message_id:
                await panel.show("player")
            panel.refresh_soon()

    # ---------- emoji settings ----------

    @router.callback_query(F.data.startswith("em:"))
    async def cb_emoji(cb: CallbackQuery, emoji: Emoji, panel: Panel):
        _, action, key = cb.data.split(":", 2)
        if action == "set":
            emoji_waiting[cb.message.chat.id] = key
            await cb.answer(t("emoji.send_for", label=t("label." + key)))
            await cb.message.edit_text(rich_message=rich(ui.emoji_view(emoji, KEYS, waiting=key)))
            return
        emoji.reset_override(None if key == "*" else key)
        await cb.answer(t("emoji.reset_done"))
        await cb.message.edit_text(rich_message=rich(ui.emoji_view(emoji, KEYS)))
        await panel.redraw()

    # ---------- language ----------

    @router.callback_query(F.data.startswith("lang:"))
    async def cb_language(cb: CallbackQuery, bot: Bot, emoji: Emoji, panel: Panel):
        code = cb.data.split(":", 1)[1]
        if code not in LANGUAGES:
            await cb.answer()
            return
        set_lang(code)
        save_settings({"LANGUAGE": code})
        await cb.answer(t("lang.set"))
        try:
            await cb.message.edit_text(rich_message=rich(ui.language_view(emoji)))
        except TelegramBadRequest:
            pass
        await set_commands(bot)
        await panel.redraw()

    @router.callback_query(F.data == "noop")
    async def cb_noop(cb: CallbackQuery):
        await cb.answer()

    return router
