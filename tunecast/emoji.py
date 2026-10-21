"""Animated emoji: packs created by the bot, custom replacements, non-Premium mode.

Custom emoji in bot messages are visible to everyone, but a bot may only use
them if its owner has Telegram Premium. So:
  • Premium → emoji from the TuneCast packs (or the ones the user picked);
  • no Premium → regular emoji.
"""

import hashlib
import json
import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InputSticker

from . import emoji_art
from .i18n import t
from .storage import Store

log = logging.getLogger(__name__)

PACKS = {
    "icons": {"title": "pack.icons", "repaint": True},
    "art": {"title": "pack.art", "repaint": False},
}

# Order of icons in /emoji
KEYS = list(emoji_art.FALLBACK)


class Emoji:
    def __init__(self, store: Store):
        self.store = store
        self.ids: dict[str, str] = store.get("emoji_ids", {})
        self.overrides: dict[str, dict] = store.get("emoji_overrides", {})
        self.premium: bool = bool(store.get("owner_premium", False))

    # ---------- use in text ----------

    def char(self, key: str) -> str:
        override = self.overrides.get(key) or {}
        return override.get("char") or emoji_art.FALLBACK.get(key, "•")

    def custom_id(self, key: str) -> str | None:
        if not self.premium:
            return None
        if key in self.overrides:  # replaced with a regular emoji → stays regular
            return self.overrides[key].get("id")
        return self.ids.get(key)

    def __call__(self, key: str) -> str:
        """HTML fragment for a Rich Message: animated emoji or a regular one."""
        cid = self.custom_id(key)
        char = escape(self.char(key))
        return f'<tg-emoji emoji-id="{cid}">{char}</tg-emoji>' if cid else char

    # ---------- Premium ----------

    def set_premium(self, value: bool | None) -> bool:
        """Returns True if the status changed (the panel should be redrawn)."""
        value = bool(value)
        if value == self.premium:
            return False
        self.premium = value
        self.store.set(owner_premium=value)
        log.info("Emoji: Telegram Premium %s → %s emoji", "on" if value else "off", "animated" if value else "regular")
        return True

    # ---------- custom replacements ----------

    def set_override(self, key: str, custom_id: str | None, char: str | None) -> None:
        self.overrides[key] = {"id": custom_id, "char": char}
        self.store.set(emoji_overrides=self.overrides)

    def reset_override(self, key: str | None = None) -> None:
        if key is None:
            self.overrides = {}
        else:
            self.overrides.pop(key, None)
        self.store.set(emoji_overrides=self.overrides)

    # ---------- packs ----------

    async def sync_packs(self, bot: Bot, owner_id: int) -> None:
        """Create the TuneCast packs (or recreate them if the artwork changed)."""
        me = await bot.get_me()
        art = emoji_art.build_all()
        packs_state: dict = self.store.get("emoji_packs", {})
        ids = dict(self.ids)

        for pack, docs in art.items():
            files = {key: emoji_art.tgs(doc) for key, doc in docs.items()}
            digest = hashlib.sha1(
                json.dumps({k: hashlib.sha1(v).hexdigest() for k, v in files.items()}, sort_keys=True).encode()
            ).hexdigest()[:8]
            name = f"tunecast_{pack}_{digest}_by_{me.username}".lower()
            current = packs_state.get(pack, {})

            if current.get("name") == name and all(key in ids for key in files):
                continue  # pack is up to date

            stickers = await self._ensure_set(bot, owner_id, name, pack, files)
            for key, sticker in zip(files, stickers):
                ids[key] = sticker.custom_emoji_id
            old = current.get("name")
            packs_state[pack] = {"name": name}
            self.ids = ids
            self.store.set(emoji_ids=ids, emoji_packs=packs_state)
            log.info("Emoji: pack ready: t.me/addemoji/%s", name)
            if old and old != name:
                try:
                    await bot.delete_sticker_set(old)
                except TelegramBadRequest:
                    pass

    async def _ensure_set(self, bot: Bot, owner_id: int, name: str, pack: str, files: dict[str, bytes]):
        """Create the pack with one icon, then add the rest one by one.

        Telegram rate-limits these calls strictly. If it asks to wait,
        TelegramRetryAfter propagates up, and the next attempt continues where
        this one stopped: icons already added stay in the pack in order.
        """
        keys = list(files)

        def sticker(key: str) -> InputSticker:
            return InputSticker(
                sticker=BufferedInputFile(files[key], filename=f"{key}.tgs"),
                format="animated",
                emoji_list=[emoji_art.FALLBACK[key]],
                keywords=[key.replace("_", " ")],
            )

        try:
            count = len((await bot.get_sticker_set(name)).stickers)
        except TelegramBadRequest:
            await bot.create_new_sticker_set(
                user_id=owner_id,
                name=name,
                title=t(PACKS[pack]["title"]),
                stickers=[sticker(keys[0])],
                sticker_type="custom_emoji",
                needs_repainting=PACKS[pack]["repaint"],
            )
            count = 1

        for n, key in enumerate(keys[count:], count + 1):
            await bot.add_sticker_to_set(user_id=owner_id, name=name, sticker=sticker(key))
            log.info("Emoji: %s %d/%d", pack, n, len(keys))
        return (await bot.get_sticker_set(name)).stickers
