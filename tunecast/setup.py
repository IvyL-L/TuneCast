"""TuneCast first-run setup wizard.

Every step explains why a key is needed and where to get it, opens the right
pages and checks the value right away. Everything is saved only in
data/settings.env on this computer.
"""

import asyncio
import base64
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table

from .config import APP_NAME, DATA, REDIRECT_URI, ROOT, SETTINGS, has_language, reload_settings, save_settings
from .i18n import LANGUAGE_NAMES, LANGUAGES, lang, set_lang, t

console = Console(highlight=False)
GREEN = "#1ed760"
TOTAL = 6


# ---------- look & feel ----------


def step(n: int, title_key: str) -> None:
    console.print()
    console.print(Rule(f"[bold {GREEN}]{t('w.step', n=n, total=TOTAL, title=t(title_key))}[/]", style=GREEN))


def explain(why: str, where: list[str] | None = None, note: str | None = None) -> None:
    body = f"[bold]{t('w.why')}[/]\n{why}"
    if where:
        body += f"\n\n[bold]{t('w.where')}[/]\n" + "\n".join(f"  [{GREEN}]{i}.[/] {line}" for i, line in enumerate(where, 1))
    if note:
        body += f"\n\n[dim]{note}[/]"
    console.print(Panel(body, border_style="grey35", padding=(1, 2)))


def ok(text: str) -> None:
    console.print(f"[{GREEN}]✔[/] {text}")


def fail(text: str) -> None:
    console.print(f"[red]✖[/] {text}")


def mask(value: str) -> str:
    return value if len(value) < 10 else f"{value[:4]}…{value[-4:]}"


def open_url(url: str) -> None:
    console.print(f"[dim]{t('w.opening')}[/] [link={url}]{url}[/link]")
    try:
        webbrowser.open(url)
    except Exception:
        pass


def copy_to_clipboard(text: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        subprocess.run("clip", input=text.encode("utf-16"), check=True)
        return True
    except Exception:
        return False


def ask(label: str, current: str | None = None, secret: bool = False) -> str:
    """Ask for a value. Enter keeps the current one (when re-running setup)."""
    hint = f" [dim]({t('w.keep', value=mask(current))})[/]" if current else ""
    while True:
        value = Prompt.ask(f"[bold]{label}[/]{hint}", password=secret, default="", show_default=False).strip()
        if value:
            return value
        if current:
            return current
        fail(t("w.empty"))


# ---------- steps ----------


def language_step() -> None:
    """Asked once, in both languages. Later the bot's /language command switches it."""
    if has_language():
        return
    console.print()
    console.print(Panel("Choose a language / Выбери язык\n\n  [bold]1[/] — English\n  [bold]2[/] — Русский",
                        border_style=GREEN, padding=(1, 2)))
    choice = Prompt.ask("[bold]1 / 2[/]", choices=["1", "2"], default="1", show_choices=False)
    code = LANGUAGES[int(choice) - 1]
    set_lang(code)
    save_settings({"LANGUAGE": code})
    ok(LANGUAGE_NAMES[code])


def welcome() -> None:
    console.print()
    console.print(
        Panel(
            f"[bold {GREEN}]{APP_NAME}[/] · {t('app.tagline')}\n\n" + t("w.welcome", path=SETTINGS),
            title=t("w.welcome_title"),
            border_style=GREEN,
            padding=(1, 2),
        )
    )
    Prompt.ask(f"[dim]{t('w.press_enter')}[/]", default="", show_default=False)


def bot_token_step() -> tuple[str, dict]:
    step(1, "w.s1.title")
    explain(t("w.s1.why"), [t(f"w.s1.w{i}") for i in range(1, 6)])
    current = os.getenv("BOT_TOKEN")
    if not current:
        open_url("https://t.me/BotFather")
    while True:
        token = ask(t("w.s1.prompt"), current)
        try:
            data = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
        except Exception as exc:
            fail(t("w.no_net", service="Telegram", err=exc.__class__.__name__))
            current = None
            continue
        if data.get("ok"):
            bot = data["result"]
            ok(t("w.s1.ok", username=bot["username"], name=bot["first_name"]))
            _set_bot_profile(token)
            return token, bot
        fail(t("w.s1.bad"))
        current = None


def _set_bot_profile(token: str) -> None:
    """Bot description in Telegram, shown before the first /start: English + Russian."""
    api = f"https://api.telegram.org/bot{token}"
    current = lang()
    try:
        for code in LANGUAGES:
            set_lang(code)
            extra = {} if code == "en" else {"language_code": code}
            httpx.post(f"{api}/setMyShortDescription", json={"short_description": t("app.tagline"), **extra}, timeout=15)
            httpx.post(f"{api}/setMyDescription", json={"description": t("bot.description"), **extra}, timeout=15)
    except Exception:
        pass
    finally:
        set_lang(current)


def owner_step(token: str, bot: dict) -> str:
    step(2, "w.s2.title")
    explain(t("w.s2.why"), [t("w.s2.w1", username=bot["username"]), t("w.s2.w2")])
    current = os.getenv("ALLOWED_USER_IDS")
    if current and Confirm.ask(t("w.s2.keep", id=current), default=True):
        return current

    api = f"https://api.telegram.org/bot{token}"
    try:
        httpx.post(f"{api}/deleteWebhook", timeout=15)
    except Exception:
        pass
    open_url(f"https://t.me/{bot['username']}")

    user = None
    deadline = time.monotonic() + 180
    with console.status(f"[bold]{t('w.s2.waiting')}[/]", spinner="dots"):
        while time.monotonic() < deadline and user is None:
            try:
                updates = httpx.get(f"{api}/getUpdates", params={"timeout": 20}, timeout=30).json().get("result", [])
            except Exception:
                time.sleep(2)
                continue
            users = [u["message"]["from"] for u in updates if u.get("message", {}).get("from")]
            if users:
                user = users[-1]

    if user:
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        if user.get("username"):
            name += f" (@{user['username']})"
        if Confirm.ask(t("w.s2.is_you", name=name, id=user["id"]), default=True):
            ok(t("w.s2.saved"))
            return str(user["id"])

    console.print(f"[dim]{t('w.s2.manual')}[/]")
    while True:
        value = ask(t("w.s2.prompt"))
        if value.isdigit():
            return value
        fail(t("w.s2.digits"))


def spotify_app_step() -> tuple[str, str]:
    step(3, "w.s3.title")
    copied = copy_to_clipboard(REDIRECT_URI)
    explain(
        t("w.s3.why"),
        [
            t("w.s3.w1"),
            t("w.s3.w2"),
            t("w.s3.w3", uri=REDIRECT_URI, copied=t("w.s3.copied") if copied else "."),
            t("w.s3.w4"),
            t("w.s3.w5"),
        ],
        t("w.s3.note"),
    )
    current_id, current_secret = os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")
    if not current_id:
        open_url("https://developer.spotify.com/dashboard")
    while True:
        client_id = ask("Client ID", current_id)
        client_secret = ask("Client secret", current_secret, secret=True)
        error = _check_spotify(client_id, client_secret)
        if error is None:
            ok(t("w.s3.ok"))
            return client_id, client_secret
        fail(error)
        current_id = current_secret = None


def _check_spotify(client_id: str, client_secret: str) -> str | None:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        resp = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {basic}"},
            timeout=15,
        )
    except Exception as exc:
        return t("w.no_net", service="Spotify", err=exc.__class__.__name__)
    return None if resp.status_code == 200 else t("w.s3.bad")


def spotify_login_step(values: dict) -> None:
    step(4, "w.s4.title")
    explain(t("w.s4.why"), [t("w.s4.w1"), t("w.s4.w2"), t("w.s4.w3")])
    from .spotify import Spotify

    async def login():
        token_path = DATA / "spotify_token.json"
        if token_path.exists():
            token_path.unlink()  # the keys may have changed — sign in again
        sp = Spotify(values["SPOTIFY_CLIENT_ID"], values["SPOTIFY_CLIENT_SECRET"], REDIRECT_URI, token_path)
        try:
            await sp.ensure_auth()
            return await sp.me()
        finally:
            await sp.close()

    while True:
        try:
            with console.status(f"[bold]{t('w.s4.waiting')}[/]", spinner="dots"):
                me = asyncio.run(login())
            break
        except Exception as exc:
            fail(t("w.s4.fail", err=exc))
            console.print(f"[dim]{t('w.s4.hint', uri=REDIRECT_URI)}[/]")
            if not Confirm.ask(t("w.s4.retry"), default=True):
                raise SystemExit(1)
    ok(t("w.s4.ok", name=me.get("display_name") or me.get("id")))
    if me.get("product") and me["product"] != "premium":
        console.print(f"[yellow]![/] {t('w.s4.no_premium')}")


def profile_step(values: dict) -> None:
    step(5, "w.s5.title")
    explain(t("w.s5.why"), [t(f"w.s5.w{i}") for i in range(1, 5)], t("w.s5.note"))
    enabled = bool(os.getenv("TG_API_ID"))
    if not Confirm.ask(t("w.s5.ask"), default=enabled):
        values.setdefault("PROFILE_MUSIC_ENABLED", "true" if enabled else "false")
        return
    open_url("https://my.telegram.org/apps")
    while True:
        api_id = ask("api_id", os.getenv("TG_API_ID"))
        if api_id.isdigit():
            break
        fail(t("w.s5.digits"))
    api_hash = ask("api_hash", os.getenv("TG_API_HASH"), secret=True)

    console.print(Panel(t("w.s5.login"), border_style="yellow", padding=(1, 2)))
    from telethon import TelegramClient

    async def login():
        client = TelegramClient(str(DATA / "telegram_user"), int(api_id), api_hash)
        await client.start(
            phone=lambda: Prompt.ask(f"[bold]{t('w.s5.phone')}[/]"),
            code_callback=lambda: Prompt.ask(f"[bold]{t('w.s5.code')}[/]"),
            password=lambda: Prompt.ask(f"[bold]{t('w.s5.password')}[/]", password=True),
        )
        me = await client.get_me()
        await client.disconnect()
        return me

    try:
        me = asyncio.run(login())
        ok(t("w.s5.ok", name=me.first_name))
        values.update(TG_API_ID=api_id, TG_API_HASH=api_hash, PROFILE_MUSIC_ENABLED="true")
    except Exception as exc:
        fail(t("w.s5.fail", err=exc))
        values["PROFILE_MUSIC_ENABLED"] = "false"


def autostart_step() -> None:
    step(6, "w.s6.title")
    explain(t("w.s6.why"))
    startup = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    script = startup / f"{APP_NAME}.cmd"
    if not Confirm.ask(t("w.s6.ask"), default=script.exists()):
        if script.exists():
            script.unlink()
            ok(t("w.s6.off"))
        return
    if getattr(sys, "frozen", False):
        command = f'start "{APP_NAME}" /min "{sys.executable}"'
    else:
        command = f'start "{APP_NAME}" /min "{sys.executable}" -m tunecast'
    try:
        startup.mkdir(parents=True, exist_ok=True)
        script.write_text(f'@echo off\ncd /d "{ROOT}"\n{command}\n', "utf-8")
        ok(t("w.s6.on"))
    except OSError as exc:
        fail(t("w.s6.fail", err=exc))


def summary(bot: dict) -> None:
    table = Table.grid(padding=(0, 2))
    lines = [t("w.d1", username=bot["username"]), t("w.d2"), t("w.d3"), t("w.d4"), t("w.d5")]
    for i, line in enumerate(lines, 1):
        table.add_row(f"[{GREEN}]{i}.[/]", line)
    console.print()
    console.print(Panel(table, title=f"[bold]{t('w.done')}[/]", border_style=GREEN, padding=(1, 2)))
    console.print(f"[dim]{t('w.footer')}[/]")


def run_wizard() -> None:
    reload_settings()
    language_step()
    welcome()
    token, bot = bot_token_step()
    save_settings({"BOT_TOKEN": token})
    owner = owner_step(token, bot)
    save_settings({"ALLOWED_USER_IDS": owner})
    client_id, client_secret = spotify_app_step()
    values = {"SPOTIFY_CLIENT_ID": client_id, "SPOTIFY_CLIENT_SECRET": client_secret, "SPOTIFY_REDIRECT_URI": REDIRECT_URI}
    save_settings(values)
    spotify_login_step(values)
    profile_step(values)
    save_settings(values)
    autostart_step()
    summary(bot)
