"""Свои анимированные эмодзи: создание паков ботом, замена своими, режим без Premium.

Custom emoji в сообщениях бота видны всем, но ставить их бот может, только
если у владельца бота есть Telegram Premium. Поэтому:
  • Premium есть → эмодзи из паков TuneCast (или те, что пользователь выбрал сам);
  • Premium нет → обычные эмодзи.
"""

import hashlib
import json
import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InputSticker

from . import emoji_art
from .storage import Store

log = logging.getLogger(__name__)

PACKS = {
    "icons": {"title": "TuneCast · иконки", "repaint": True},
    "art": {"title": "TuneCast · акценты", "repaint": False},
}

LABELS = {
    "play": "Играть",
    "pause": "Пауза",
    "next": "Следующий",
    "prev": "Предыдущий",
    "shuffle": "Перемешать",
    "repeat": "Повтор",
    "repeat_one": "Повтор трека",
    "vol_down": "Тише",
    "vol_up": "Громче",
    "queue": "Очередь",
    "library": "Плейлисты",
    "devices": "Устройства",
    "refresh": "Обновить",
    "search": "Поиск",
    "plus": "В очередь",
    "close": "Закрыть",
    "back": "Назад",
    "computer": "Компьютер",
    "phone": "Телефон",
    "speaker": "Колонка",
    "music": "Трек",
    "heart_outline": "Сердце (контур)",
    "disc": "Альбом",
    "clock": "Длительность",
    "equalizer": "Играет",
    "equalizer_paused": "На паузе",
    "vinyl": "Винил",
    "heart": "Любимые",
    "note": "Нота",
    "live": "В эфире",
    "sleep": "Ничего не играет",
}


class Emoji:
    def __init__(self, store: Store):
        self.store = store
        self.ids: dict[str, str] = store.get("emoji_ids", {})
        self.overrides: dict[str, dict] = store.get("emoji_overrides", {})
        self.premium: bool = bool(store.get("owner_premium", False))

    # ---------- использование в тексте ----------

    def char(self, key: str) -> str:
        override = self.overrides.get(key) or {}
        return override.get("char") or emoji_art.FALLBACK.get(key, "•")

    def custom_id(self, key: str) -> str | None:
        if not self.premium:
            return None
        if key in self.overrides:  # заменённый обычным эмодзи остаётся обычным
            return self.overrides[key].get("id")
        return self.ids.get(key)

    def __call__(self, key: str) -> str:
        """HTML-фрагмент для Rich Message: анимированный эмодзи или обычный."""
        cid = self.custom_id(key)
        char = escape(self.char(key))
        return f'<tg-emoji emoji-id="{cid}">{char}</tg-emoji>' if cid else char

    # ---------- Premium ----------

    def set_premium(self, value: bool | None) -> bool:
        """Вернёт True, если статус изменился (панель стоит перерисовать)."""
        value = bool(value)
        if value == self.premium:
            return False
        self.premium = value
        self.store.set(owner_premium=value)
        log.info("Эмодзи: Premium %s → %s", "есть" if value else "нет", "анимированные" if value else "обычные")
        return True

    # ---------- замена своими ----------

    def set_override(self, key: str, custom_id: str | None, char: str | None) -> None:
        self.overrides[key] = {"id": custom_id, "char": char}
        self.store.set(emoji_overrides=self.overrides)

    def reset_override(self, key: str | None = None) -> None:
        if key is None:
            self.overrides = {}
        else:
            self.overrides.pop(key, None)
        self.store.set(emoji_overrides=self.overrides)

    # ---------- паки ----------

    async def sync_packs(self, bot: Bot, owner_id: int) -> None:
        """Создать паки TuneCast (или пересоздать, если рисунки поменялись)."""
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
                continue  # пак актуален

            stickers = await self._ensure_set(bot, owner_id, name, pack, files)
            for key, sticker in zip(files, stickers):
                ids[key] = sticker.custom_emoji_id
            old = current.get("name")
            packs_state[pack] = {"name": name}
            self.ids = ids
            self.store.set(emoji_ids=ids, emoji_packs=packs_state)
            log.info("Эмодзи: пак «%s» готов: t.me/addemoji/%s", PACKS[pack]["title"], name)
            if old and old != name:
                try:
                    await bot.delete_sticker_set(old)
                except TelegramBadRequest:
                    pass

    async def _ensure_set(self, bot: Bot, owner_id: int, name: str, pack: str, files: dict[str, bytes]):
        """Создаёт пак с одной иконкой и докладывает остальные по одной.

        Telegram строго ограничивает частоту таких запросов. Если он попросит
        подождать, TelegramRetryAfter уйдёт наверх, а при повторе работа
        продолжится с того места, где остановилась: уже добавленные иконки
        лежат в паке по порядку.
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
                title=PACKS[pack]["title"],
                stickers=[sticker(keys[0])],
                sticker_type="custom_emoji",
                needs_repainting=PACKS[pack]["repaint"],
            )
            count = 1

        for n, key in enumerate(keys[count:], count + 1):
            await bot.add_sticker_to_set(user_id=owner_id, name=name, sticker=sticker(key))
            log.info("Эмодзи: %s %d/%d", pack, n, len(keys))
        return (await bot.get_sticker_set(name)).stickers


