"""Оформление бота: всё собирается в Rich Message (Bot API 10.1+).

Каждая функция возвращает HTML для InputRichMessage. Кнопки встроены прямо
в сообщение рядами по центру. `e` — объект Emoji: e("pause") даёт
анимированный эмодзи (с Premium) или обычный.
"""

import math
import re
from html import escape, unescape

from .emoji import Emoji

GREEN, BLUE, RED, LINK = "success", "primary", "danger", "link"

PLAYLISTS_PER_PAGE = 8
QUEUE_LIMIT = 20

DEVICE_KEYS = {
    "computer": "computer",
    "smartphone": "phone",
    "tablet": "phone",
    "speaker": "speaker",
    "castaudio": "speaker",
    "castvideo": "speaker",
    "tv": "computer",
}
REPEAT_NEXT = {"off": "context", "context": "track", "track": "off"}


# ---------- строительные блоки ----------


def btn(text: str, data: str, style: str | None = None) -> str:
    s = f' style="{style}"' if style else ""
    return f'<tg-button type="callback_data"{s} data="{escape(data)}">{text}</tg-button>'


def url_btn(text: str, url: str, style: str | None = None) -> str:
    s = f' style="{style}"' if style else ""
    return f'<tg-button type="url"{s} url="{escape(url)}">{text}</tg-button>'


def label(text: str) -> str:
    return f'<tg-button type="disabled">{text}</tg-button>'


def row(*buttons: str) -> str:
    items = "".join(b for b in buttons if b)
    return f'<tg-button-row align="center">{items}</tg-button-row>' if items else ""


def page(*parts: str) -> str:
    return "\n".join(p for p in parts if p)


def short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fmt_time(ms: int | None) -> str:
    seconds = int((ms or 0) // 1000)
    if seconds >= 3600:
        return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


def progress_bar(progress: int, duration: int, width: int = 16) -> str:
    if not duration:
        return "─" * width
    pos = min(width - 1, int(progress / duration * width))
    return "━" * pos + "●" + "─" * (width - pos - 1)


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def artists(item: dict) -> str:
    if item.get("type") == "episode":
        return (item.get("show") or {}).get("name", "Подкаст")
    return ", ".join(a["name"] for a in item.get("artists", [])) or "Неизвестный исполнитель"


def pick_image(images: list[dict] | None, small: bool = False) -> str | None:
    if not images:
        return None
    ordered = sorted(images, key=lambda img: img.get("width") or 0)
    if small:
        for img in ordered:
            if (img.get("width") or 0) >= 250:
                return img["url"]
    return ordered[-1]["url"]


def item_image(item: dict | None, small: bool = False) -> str | None:
    if not item:
        return None
    if item.get("type") == "episode":
        return pick_image(item.get("images") or (item.get("show") or {}).get("images"), small)
    return pick_image((item.get("album") or {}).get("images"), small)


def total_items(obj: dict) -> int | None:
    # В 2026 Spotify переименовал поле tracks → items
    for key in ("items", "tracks"):
        value = obj.get(key)
        if isinstance(value, dict) and "total" in value:
            return value["total"]
    return None


def link(text: str, url: str | None) -> str:
    return f'<a href="{escape(url)}">{text}</a>' if url else text


def spotify_url(obj: dict) -> str | None:
    return (obj.get("external_urls") or {}).get("spotify")


def cover(url: str | None) -> str:
    return f'<img src="{escape(url)}"/>' if url else ""


def device_key(device: dict | None) -> str:
    return DEVICE_KEYS.get(((device or {}).get("type") or "").lower(), "devices")


def cell_icon(e: Emoji, key: str) -> str:
    """Иконка для кнопки в ячейке таблицы.

    Пробел U+2002 после custom emoji делает кнопку шире (ровная «таблетка»
    вместо кружка) и не даёт Unigram сдвигать иконку вправо.
    """
    return e(key) + (" " if e.custom_id(key) else "")


def nav_back(e: Emoji, data: str = "v:player", text: str = "К плееру") -> str:
    return row(btn(f"{e('back')} {text}", data))


# ---------- панель: плеер ----------


def player_signature(pb: dict | None) -> tuple:
    """Всё, кроме позиции трека: если поменялось, панель обновляется сразу."""
    if not pb:
        return ()
    item = pb.get("item") or {}
    device = pb.get("device") or {}
    return (
        item.get("id") or item.get("uri"),
        pb.get("is_playing"),
        pb.get("shuffle_state"),
        pb.get("repeat_state"),
        device.get("id"),
        device.get("volume_percent"),
        (pb.get("context") or {}).get("uri"),
    )


def player_view(e: Emoji, pb: dict | None, context_label: str | None = None) -> str:
    item = (pb or {}).get("item")
    if not item:
        return page(
            f"<aside>{e('sleep')} <b>Сейчас ничего не играет</b>"
            "<cite>Включи Spotify на любом устройстве или выбери плейлист</cite></aside>",
            row(btn(f"{e('library')} Плейлисты", "v:pl:0", BLUE), btn(f"{e('heart')} Любимые", "lk", GREEN)),
            row(btn(f"{e('devices')} Устройства", "v:dev"), btn(f"{e('refresh')} Обновить", "p:refresh")),
            f"<footer>{e('search')} Чтобы найти трек, просто напиши мне его название</footer>",
        )

    playing = bool(pb.get("is_playing"))
    device = pb.get("device") or {}
    is_episode = item.get("type") == "episode"
    title = link(escape(item["name"]), spotify_url(item))
    cite = f"{e('music')} Подкаст" if is_episode else f"{e('disc')} {escape((item.get('album') or {}).get('name', ''))}"

    progress = pb.get("progress_ms") or 0
    duration = item.get("duration_ms") or 0
    shuffle_on = bool(pb.get("shuffle_state"))
    repeat = pb.get("repeat_state", "off")

    toggle = (
        btn(f"{e('pause')} Пауза", "p:toggle", BLUE) if playing else btn(f"{e('play')} Играть", "p:toggle", GREEN)
    )
    footer = [
        f"{e('equalizer')} Играет" if playing else f"{e('equalizer_paused')} Пауза",
        f"{e(device_key(device))} {escape(device.get('name') or 'устройство')}",
    ]
    if device.get("volume_percent") is not None:
        footer.append(f"{e('vol_up')} {device['volume_percent']}%")
    if context_label:
        footer.append(f"{e('library')} {escape(context_label)}")

    return page(
        cover(item_image(item)),
        f"<aside><b>{title}</b><br/>{escape(artists(item))}<cite>{cite}</cite></aside>",
        f"<aside><code>{fmt_time(progress)}  {progress_bar(progress, duration)}  {fmt_time(duration)}</code></aside>",
        row(btn(e("prev"), "p:prev"), toggle, btn(e("next"), "p:next")),
        row(
            btn(e("shuffle"), "p:shuffle", GREEN if shuffle_on else None),
            btn(e("repeat_one") if repeat == "track" else e("repeat"), "p:repeat", GREEN if repeat != "off" else None),
            btn(e("vol_down"), "p:vol:-10"),
            btn(e("vol_up"), "p:vol:10"),
        ),
        row(
            btn(f"{e('queue')} Очередь", "v:queue"),
            btn(f"{e('library')} Плейлисты", "v:pl:0"),
            btn(e("devices"), "v:dev"),
            btn(e("refresh"), "p:refresh"),
        ),
        f"<footer>{'  ·  '.join(footer)}</footer>",
    )


# ---------- панель: очередь ----------


def track_cell(item: dict, title_limit: int = 34) -> str:
    return f"<b>{escape(short(item['name'], title_limit))}</b> · <i>{escape(short(artists(item), 24))}</i>"


def queue_view(e: Emoji, data: dict) -> str:
    current = data.get("currently_playing")
    upcoming = [item for item in (data.get("queue") or []) if item][:QUEUE_LIMIT]

    parts = [
        f"<aside>{e('queue')} <b>Очередь</b><cite>"
        + (f"дальше {len(upcoming)} {plural(len(upcoming), 'трек', 'трека', 'треков')}" if upcoming else "пока пусто")
        + "</cite></aside>"
    ]
    if current:
        parts.append(f"<blockquote>{e('equalizer')} {track_cell(current, 40)}</blockquote>")
    if upcoming:
        rows = "".join(
            f'<tr><td align="right">{i}</td><td>{track_cell(item)}</td>'
            f'<td align="right">{fmt_time(item.get("duration_ms"))}</td></tr>'
            for i, item in enumerate(upcoming, 1)
        )
        parts.append(f"<table compact striped><tr><th>#</th><th>Трек</th><th>{e('clock')}</th></tr>{rows}</table>")
    else:
        parts.append(f"<p><i>Напиши название трека, и я добавлю его в очередь {e('plus')}</i></p>")

    parts.append(row(btn(f"{e('next')} Следующий", "p:next", BLUE), btn(f"{e('refresh')} Обновить", "v:queue")))
    parts.append(nav_back(e))
    return page(*parts)


# ---------- панель: плейлисты ----------


def playlists_view(e: Emoji, data: dict, page_no: int) -> str:
    items = [p for p in (data.get("items") or []) if p]
    total = data.get("total") or len(items)
    pages = max(1, math.ceil(total / PLAYLISTS_PER_PAGE))

    parts = [
        f"<aside>{e('library')} <b>Твои плейлисты</b><cite>"
        f"{total} {plural(total, 'плейлист', 'плейлиста', 'плейлистов')}</cite></aside>"
    ]
    if page_no == 0:
        parts.append(row(btn(f"{e('heart')} Любимые треки", "lk", GREEN)))
    for pl in items:
        count = total_items(pl)
        name = escape(short(pl.get("name") or "Без названия", 32))
        parts.append(row(btn(f"{e('music')} {name}" + (f"  · {count}" if count is not None else ""), f"pl:{pl['id']}")))
    if pages > 1:
        parts.append(
            row(
                btn(e("prev"), f"v:pl:{page_no - 1}") if page_no > 0 else label(e("prev")),
                label(f"{page_no + 1} / {pages}"),
                btn(e("next"), f"v:pl:{page_no + 1}") if page_no + 1 < pages else label(e("next")),
            )
        )
    parts.append(nav_back(e))
    parts.append(f"<footer>{e('search')} Можно прислать ссылку на любой плейлист или альбом из Spotify</footer>")
    return page(*parts)


def context_card(e: Emoji, kind: str, obj: dict, back: str | None = None, closable: bool = False) -> str:
    """Карточка плейлиста / альбома / исполнителя с кнопками запуска."""
    icon = {"playlist": "library", "album": "disc", "artist": "music"}.get(kind, "music")
    kind_label = {"playlist": "Плейлист", "album": "Альбом", "artist": "Исполнитель"}.get(kind, "")
    title = link(escape(obj.get("name") or "Без названия"), spotify_url(obj))

    details: list[str] = []
    if kind == "playlist" and (obj.get("owner") or {}).get("display_name"):
        details.append(escape(obj["owner"]["display_name"]))
    elif kind == "album":
        details.append(escape(artists(obj)))
        if obj.get("release_date"):
            details.append(escape(obj["release_date"][:4]))
    elif kind == "artist" and obj.get("genres"):
        details.append(escape(", ".join(obj["genres"][:3])))
    count = total_items(obj)
    if count is not None:
        details.append(f"{count} {plural(count, 'трек', 'трека', 'треков')}")

    description = unescape(re.sub(r"<[^>]+>", "", obj.get("description") or "")).strip()
    bottom = []
    if back:
        bottom.append(btn(f"{e('back')} Назад", back))
    if closable:
        bottom.append(btn(f"{e('close')} Закрыть", "s:x", RED))

    return page(
        cover(pick_image(obj.get("images"))),
        f"<aside><b>{title}</b>" + (f"<br/>{' · '.join(details)}" if details else "") + f"<cite>{e(icon)} {kind_label}</cite></aside>",
        f"<details><summary>Описание</summary><p>{escape(short(description, 600))}</p></details>" if description else "",
        row(
            btn(f"{e('play')} Играть", f"c:p:{kind}:{obj['id']}", GREEN),
            btn(f"{e('shuffle')} Вперемешку", f"c:s:{kind}:{obj['id']}", BLUE),
        ),
        row(*bottom),
    )


# ---------- панель: устройства ----------


def devices_view(e: Emoji, devices: list[dict]) -> str:
    parts = [f"<aside>{e('devices')} <b>Устройства</b><cite>Нажми, чтобы перенести музыку</cite></aside>"]
    usable = [d for d in devices if d.get("id") and not d.get("is_restricted")]
    if not usable:
        parts.append(f"<blockquote>{e('sleep')} Не вижу ни одного устройства. Открой Spotify на ПК или телефоне и нажми «Обновить».</blockquote>")
    for dev in usable:
        vol = dev.get("volume_percent")
        text = f"{e(device_key(dev))} {escape(short(dev.get('name') or '?', 28))}" + (f"  · {vol}%" if vol is not None else "")
        parts.append(row(btn(text, f"dev:{dev['id']}", GREEN if dev.get("is_active") else None)))
    parts.append(row(btn(f"{e('refresh')} Обновить", "v:dev"), btn(f"{e('back')} К плееру", "v:player")))
    return page(*parts)


# ---------- поиск и ссылки (отдельные сообщения) ----------


def search_view(e: Emoji, query: str, result: dict, offset: int) -> str:
    items = [t for t in (result.get("items") or []) if t]
    total = min(result.get("total") or 0, 1000)
    if not items:
        return page(
            f"<aside>{e('search')} <b>Ничего не нашёл</b><cite>{escape(short(query, 60))}</cite></aside>",
            "<p>Попробуй написать иначе, например «исполнитель — трек».</p>",
            row(btn(f"{e('close')} Закрыть", "s:x", RED)),
        )

    rows = "".join(
        f'<tr><td align="right">{i}</td><td>{track_cell(t, 30)}</td>'
        f'<td align="right">{fmt_time(t.get("duration_ms"))}</td>'
        # Обе кнопки в одной ячейке: так Telegram рисует их ровными «таблетками»
        f'<td>{btn(cell_icon(e, "plus"), "t:add:" + t["id"])}{btn(cell_icon(e, "play"), "t:now:" + t["id"], GREEN)}</td></tr>'
        for i, t in enumerate(items, offset + 1)
    )
    nav = []
    if offset > 0:
        nav.append(btn(f"{e('prev')} Назад", f"s:pg:{max(0, offset - 10)}"))
    if offset + len(items) < total:
        nav.append(btn(f"Ещё {e('next')}", f"s:pg:{offset + 10}", BLUE))
    nav.append(btn(f"{e('close')} Закрыть", "s:x", RED))

    return page(
        f"<aside>{e('search')} <b>{escape(short(query, 60))}</b><cite>{e('plus')} в очередь  ·  {e('play')} включить сразу</cite></aside>",
        f"<table compact striped><tr><th>#</th><th>Трек</th><th>{e('clock')}</th><th></th></tr>{rows}</table>",
        row(*nav),
    )


def track_card(e: Emoji, track: dict) -> str:
    album = (track.get("album") or {}).get("name")
    return page(
        cover(item_image(track)),
        f"<aside><b>{link(escape(track['name']), spotify_url(track))}</b><br/>{escape(artists(track))}"
        f"<cite>{e('disc')} {escape(album or '')}  ·  {fmt_time(track.get('duration_ms'))}</cite></aside>",
        row(btn(f"{e('plus')} В очередь", f"t:add:{track['id']}", GREEN), btn(f"{e('play')} Включить", f"t:now:{track['id']}", BLUE)),
        row(btn(f"{e('close')} Закрыть", "s:x", RED)),
    )


def help_view(e: Emoji) -> str:
    return page(
        f"<aside>{e('vinyl')} <b>TuneCast</b><cite>Управляй Spotify из Telegram</cite></aside>",
        "<h3>Что я умею</h3>",
        "<ul>"
        f"<li>{e('play')} Управлять музыкой: пауза, переключение, перемешивание, громкость</li>"
        f"<li>{e('queue')} Показывать очередь</li>"
        f"<li>{e('search')} Искать треки и добавлять их в очередь</li>"
        f"<li>{e('library')} Включать плейлисты, альбомы и исполнителей</li>"
        f"<li>{e('live')} Показывать текущий трек в профиле Telegram</li>"
        "</ul>",
        "<h3>Как пользоваться</h3>",
        "<ul>"
        "<li><b>/start</b> — открыть плеер</li>"
        "<li>Напиши название трека, чтобы найти его</li>"
        "<li>Пришли ссылку из Spotify, чтобы включить плейлист, альбом или трек</li>"
        "<li><b>/emoji</b> — заменить иконки своими эмодзи</li>"
        "</ul>",
        row(btn(f"{e('vinyl')} Открыть плеер", "v:new")),
    )


# ---------- настройка эмодзи ----------


def emoji_view(e: Emoji, labels: dict[str, str], waiting: str | None = None) -> str:
    if not e.premium:
        return page(
            f"<aside>{e('heart')} <b>Свои эмодзи</b><cite>нужен Telegram Premium</cite></aside>",
            "<p>Анимированные эмодзи бот может ставить, только если у владельца бота есть Telegram Premium. "
            "Сейчас используются обычные эмодзи. Когда Premium появится, всё переключится само.</p>",
        )
    rows = "".join(
        f"<tr><td>{e(key)}</td><td>{escape(name)}</td>"
        f"<td>{btn('изменить', 'em:set:' + key)}"
        + (btn('сброс', 'em:rst:' + key, RED) if key in e.overrides else "")
        + "</td></tr>"
        for key, name in labels.items()
    )
    hint = (
        f"<blockquote>{e('note')} Пришли мне эмодзи для «{escape(labels[waiting])}»: любой из Premium-паков или обычный.</blockquote>"
        if waiting
        else "<p>Нажми «изменить» и пришли любой эмодзи. Анимированные паки TuneCast добавлены по умолчанию.</p>"
    )
    return page(
        f"<aside>{e('heart')} <b>Эмодзи бота</b><cite>{len(e.overrides)} заменено</cite></aside>",
        hint,
        f"<table compact striped>{rows}</table>",
        row(btn(f"{e('refresh')} Сбросить все", "em:rst:*", RED) if e.overrides else "", btn(f"{e('close')} Готово", "s:x")),
    )
