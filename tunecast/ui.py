"""Every bot screen, built as a Rich Message (Bot API 10.1+).

Each function returns HTML for InputRichMessage. Buttons are embedded in the
message as centered rows. `e` is the Emoji object: e("pause") returns an
animated emoji (with Premium) or a regular one. All texts come from i18n.
"""

import math
import re
from html import escape, unescape

from .emoji import Emoji
from .i18n import FLAGS, LANGUAGE_NAMES, LANGUAGES, lang, pl, t

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


# ---------- building blocks ----------


def btn(text: str, data: str, style: str | None = None) -> str:
    s = f' style="{style}"' if style else ""
    return f'<tg-button type="callback_data"{s} data="{escape(data)}">{text}</tg-button>'


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


def artists(item: dict) -> str:
    if item.get("type") == "episode":
        return (item.get("show") or {}).get("name", t("podcast"))
    return ", ".join(a["name"] for a in item.get("artists", [])) or t("unknown_artist")


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
    # In 2026 Spotify renamed the "tracks" field to "items"
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
    """Icon for a button inside a table cell.

    A U+2002 space after a custom emoji makes the button wider (an even pill
    instead of a circle) and keeps Unigram from shifting the icon to the right.
    """
    return e(key) + (" " if e.custom_id(key) else "")


def nav_back(e: Emoji) -> str:
    return row(btn(f"{e('back')} {t('btn.to_player')}", "v:player"))


# ---------- panel: player ----------


def player_signature(pb: dict | None) -> tuple:
    """Everything except the track position: if it changes, the panel updates right away."""
    if not pb:
        return (lang(),)
    item = pb.get("item") or {}
    device = pb.get("device") or {}
    return (
        lang(),
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
            f"<aside>{e('sleep')} <b>{t('player.idle')}</b><cite>{t('player.idle_hint')}</cite></aside>",
            row(
                btn(f"{e('library')} {t('btn.playlists')}", "v:pl:0", BLUE),
                btn(f"{e('heart')} {t('btn.liked')}", "lk", GREEN),
            ),
            row(
                btn(f"{e('devices')} {t('btn.devices')}", "v:dev"),
                btn(f"{e('refresh')} {t('btn.refresh')}", "p:refresh"),
            ),
            f"<footer>{e('search')} {t('player.search_hint')}</footer>",
        )

    playing = bool(pb.get("is_playing"))
    device = pb.get("device") or {}
    is_episode = item.get("type") == "episode"
    title = link(escape(item["name"]), spotify_url(item))
    cite = (
        f"{e('music')} {t('podcast')}"
        if is_episode
        else f"{e('disc')} {escape((item.get('album') or {}).get('name', ''))}"
    )

    progress = pb.get("progress_ms") or 0
    duration = item.get("duration_ms") or 0
    shuffle_on = bool(pb.get("shuffle_state"))
    repeat = pb.get("repeat_state", "off")

    toggle = (
        btn(f"{e('pause')} {t('btn.pause')}", "p:toggle", BLUE)
        if playing
        else btn(f"{e('play')} {t('btn.play')}", "p:toggle", GREEN)
    )
    footer = [
        f"{e('equalizer')} {t('player.playing')}" if playing else f"{e('equalizer_paused')} {t('player.paused')}",
        f"{e(device_key(device))} {escape(device.get('name') or t('device'))}",
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
            btn(f"{e('queue')} {t('btn.queue')}", "v:queue"),
            btn(f"{e('library')} {t('btn.playlists')}", "v:pl:0"),
            btn(e("devices"), "v:dev"),
            btn(e("refresh"), "p:refresh"),
        ),
        f"<footer>{'  ·  '.join(footer)}</footer>",
    )


# ---------- panel: queue ----------


def track_cell(item: dict, title_limit: int = 34) -> str:
    return f"<b>{escape(short(item['name'], title_limit))}</b> · <i>{escape(short(artists(item), 24))}</i>"


def queue_view(e: Emoji, data: dict) -> str:
    current = data.get("currently_playing")
    upcoming = [item for item in (data.get("queue") or []) if item][:QUEUE_LIMIT]

    status = t("queue.up_next", tracks=pl(len(upcoming), "track")) if upcoming else t("queue.empty")
    parts = [f"<aside>{e('queue')} <b>{t('queue.title')}</b><cite>{status}</cite></aside>"]
    if current:
        parts.append(f"<blockquote>{e('equalizer')} {track_cell(current, 40)}</blockquote>")
    if upcoming:
        rows = "".join(
            f'<tr><td align="right">{i}</td><td>{track_cell(item)}</td>'
            f'<td align="right">{fmt_time(item.get("duration_ms"))}</td></tr>'
            for i, item in enumerate(upcoming, 1)
        )
        parts.append(
            f"<table compact striped><tr><th>#</th><th>{t('queue.track')}</th><th>{e('clock')}</th></tr>{rows}</table>"
        )
    else:
        parts.append(f"<p><i>{t('queue.add_hint')} {e('plus')}</i></p>")

    parts.append(
        row(
            btn(f"{e('next')} {t('btn.next')}", "p:next", BLUE),
            btn(f"{e('refresh')} {t('btn.refresh')}", "v:queue"),
        )
    )
    parts.append(nav_back(e))
    return page(*parts)


# ---------- panel: playlists ----------


def playlists_view(e: Emoji, data: dict, page_no: int) -> str:
    items = [p for p in (data.get("items") or []) if p]
    total = data.get("total") or len(items)
    pages = max(1, math.ceil(total / PLAYLISTS_PER_PAGE))

    parts = [f"<aside>{e('library')} <b>{t('pl.title')}</b><cite>{pl(total, 'playlist')}</cite></aside>"]
    if page_no == 0:
        parts.append(row(btn(f"{e('heart')} {t('btn.liked_songs')}", "lk", GREEN)))
    for item in items:
        count = total_items(item)
        name = escape(short(item.get("name") or t("untitled"), 32))
        parts.append(
            row(btn(f"{e('music')} {name}" + (f"  · {count}" if count is not None else ""), f"pl:{item['id']}"))
        )
    if pages > 1:
        parts.append(
            row(
                btn(e("prev"), f"v:pl:{page_no - 1}") if page_no > 0 else label(e("prev")),
                label(f"{page_no + 1} / {pages}"),
                btn(e("next"), f"v:pl:{page_no + 1}") if page_no + 1 < pages else label(e("next")),
            )
        )
    parts.append(nav_back(e))
    parts.append(f"<footer>{e('search')} {t('pl.link_hint')}</footer>")
    return page(*parts)


def context_card(e: Emoji, kind: str, obj: dict, back: str | None = None, closable: bool = False) -> str:
    """Card of a playlist / album / artist with play buttons."""
    icon = {"playlist": "library", "album": "disc", "artist": "music"}.get(kind, "music")
    kind_label = t(f"kind.{kind}") if kind in ("playlist", "album", "artist") else ""
    title = link(escape(obj.get("name") or t("untitled")), spotify_url(obj))

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
        details.append(pl(count, "track"))

    description = unescape(re.sub(r"<[^>]+>", "", obj.get("description") or "")).strip()
    bottom = []
    if back:
        bottom.append(btn(f"{e('back')} {t('btn.back')}", back))
    if closable:
        bottom.append(btn(f"{e('close')} {t('btn.close')}", "s:x", RED))

    return page(
        cover(pick_image(obj.get("images"))),
        f"<aside><b>{title}</b>"
        + (f"<br/>{' · '.join(details)}" if details else "")
        + f"<cite>{e(icon)} {kind_label}</cite></aside>",
        f"<details><summary>{t('card.description')}</summary><p>{escape(short(description, 600))}</p></details>"
        if description
        else "",
        row(
            btn(f"{e('play')} {t('btn.play')}", f"c:p:{kind}:{obj['id']}", GREEN),
            btn(f"{e('shuffle')} {t('btn.shuffle_play')}", f"c:s:{kind}:{obj['id']}", BLUE),
        ),
        row(*bottom),
    )


# ---------- panel: devices ----------


def devices_view(e: Emoji, devices: list[dict]) -> str:
    parts = [f"<aside>{e('devices')} <b>{t('dev.title')}</b><cite>{t('dev.hint')}</cite></aside>"]
    usable = [d for d in devices if d.get("id") and not d.get("is_restricted")]
    if not usable:
        parts.append(f"<blockquote>{e('sleep')} {t('dev.none')}</blockquote>")
    for dev in usable:
        vol = dev.get("volume_percent")
        text = f"{e(device_key(dev))} {escape(short(dev.get('name') or '?', 28))}" + (
            f"  · {vol}%" if vol is not None else ""
        )
        parts.append(row(btn(text, f"dev:{dev['id']}", GREEN if dev.get("is_active") else None)))
    parts.append(
        row(
            btn(f"{e('refresh')} {t('btn.refresh')}", "v:dev"),
            btn(f"{e('back')} {t('btn.to_player')}", "v:player"),
        )
    )
    return page(*parts)


# ---------- search and links (separate messages) ----------


def search_view(e: Emoji, query: str, result: dict, offset: int) -> str:
    items = [x for x in (result.get("items") or []) if x]
    total = min(result.get("total") or 0, 1000)
    if not items:
        return page(
            f"<aside>{e('search')} <b>{t('search.none')}</b><cite>{escape(short(query, 60))}</cite></aside>",
            f"<p>{t('search.none_hint')}</p>",
            row(btn(f"{e('close')} {t('btn.close')}", "s:x", RED)),
        )

    rows = "".join(
        f'<tr><td align="right">{i}</td><td>{track_cell(x, 30)}</td>'
        f'<td align="right">{fmt_time(x.get("duration_ms"))}</td>'
        # Both buttons in one cell: this way Telegram draws them as even pills
        f'<td>{btn(cell_icon(e, "plus"), "t:add:" + x["id"])}{btn(cell_icon(e, "play"), "t:now:" + x["id"], GREEN)}</td></tr>'
        for i, x in enumerate(items, offset + 1)
    )
    nav = []
    if offset > 0:
        nav.append(btn(f"{e('prev')} {t('btn.back')}", f"s:pg:{max(0, offset - 10)}"))
    if offset + len(items) < total:
        nav.append(btn(f"{t('btn.more')} {e('next')}", f"s:pg:{offset + 10}", BLUE))
    nav.append(btn(f"{e('close')} {t('btn.close')}", "s:x", RED))

    return page(
        f"<aside>{e('search')} <b>{escape(short(query, 60))}</b>"
        f"<cite>{e('plus')} {t('search.to_queue')}  ·  {e('play')} {t('search.play_now')}</cite></aside>",
        f"<table compact striped><tr><th>#</th><th>{t('queue.track')}</th><th>{e('clock')}</th><th></th></tr>{rows}</table>",
        row(*nav),
    )


def track_card(e: Emoji, track: dict) -> str:
    album = (track.get("album") or {}).get("name")
    return page(
        cover(item_image(track)),
        f"<aside><b>{link(escape(track['name']), spotify_url(track))}</b><br/>{escape(artists(track))}"
        f"<cite>{e('disc')} {escape(album or '')}  ·  {fmt_time(track.get('duration_ms'))}</cite></aside>",
        row(
            btn(f"{e('plus')} {t('btn.add_queue')}", f"t:add:{track['id']}", GREEN),
            btn(f"{e('play')} {t('btn.play_now')}", f"t:now:{track['id']}", BLUE),
        ),
        row(btn(f"{e('close')} {t('btn.close')}", "s:x", RED)),
    )


def help_view(e: Emoji) -> str:
    return page(
        f"<aside>{e('vinyl')} <b>TuneCast</b><cite>{t('app.tagline')}</cite></aside>",
        f"<h3>{t('help.can')}</h3>",
        "<ul>"
        f"<li>{e('play')} {t('help.f1')}</li>"
        f"<li>{e('queue')} {t('help.f2')}</li>"
        f"<li>{e('search')} {t('help.f3')}</li>"
        f"<li>{e('library')} {t('help.f4')}</li>"
        f"<li>{e('live')} {t('help.f5')}</li>"
        "</ul>",
        f"<h3>{t('help.how')}</h3>",
        "<ul>"
        f"<li>{t('help.h1')}</li>"
        f"<li>{t('help.h2')}</li>"
        f"<li>{t('help.h3')}</li>"
        f"<li>{t('help.h4')}</li>"
        f"<li>{t('help.h5')}</li>"
        "</ul>",
        row(btn(f"{e('vinyl')} {t('btn.open_player')}", "v:new")),
    )


# ---------- language ----------


def language_view(e: Emoji) -> str:
    return page(
        f"<aside>🌐 <b>{t('lang.title')}</b><cite>{t('lang.hint')}</cite></aside>",
        row(
            *(
                btn(f"{FLAGS[code]} {LANGUAGE_NAMES[code]}", f"lang:{code}", GREEN if code == lang() else None)
                for code in LANGUAGES
            )
        ),
        row(btn(f"{e('close')} {t('btn.close')}", "s:x")),
    )


# ---------- emoji settings ----------


def emoji_view(e: Emoji, keys: list[str], waiting: str | None = None) -> str:
    if not e.premium:
        return page(
            f"<aside>{e('heart')} <b>{t('emoji.custom')}</b><cite>{t('emoji.need_premium')}</cite></aside>",
            f"<p>{t('emoji.no_premium')}</p>",
        )
    rows = "".join(
        f"<tr><td>{e(key)}</td><td>{escape(t('label.' + key))}</td>"
        f"<td>{btn(t('btn.change'), 'em:set:' + key)}"
        + (btn(t("btn.reset"), "em:rst:" + key, RED) if key in e.overrides else "")
        + "</td></tr>"
        for key in keys
    )
    hint = (
        f"<blockquote>{e('note')} {escape(t('emoji.waiting', label=t('label.' + waiting)))}</blockquote>"
        if waiting
        else f"<p>{t('emoji.hint')}</p>"
    )
    return page(
        f"<aside>{e('heart')} <b>{t('emoji.title')}</b><cite>{t('emoji.replaced', n=len(e.overrides))}</cite></aside>",
        hint,
        f"<table compact striped>{rows}</table>",
        row(
            btn(f"{e('refresh')} {t('btn.reset_all')}", "em:rst:*", RED) if e.overrides else "",
            btn(f"{e('close')} {t('btn.done')}", "s:x"),
        ),
    )
