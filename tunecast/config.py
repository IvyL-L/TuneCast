"""Настройки TuneCast.

Все ключи и файлы входа лежат только на твоём компьютере, в папке data рядом
с TuneCast.exe (или рядом с исходниками, если запускаешь из Python).
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

if getattr(sys, "frozen", False):  # собранный TuneCast.exe
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
SETTINGS = DATA / "settings.env"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
APP_NAME = "TuneCast"
DESCRIPTION = "Управляй Spotify из Telegram"

REQUIRED = ("BOT_TOKEN", "ALLOWED_USER_IDS", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "да")


def _num(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_ids: frozenset[int]
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    poll_interval: float
    panel_refresh: float
    profile_enabled: bool
    tg_api_id: int | None
    tg_api_hash: str | None
    profile_clear_after: float
    profile_clear_on_exit: bool


def reload_settings() -> None:
    load_dotenv(SETTINGS, override=True)


def is_configured() -> bool:
    reload_settings()
    return SETTINGS.exists() and all(os.getenv(key, "").strip() for key in REQUIRED)


def save_settings(values: dict[str, str]) -> None:
    """Дописать или обновить значения в data/settings.env."""
    DATA.mkdir(parents=True, exist_ok=True)
    current: dict[str, str] = {}
    if SETTINGS.exists():
        for line in SETTINGS.read_text("utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                current[key.strip()] = value.strip()
    current.update({k: str(v) for k, v in values.items()})
    lines = [
        "# Настройки TuneCast. Файл хранится только на этом компьютере.",
        "# Никому его не отправляй: здесь ключи от твоего бота и Spotify.",
        "",
    ]
    lines += [f"{key}={value}" for key, value in current.items()]
    SETTINGS.write_text("\n".join(lines) + "\n", "utf-8")
    reload_settings()


def load_config() -> Config:
    reload_settings()
    missing = [key for key in REQUIRED if not os.getenv(key, "").strip()]
    if missing:
        raise SystemExit("Не заполнены настройки: " + ", ".join(missing) + ". Запусти TuneCast.exe --setup")

    ids = frozenset(
        int(part) for part in os.getenv("ALLOWED_USER_IDS", "").replace(";", ",").split(",") if part.strip()
    )
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()

    return Config(
        bot_token=os.environ["BOT_TOKEN"].strip(),
        allowed_ids=ids,
        spotify_client_id=os.environ["SPOTIFY_CLIENT_ID"].strip(),
        spotify_client_secret=os.environ["SPOTIFY_CLIENT_SECRET"].strip(),
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "").strip() or REDIRECT_URI,
        poll_interval=max(_num("POLL_INTERVAL", 5), 2),
        panel_refresh=max(_num("PANEL_REFRESH", 15), 5),
        profile_enabled=_bool("PROFILE_MUSIC_ENABLED", True) and bool(api_id and api_hash),
        tg_api_id=int(api_id) if api_id else None,
        tg_api_hash=api_hash or None,
        profile_clear_after=_num("PROFILE_CLEAR_AFTER", 90),
        profile_clear_on_exit=_bool("PROFILE_CLEAR_ON_EXIT", True),
    )
