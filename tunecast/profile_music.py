"""Shows the current track in the Telegram profile's music section.

Spotify doesn't provide audio files, so a silent MP3 of the right length with
the current title, artist and cover is uploaded to the profile. The
"♪ Track — Artist" bar in the profile shows exactly that.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
from telethon import TelegramClient, errors
from telethon.tl import functions, types

from . import ui
from .i18n import t
from .audio import silent_mp3
from .storage import Store

log = logging.getLogger(__name__)

DEBOUNCE = 3  # don't spam Telegram while tracks are skipped quickly


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    performer: str
    duration: int
    cover: str | None


class ProfileMusic:
    def __init__(self, api_id: int, api_hash: str, session_path: str, store: Store, clear_after: float, clear_on_exit: bool):
        self.client = TelegramClient(session_path, api_id, api_hash)
        self.store = store
        self.clear_after = clear_after
        self.clear_on_exit = clear_on_exit

        self._desired: Track | None = None
        self._current: Track | None = None
        self._current_doc: types.InputDocument | None = None
        self._idle_since: float | None = None
        self._event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._http = httpx.AsyncClient(timeout=15)
        self._use_saved_messages = bool(store.get("profile_use_saved_messages"))

    async def start(self) -> bool:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            log.warning("Profile: Telegram account not connected. Run TuneCast.exe --setup and complete the profile track step.")
            await self.client.disconnect()
            return False
        me = await self.client.get_me()
        log.info("Profile: connected as %s", me.first_name)

        # If the last run crashed, remove the leftover track
        leftover = self.store.get("profile_doc")
        if leftover:
            await self._unsave(self._load_doc(leftover))
            await self._delete_saved_message()
            self.store.set(profile_doc=None)

        self._task = asyncio.create_task(self._worker())
        return True

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        try:
            if self.clear_on_exit and self._current_doc:
                await self._unsave(self._current_doc)
                await self._delete_saved_message()
                self.store.set(profile_doc=None)
        finally:
            await self._http.aclose()
            await self.client.disconnect()

    def update(self, pb: dict | None) -> None:
        """Called by the panel's background loop on every Spotify poll."""
        item = (pb or {}).get("item")
        if pb and pb.get("is_playing") and item and item.get("id"):
            self._idle_since = None
            if self._desired is None or self._desired.id != item["id"]:
                self._desired = Track(
                    id=item["id"],
                    title=item.get("name") or t("untitled"),
                    performer=ui.artists(item),
                    duration=max(1, (item.get("duration_ms") or 0) // 1000),
                    cover=ui.item_image(item, small=True),
                )
                self._event.set()
            return

        now = time.monotonic()
        if self._idle_since is None:
            self._idle_since = now
        if self._desired is not None and self.clear_after > 0 and now - self._idle_since >= self.clear_after:
            self._desired = None
            self._event.set()

    # ---------- internals ----------

    async def _worker(self) -> None:
        while True:
            await self._event.wait()
            await asyncio.sleep(DEBOUNCE)
            self._event.clear()
            target = self._desired
            if (target and target.id) == (self._current and self._current.id):
                continue
            try:
                await self._apply(target)
            except errors.FloodWaitError as exc:
                log.warning("Profile: Telegram asks to wait %s s", exc.seconds)
                await asyncio.sleep(exc.seconds + 1)
                self._event.set()
            except Exception:
                log.exception("Profile: could not update the track")
                await asyncio.sleep(10)

    async def _apply(self, target: Track | None) -> None:
        if target is None:
            if self._current_doc:
                await self._unsave(self._current_doc)
                await self._delete_saved_message()
            self._current = self._current_doc = None
            self.store.set(profile_doc=None)
            log.info("Profile: track removed (music paused)")
            return

        old_doc, old_msg = self._current_doc, self.store.get("profile_message_id")
        doc, msg_id = await self._upload(target)
        try:
            await self.client(functions.account.SaveMusicRequest(id=doc))
        except errors.RPCError as exc:
            if "DOCUMENT_INVALID" not in str(exc) or self._use_saved_messages:
                raise
            # Fallback: upload the file via Saved Messages
            log.info("Profile: switching to uploads via Saved Messages")
            self._use_saved_messages = True
            self.store.set(profile_use_saved_messages=True)
            doc, msg_id = await self._upload(target)
            await self.client(functions.account.SaveMusicRequest(id=doc))

        self._current, self._current_doc = target, doc
        self.store.set(profile_doc=self._dump_doc(doc), profile_message_id=msg_id)
        if old_doc:
            await self._unsave(old_doc)
        if old_msg and old_msg != msg_id:
            await self._delete_messages([old_msg])
        log.info("Profile: ♪ %s — %s", target.title, target.performer)

    async def _upload(self, track: Track) -> tuple[types.InputDocument, int | None]:
        audio = await self.client.upload_file(
            silent_mp3(track.duration, track.title, track.performer), file_name="track.mp3"
        )
        thumb = None
        if track.cover:
            try:
                resp = await self._http.get(track.cover)
                resp.raise_for_status()
                thumb = await self.client.upload_file(resp.content, file_name="cover.jpg")
            except Exception as exc:
                log.debug("Profile: cover download failed: %s", exc)

        attributes = [
            types.DocumentAttributeAudio(duration=track.duration, title=track.title, performer=track.performer),
            types.DocumentAttributeFilename(f"{track.performer} - {track.title}.mp3"[:120]),
        ]
        media = types.InputMediaUploadedDocument(file=audio, mime_type="audio/mpeg", attributes=attributes, thumb=thumb)

        if self._use_saved_messages:
            result = await self.client(
                functions.messages.SendMediaRequest(peer=types.InputPeerSelf(), media=media, message="", silent=True)
            )
            message = next(u.message for u in result.updates if isinstance(u, types.UpdateNewMessage))
            document = message.media.document
            msg_id = message.id
        else:
            result = await self.client(functions.messages.UploadMediaRequest(peer=types.InputPeerSelf(), media=media))
            document = result.document
            msg_id = None
        return types.InputDocument(document.id, document.access_hash, document.file_reference), msg_id

    async def _unsave(self, doc: types.InputDocument) -> None:
        try:
            await self.client(functions.account.SaveMusicRequest(id=doc, unsave=True))
        except errors.RPCError as exc:
            log.debug("Profile: could not remove the old track: %s", exc)

    async def _delete_saved_message(self) -> None:
        msg_id = self.store.get("profile_message_id")
        if msg_id:
            await self._delete_messages([msg_id])
            self.store.set(profile_message_id=None)

    async def _delete_messages(self, ids: list[int]) -> None:
        try:
            await self.client.delete_messages("me", ids)
        except errors.RPCError as exc:
            log.debug("Profile: could not delete the message: %s", exc)

    @staticmethod
    def _dump_doc(doc: types.InputDocument) -> dict:
        return {"id": doc.id, "access_hash": doc.access_hash, "file_reference": doc.file_reference.hex()}

    @staticmethod
    def _load_doc(data: dict) -> types.InputDocument:
        return types.InputDocument(data["id"], data["access_hash"], bytes.fromhex(data["file_reference"]))
