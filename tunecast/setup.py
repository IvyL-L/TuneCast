"""Мастер первой настройки TuneCast.

На каждом шаге объясняет, зачем нужен ключ и где его взять, сам открывает
нужные страницы и сразу проверяет введённое. Всё сохраняется только
в data/settings.env на этом компьютере.
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

from .config import APP_NAME, DATA, DESCRIPTION, REDIRECT_URI, ROOT, SETTINGS, reload_settings, save_settings

console = Console(highlight=False)
GREEN = "#1ed760"
TOTAL = 6

BOT_DESCRIPTION = (
    f"{APP_NAME}: управляй Spotify из Telegram.\n\n"
    "▶️ Плеер с обложкой и цветными кнопками\n"
    "📜 Очередь\n"
    "🔎 Поиск треков: просто напиши название\n"
    "📚 Плейлисты, альбомы и исполнители по ссылке\n\n"
    "Это личный бот: он отвечает только своему владельцу."
)


# ---------- оформление ----------


def step(n: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold {GREEN}]Шаг {n} из {TOTAL} · {title}[/]", style=GREEN))


def explain(why: str, where: list[str] | None = None, note: str | None = None) -> None:
    body = f"[bold]Зачем это нужно[/]\n{why}"
    if where:
        body += "\n\n[bold]Где взять[/]\n" + "\n".join(f"  [{GREEN}]{i}.[/] {line}" for i, line in enumerate(where, 1))
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
    console.print(f"[dim]Открываю в браузере:[/] [link={url}]{url}[/link]")
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
    """Спросить значение. Enter оставляет текущее (при повторной настройке)."""
    hint = f" [dim](Enter — оставить {mask(current)})[/]" if current else ""
    while True:
        value = Prompt.ask(f"[bold]{label}[/]{hint}", password=secret, default="", show_default=False).strip()
        if value:
            return value
        if current:
            return current
        fail("Пусто. Вставь значение (в консоли: правая кнопка мыши или Ctrl+V).")


# ---------- шаги ----------


def welcome() -> None:
    console.print()
    console.print(
        Panel(
            f"[bold {GREEN}]{APP_NAME}[/] · {DESCRIPTION}\n\n"
            "Сейчас настроим всё за 5–10 минут. Понадобится:\n"
            "  • аккаунт Telegram;\n"
            "  • аккаунт [bold]Spotify Premium[/] (без Premium Spotify не даёт управлять музыкой);\n"
            "  • браузер: нужные страницы я открою сам.\n\n"
            "[dim]Все ключи сохранятся только на этом компьютере, в файле:[/]\n"
            f"[dim]{SETTINGS}[/]\n"
            "[dim]Никакого сервера TuneCast нет: программа общается с Telegram и Spotify напрямую.[/]",
            title="Добро пожаловать",
            border_style=GREEN,
            padding=(1, 2),
        )
    )
    Prompt.ask("[dim]Нажми Enter, чтобы начать[/]", default="", show_default=False)


def bot_token_step() -> tuple[str, dict]:
    step(1, "Свой бот в Telegram")
    explain(
        "TuneCast работает как [bold]твой личный бот[/]. Токен — это «пароль» бота: по нему программа "
        "на твоём компьютере получает сообщения и отвечает от его имени. Кроме тебя, токен никому не нужен.",
        [
            "Открой [bold]@BotFather[/] в Telegram (сейчас открою ссылку).",
            "Отправь ему команду [bold]/newbot[/].",
            "Придумай имя, например «Мой TuneCast».",
            "Придумай адрес бота: латиницей и с [bold]bot[/] на конце, например [italic]ivan_tunecast_bot[/].",
            "BotFather пришлёт токен вида [italic]123456789:AAH…[/]. Скопируй его сюда.",
        ],
    )
    current = os.getenv("BOT_TOKEN")
    if not current:
        open_url("https://t.me/BotFather")
    while True:
        token = ask("Токен бота", current, secret=False)
        try:
            resp = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
            data = resp.json()
        except Exception as exc:
            fail(f"Нет связи с Telegram ({exc.__class__.__name__}). Проверь интернет и попробуй ещё раз.")
            current = None
            continue
        if data.get("ok"):
            bot = data["result"]
            ok(f"Бот найден: [bold]@{bot['username']}[/] ({bot['first_name']})")
            _set_bot_profile(token)
            return token, bot
        fail("Telegram не принял токен. Скопируй его из сообщения BotFather целиком.")
        current = None


def _set_bot_profile(token: str) -> None:
    """Описание бота в Telegram: его видно до первого /start."""
    api = f"https://api.telegram.org/bot{token}"
    try:
        httpx.post(f"{api}/setMyShortDescription", json={"short_description": DESCRIPTION}, timeout=15)
        httpx.post(f"{api}/setMyDescription", json={"description": BOT_DESCRIPTION}, timeout=15)
    except Exception:
        pass


def owner_step(token: str, bot: dict) -> str:
    step(2, "Кто хозяин бота")
    explain(
        "Бот будет слушаться [bold]только тебя[/]. Иначе любой, кто найдёт его в поиске, "
        "сможет переключать твою музыку. Для этого нужен твой Telegram ID — я узнаю его сам.",
        [f"Открой своего бота [bold]@{bot['username']}[/] (сейчас открою ссылку).", "Нажми [bold]Start[/] («Запустить»)."],
    )
    current = os.getenv("ALLOWED_USER_IDS")
    if current and Confirm.ask(f"Оставить текущего владельца (ID {current})?", default=True):
        return current

    api = f"https://api.telegram.org/bot{token}"
    try:
        httpx.post(f"{api}/deleteWebhook", timeout=15)
    except Exception:
        pass
    open_url(f"https://t.me/{bot['username']}")

    deadline = time.monotonic() + 180
    with console.status("[bold]Жду, когда ты нажмёшь Start в боте…[/]", spinner="dots"):
        while time.monotonic() < deadline:
            try:
                updates = httpx.get(f"{api}/getUpdates", params={"timeout": 20}, timeout=30).json().get("result", [])
            except Exception:
                time.sleep(2)
                continue
            users = [u["message"]["from"] for u in updates if u.get("message", {}).get("from")]
            if users:
                user = users[-1]
                break
        else:
            user = None

    if user:
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        username = f" (@{user['username']})" if user.get("username") else ""
        if Confirm.ask(f"Это ты: [bold]{name}{username}[/], ID {user['id']}?", default=True):
            ok("Владелец бота сохранён")
            return str(user["id"])

    console.print("[dim]Тогда введи ID вручную. Его покажет бот @userinfobot, если написать ему любое сообщение.[/]")
    while True:
        value = ask("Твой Telegram ID")
        if value.isdigit():
            return value
        fail("ID состоит только из цифр.")


def spotify_app_step() -> tuple[str, str]:
    step(3, "Приложение Spotify")
    copied = copy_to_clipboard(REDIRECT_URI)
    explain(
        "Spotify пускает к управлению музыкой только через «приложение разработчика». "
        "Каждый пользователь TuneCast создаёт своё — так ключи и лимиты принадлежат только тебе. "
        "Это бесплатно и занимает пару минут.",
        [
            "Открой [bold]developer.spotify.com/dashboard[/] (сейчас открою) и войди своим аккаунтом Spotify.",
            "Нажми [bold]Create app[/]. Название и описание — любые, например TuneCast.",
            f"В поле [bold]Redirect URIs[/] вставь [bold {GREEN}]{REDIRECT_URI}[/] и нажми [bold]Add[/]"
            + (" [dim](адрес уже скопирован, просто нажми Ctrl+V)[/]" if copied else "."),
            "В «Which API/SDKs are you planning to use?» отметь [bold]Web API[/], согласись с условиями и нажми [bold]Save[/].",
            "Открой [bold]Settings[/]: там будут [bold]Client ID[/] и [bold]Client secret[/] (кнопка View client secret).",
        ],
        "Адрес нужно вставить точно, с 127.0.0.1 (не localhost). На него Spotify вернёт тебя после входа.",
    )
    current_id, current_secret = os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")
    if not current_id:
        open_url("https://developer.spotify.com/dashboard")
    while True:
        client_id = ask("Client ID", current_id)
        client_secret = ask("Client secret", current_secret, secret=True)
        result = _check_spotify(client_id, client_secret)
        if result is None:
            ok("Spotify принял ключи")
            return client_id, client_secret
        fail(result)
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
        return f"Нет связи со Spotify ({exc.__class__.__name__}). Проверь интернет."
    if resp.status_code == 200:
        return None
    return "Spotify не принял Client ID или Client secret. Скопируй их со страницы Settings ещё раз."


def spotify_login_step(values: dict) -> None:
    step(4, "Вход в Spotify")
    explain(
        "Spotify спросит, разрешаешь ли ты своему приложению управлять музыкой: ставить на паузу, "
        "переключать треки, добавлять в очередь. Это делается один раз — потом вход сохранится "
        "в папке data на этом компьютере.",
        ["Сейчас откроется страница Spotify.", "Нажми [bold]Принять[/] (Agree).", "Вернись в это окно."],
    )
    from .spotify import Spotify

    async def login():
        token_path = DATA / "spotify_token.json"
        if token_path.exists():
            token_path.unlink()  # ключи могли поменяться — входим заново
        sp = Spotify(values["SPOTIFY_CLIENT_ID"], values["SPOTIFY_CLIENT_SECRET"], REDIRECT_URI, token_path)
        try:
            await sp.ensure_auth()
            return await sp.me()
        finally:
            await sp.close()

    while True:
        try:
            with console.status("[bold]Жду, когда ты нажмёшь «Принять» в браузере…[/]", spinner="dots"):
                me = asyncio.run(login())
            break
        except Exception as exc:
            fail(f"Не получилось войти: {exc}")
            console.print(
                "[dim]Частая причина — в настройках приложения Spotify не добавлен Redirect URI "
                f"{REDIRECT_URI}. Проверь и попробуй ещё раз.[/]"
            )
            if not Confirm.ask("Попробовать ещё раз?", default=True):
                raise SystemExit(1)
    ok(f"Вход выполнен: [bold]{me.get('display_name') or me.get('id')}[/]")
    if me.get("product") and me["product"] != "premium":
        console.print("[yellow]![/] У этого аккаунта нет Spotify Premium: управлять музыкой Spotify не разрешит.")


def profile_step(values: dict) -> None:
    step(5, "Трек в профиле Telegram (необязательно)")
    explain(
        "TuneCast может показывать то, что играет, в [bold]«Музыке профиля»[/] — плашке «♪ Трек — Исполнитель» "
        "в твоём профиле. Боты не умеют менять профиль, поэтому это делает твой собственный аккаунт "
        "через официальный API Telegram: в профиль загружается беззвучный трек с названием и обложкой.\n"
        "[yellow]Функция экспериментальная.[/] Можно пропустить и включить позже: TuneCast.exe --setup",
        [
            "Открой [bold]my.telegram.org[/] и войди по номеру телефона (код придёт в Telegram).",
            "Выбери [bold]API development tools[/].",
            "Заполни: App title — любое без слова «Telegram», Short name — 5–32 латинских букв или цифр, "
            "Platform — Desktop, URL оставь пустым.",
            "Нажми Create application и скопируй [bold]api_id[/] и [bold]api_hash[/].",
        ],
        "Если сайт пишет «Too many attempts», подожди несколько часов и попробуй без VPN.",
    )
    enabled = bool(os.getenv("TG_API_ID"))
    if not Confirm.ask("Настроить трек в профиле сейчас?", default=enabled):
        values.setdefault("PROFILE_MUSIC_ENABLED", "true" if enabled else "false")
        return
    open_url("https://my.telegram.org/apps")
    while True:
        api_id = ask("api_id", os.getenv("TG_API_ID"))
        if api_id.isdigit():
            break
        fail("api_id состоит только из цифр.")
    api_hash = ask("api_hash", os.getenv("TG_API_HASH"), secret=True)

    console.print(
        Panel(
            "Теперь войдём в твой аккаунт Telegram. Введи номер телефона, затем код, который придёт в Telegram.\n"
            "[bold]Никому не сообщай этот код[/] — TuneCast сохранит вход только в файле "
            f"[italic]data/telegram_user.session[/] на этом компьютере.",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    from telethon import TelegramClient

    async def login():
        client = TelegramClient(str(DATA / "telegram_user"), int(api_id), api_hash)
        await client.start(
            phone=lambda: Prompt.ask("[bold]Номер телефона[/] (в формате +7…)"),
            code_callback=lambda: Prompt.ask("[bold]Код из Telegram[/]"),
            password=lambda: Prompt.ask("[bold]Облачный пароль[/] (если включён)", password=True),
        )
        me = await client.get_me()
        await client.disconnect()
        return me

    try:
        me = asyncio.run(login())
        ok(f"Аккаунт подключён: [bold]{me.first_name}[/]")
        values.update(TG_API_ID=api_id, TG_API_HASH=api_hash, PROFILE_MUSIC_ENABLED="true")
    except Exception as exc:
        fail(f"Не получилось войти: {exc}. Трек в профиле пока выключен, остальное работает.")
        values["PROFILE_MUSIC_ENABLED"] = "false"


def autostart_step() -> None:
    step(6, "Автозапуск")
    explain(
        "TuneCast работает, пока открыто его окно: выключил компьютер — бот замолчал. "
        "Можно запускать его автоматически при входе в Windows, тогда о нём можно не вспоминать."
    )
    startup = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    script = startup / f"{APP_NAME}.cmd"
    if not Confirm.ask("Запускать TuneCast вместе с Windows?", default=script.exists()):
        if script.exists():
            script.unlink()
            ok("Автозапуск выключен")
        return
    if getattr(sys, "frozen", False):
        command = f'start "{APP_NAME}" /min "{sys.executable}"'
    else:
        command = f'start "{APP_NAME}" /min "{sys.executable}" -m tunecast'
    try:
        startup.mkdir(parents=True, exist_ok=True)
        script.write_text(f'@echo off\ncd /d "{ROOT}"\n{command}\n', "utf-8")
        ok("Автозапуск включён")
    except OSError as exc:
        fail(f"Не получилось включить автозапуск: {exc}")


def summary(bot: dict) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_row(f"[{GREEN}]1.[/]", f"Открой бота [bold]@{bot['username']}[/] и напиши [bold]/start[/] — появится плеер.")
    table.add_row(f"[{GREEN}]2.[/]", "Чтобы найти трек, просто отправь боту его название.")
    table.add_row(f"[{GREEN}]3.[/]", "Пришли ссылку из Spotify, чтобы включить плейлист или альбом.")
    table.add_row(f"[{GREEN}]4.[/]", "Есть Telegram Premium? Бот нарисует анимированные эмодзи. В первый раз это "
                  "займёт около 15 минут: Telegram ограничивает скорость создания паков.")
    console.print()
    console.print(Panel(table, title="[bold]Готово![/]", border_style=GREEN, padding=(1, 2)))
    console.print("[dim]Повторить настройку: TuneCast.exe --setup · Остановить бота: закрыть окно или Ctrl+C[/]")


def run_wizard() -> None:
    reload_settings()
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
