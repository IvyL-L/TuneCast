"""Панель плеера: одно Rich Message, которое бот редактирует на месте."""

import asyncio
import logging
import time
from collections.abc import Callable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputRichMessage, Message

from . import ui
from .emoji import Emoji
from .spotify import Spotify, SpotifyError
from .storage import Store

log = logging.getLogger(__name__)


def rich(html: str) -> InputRichMessage:
    return InputRichMessage(html=html, skip_entity_detection=True)


class Panel:
    def __init__(
        self,
        bot: Bot,
        sp: Spotify,
        store: Store,
        emoji: Emoji,
        poll_interval: float,
        refresh_interval: float,
        on_playback: Callable[[dict | None], None] | None = None,
    ):
        self.bot = bot
        self.sp = sp
        self.store = store
        self.e = emoji
        self.poll_interval = poll_interval
        self.refresh_interval = refresh_interval
        self.on_playback = on_playback

        self.chat_id: int | None = store.get("panel_chat_id")
        self.message_id: int | None = store.get("panel_message_id")
        self.view = "player"
        self.playlist_page = 0
        self.pb: dict | None = None

        self._html: str | None = None
        self._signature: tuple | None = None
        self._last_edit = 0.0
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._context_names: dict[str, str | None] = {}

    # ---------- публичное ----------

    async def send_new(self, chat_id: int, view: str = "player", **kwargs) -> None:
        """Отправить свежую панель вниз чата, старую удалить."""
        async with self._lock:
            old = (self.chat_id, self.message_id)
            self.view = view
            html = await self._build(view, **kwargs)
            msg = await self.bot.send_rich_message(chat_id, rich_message=rich(html))
            self._remember(html)
            self.chat_id, self.message_id = chat_id, msg.message_id
            self.store.set(panel_chat_id=chat_id, panel_message_id=msg.message_id)
        if old[1] and old != (chat_id, self.message_id):
            try:
                await self.bot.delete_message(old[0], old[1])
            except TelegramBadRequest:
                pass

    async def show(self, view: str, message: Message | None = None, **kwargs) -> None:
        """Перерисовать панель в другом режиме (плеер, очередь, плейлисты…)."""
        if message is not None and (message.chat.id, message.message_id) != (self.chat_id, self.message_id):
            # Нажали кнопку на старой панели: делаем её текущей
            self.chat_id, self.message_id = message.chat.id, message.message_id
            self.store.set(panel_chat_id=self.chat_id, panel_message_id=self.message_id)
            self._html = None
        if not self.message_id:
            return
        async with self._lock:
            self.view = view
            html = await self._build(view, **kwargs)
            if not await self._edit(html):
                # Старую панель (например, фото из прошлой версии) отредактировать нельзя
                chat_id, old_id = self.chat_id, self.message_id
                msg = await self.bot.send_rich_message(chat_id, rich_message=rich(html))
                self.message_id = msg.message_id
                self.store.set(panel_message_id=msg.message_id)
                self._remember(html)
                try:
                    await self.bot.delete_message(chat_id, old_id)
                except TelegramBadRequest:
                    pass

    async def redraw(self) -> None:
        """Перерисовать текущий экран (например, после смены эмодзи)."""
        if self.message_id:
            await self.show(self.view)

    def refresh_soon(self, delay: float = 1.5) -> None:
        """Попросить фоновый цикл проверить Spotify пораньше (состояние обновляется с задержкой)."""

        async def wake():
            await asyncio.sleep(delay)
            self._wake.set()

        asyncio.create_task(wake())

    async def run(self) -> None:
        """Фоновый цикл: следит за Spotify, обновляет панель и профиль."""
        while True:
            try:
                pb = await self.sp.playback()
                self._set_playback(pb)
                await self._auto_update(pb)
            except SpotifyError as exc:
                log.warning("Spotify: %s", exc)
            except Exception:
                log.exception("Ошибка в фоновом цикле")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.poll_interval)
            except TimeoutError:
                pass
            self._wake.clear()

    # ---------- внутреннее ----------

    def _set_playback(self, pb: dict | None) -> None:
        self.pb = pb
        if self.on_playback:
            try:
                self.on_playback(pb)
            except Exception:
                log.exception("Ошибка обработчика профиля")

    async def _auto_update(self, pb: dict | None) -> None:
        if not self.message_id or self.view != "player" or self._lock.locked():
            return
        signature = ui.player_signature(pb)
        playing = bool(pb and pb.get("is_playing"))
        due = playing and time.monotonic() - self._last_edit >= self.refresh_interval
        if signature == self._signature and not due:
            return
        async with self._lock:
            if self.view != "player":
                return
            self._signature = signature
            await self._edit(ui.player_view(self.e, pb, await self._context_label(pb)))

    async def _build(self, view: str, **kwargs) -> str:
        if view == "player":
            pb = await self.sp.playback()
            self._set_playback(pb)
            self._signature = ui.player_signature(pb)
            return ui.player_view(self.e, pb, await self._context_label(pb))
        if view == "queue":
            return ui.queue_view(self.e, await self.sp.queue())
        if view == "playlists":
            self.playlist_page = max(0, kwargs.get("page", self.playlist_page))
            data = await self.sp.my_playlists(
                offset=self.playlist_page * ui.PLAYLISTS_PER_PAGE, limit=ui.PLAYLISTS_PER_PAGE
            )
            return ui.playlists_view(self.e, data, self.playlist_page)
        if view == "playlist":
            pl = await self.sp.playlist(kwargs["playlist_id"])
            return ui.context_card(self.e, "playlist", pl, back=f"v:pl:{self.playlist_page}")
        if view == "devices":
            return ui.devices_view(self.e, await self.sp.devices())
        raise ValueError(view)

    def _remember(self, html: str) -> None:
        self._html = html
        self._last_edit = time.monotonic()

    async def _edit(self, html: str) -> bool:
        """True — панель на месте (изменена или не требовала изменений)."""
        if html == self._html:
            return True
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id, message_id=self.message_id, rich_message=rich(html)
            )
            self._remember(html)
            return True
        except TelegramBadRequest as exc:
            text = str(exc).lower()
            if "not modified" in text:
                self._remember(html)
                return True
            if "not found" in text or "can't be edited" in text or "message to edit" in text:
                log.info("Панель недоступна для редактирования (%s)", exc.message)
                return False
            if "there is no text in the message" in text or "rich" in text:
                return False
            raise

    async def _context_label(self, pb: dict | None) -> str | None:
        context = (pb or {}).get("context") or {}
        uri, kind = context.get("uri"), context.get("type")
        if not uri:
            return None
        if kind == "collection" or uri.endswith(":collection"):
            return "Любимые треки"
        if kind == "album":
            return None  # альбом уже показан под названием
        if uri in self._context_names:
            return self._context_names[uri]
        label = None
        try:
            item_id = uri.rsplit(":", 1)[-1]
            if kind == "playlist":
                label = (await self.sp.playlist(item_id)).get("name")
            elif kind == "artist":
                label = (await self.sp.artist(item_id)).get("name")
        except SpotifyError:
            label = None
        self._context_names[uri] = label
        return label
