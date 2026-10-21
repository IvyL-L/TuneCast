"""Translations: English (default) and Russian.

t("key", name=value) returns the string in the current language.
pl(n, "track") returns "3 tracks" / "3 трека".
"""

LANGUAGES = ("en", "ru")
LANGUAGE_NAMES = {"en": "English", "ru": "Русский"}
FLAGS = {"en": "🇬🇧", "ru": "🇷🇺"}

_lang = "en"


def set_lang(code: str | None) -> str:
    global _lang
    _lang = code if code in LANGUAGES else "en"
    return _lang


def lang() -> str:
    return _lang


def t(key: str, **values) -> str:
    en, ru = S[key]
    text = ru if _lang == "ru" else en
    return text.format(**values) if values else text


_PLURALS = {
    "track": (("track", "tracks"), ("трек", "трека", "треков")),
    "playlist": (("playlist", "playlists"), ("плейлист", "плейлиста", "плейлистов")),
}


def pl(n: int, word: str) -> str:
    en, ru = _PLURALS[word]
    if _lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            form = ru[0]
        elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            form = ru[1]
        else:
            form = ru[2]
    else:
        form = en[0] if n == 1 else en[1]
    return f"{n} {form}"


S: dict[str, tuple[str, str]] = {
    # ---------- common ----------
    "app.tagline": ("Control Spotify from Telegram", "Управляй Spotify из Telegram"),
    "untitled": ("Untitled", "Без названия"),
    "podcast": ("Podcast", "Подкаст"),
    "unknown_artist": ("Unknown artist", "Неизвестный исполнитель"),
    "device": ("device", "устройство"),
    "liked_songs": ("Liked Songs", "Любимые треки"),
    # ---------- buttons ----------
    "btn.pause": ("Pause", "Пауза"),
    "btn.play": ("Play", "Играть"),
    "btn.queue": ("Queue", "Очередь"),
    "btn.playlists": ("Playlists", "Плейлисты"),
    "btn.liked": ("Liked", "Любимые"),
    "btn.liked_songs": ("Liked Songs", "Любимые треки"),
    "btn.devices": ("Devices", "Устройства"),
    "btn.refresh": ("Refresh", "Обновить"),
    "btn.next": ("Next", "Следующий"),
    "btn.to_player": ("Player", "К плееру"),
    "btn.back": ("Back", "Назад"),
    "btn.close": ("Close", "Закрыть"),
    "btn.shuffle_play": ("Shuffle", "Вперемешку"),
    "btn.more": ("More", "Ещё"),
    "btn.add_queue": ("Add to queue", "В очередь"),
    "btn.play_now": ("Play now", "Включить"),
    "btn.open_player": ("Open player", "Открыть плеер"),
    "btn.change": ("change", "изменить"),
    "btn.reset": ("reset", "сброс"),
    "btn.reset_all": ("Reset all", "Сбросить все"),
    "btn.done": ("Done", "Готово"),
    # ---------- player ----------
    "player.idle": ("Nothing is playing", "Сейчас ничего не играет"),
    "player.idle_hint": ("Start Spotify on any device or pick a playlist", "Включи Spotify на любом устройстве или выбери плейлист"),
    "player.search_hint": ("To find a track, just send me its name", "Чтобы найти трек, просто напиши мне его название"),
    "player.playing": ("Playing", "Играет"),
    "player.paused": ("Paused", "Пауза"),
    # ---------- queue ----------
    "queue.title": ("Queue", "Очередь"),
    "queue.up_next": ("{tracks} up next", "дальше {tracks}"),
    "queue.empty": ("empty for now", "пока пусто"),
    "queue.track": ("Track", "Трек"),
    "queue.add_hint": ("Send me a track name and I'll add it to the queue", "Напиши название трека, и я добавлю его в очередь"),
    # ---------- playlists & cards ----------
    "pl.title": ("Your playlists", "Твои плейлисты"),
    "pl.link_hint": ("You can also send a link to any Spotify playlist or album", "Можно прислать ссылку на любой плейлист или альбом из Spotify"),
    "kind.playlist": ("Playlist", "Плейлист"),
    "kind.album": ("Album", "Альбом"),
    "kind.artist": ("Artist", "Исполнитель"),
    "card.description": ("Description", "Описание"),
    # ---------- devices ----------
    "dev.title": ("Devices", "Устройства"),
    "dev.hint": ("Tap a device to move the music there", "Нажми, чтобы перенести музыку"),
    "dev.none": (
        "I can't see any devices. Open Spotify on your PC or phone and tap Refresh.",
        "Не вижу ни одного устройства. Открой Spotify на ПК или телефоне и нажми «Обновить».",
    ),
    # ---------- search ----------
    "search.none": ("Nothing found", "Ничего не нашёл"),
    "search.none_hint": ("Try different wording, e.g. “artist — track”.", "Попробуй написать иначе, например «исполнитель — трек»."),
    "search.to_queue": ("add to queue", "в очередь"),
    "search.play_now": ("play now", "включить сразу"),
    # ---------- help ----------
    "help.can": ("What I can do", "Что я умею"),
    "help.f1": ("Control playback: pause, skip, shuffle, volume", "Управлять музыкой: пауза, переключение, перемешивание, громкость"),
    "help.f2": ("Show the queue", "Показывать очередь"),
    "help.f3": ("Search tracks and add them to the queue", "Искать треки и добавлять их в очередь"),
    "help.f4": ("Play playlists, albums and artists", "Включать плейлисты, альбомы и исполнителей"),
    "help.f5": ("Show the current track in your Telegram profile", "Показывать текущий трек в профиле Telegram"),
    "help.how": ("How to use", "Как пользоваться"),
    "help.h1": ("<b>/start</b> — open the player", "<b>/start</b> — открыть плеер"),
    "help.h2": ("Send a track name to search for it", "Напиши название трека, чтобы найти его"),
    "help.h3": ("Send a Spotify link to play a playlist, album or track", "Пришли ссылку из Spotify, чтобы включить плейлист, альбом или трек"),
    "help.h4": ("<b>/emoji</b> — replace icons with your own emoji", "<b>/emoji</b> — заменить иконки своими эмодзи"),
    "help.h5": ("<b>/language</b> — switch language", "<b>/language</b> — сменить язык"),
    # ---------- emoji settings ----------
    "emoji.title": ("Bot emoji", "Эмодзи бота"),
    "emoji.custom": ("Custom emoji", "Свои эмодзи"),
    "emoji.need_premium": ("Telegram Premium required", "нужен Telegram Premium"),
    "emoji.no_premium": (
        "The bot can use animated emoji only if its owner has Telegram Premium. Regular emoji are used for now; "
        "everything switches automatically once Premium is active.",
        "Анимированные эмодзи бот может ставить, только если у владельца бота есть Telegram Premium. "
        "Сейчас используются обычные эмодзи. Когда Premium появится, всё переключится само.",
    ),
    "emoji.replaced": ("{n} replaced", "{n} заменено"),
    "emoji.waiting": (
        "Send me an emoji for “{label}”: from any Premium pack or a regular one.",
        "Пришли мне эмодзи для «{label}»: любой из Premium-паков или обычный.",
    ),
    "emoji.hint": (
        "Tap “change” and send any emoji. The animated TuneCast packs are used by default.",
        "Нажми «изменить» и пришли любой эмодзи. Анимированные паки TuneCast добавлены по умолчанию.",
    ),
    "emoji.not_emoji": (
        "That doesn't look like an emoji. Tap “change” again and send a single emoji.",
        "Это не похоже на эмодзи. Нажми «изменить» ещё раз и пришли один эмодзи.",
    ),
    "emoji.send_for": ("Send an emoji for “{label}”", "Пришли эмодзи для «{label}»"),
    "emoji.reset_done": ("Reset", "Сброшено"),
    "pack.icons": ("TuneCast · icons", "TuneCast · иконки"),
    "pack.art": ("TuneCast · accents", "TuneCast · акценты"),
    # ---------- language ----------
    "lang.title": ("Language", "Язык"),
    "lang.hint": ("Choose the bot language", "Выбери язык бота"),
    "lang.set": ("Language: English", "Язык: русский"),
    # ---------- toasts & alerts ----------
    "t.no_devices": ("😴 No devices available.\nOpen Spotify on your PC or phone.", "😴 Нет доступных устройств.\nОткрой Spotify на ПК или телефоне."),
    "t.pick_device": ("📱 Choose where to play", "📱 Выбери, где играть"),
    "t.premium": ("💎 Spotify Premium is required for playback control", "💎 Для управления нужен Spotify Premium"),
    "t.device_silent": ("😴 The device isn't responding. Open Spotify and try again.", "😴 Устройство не отвечает. Открой Spotify и попробуй ещё раз."),
    "t.refreshed": ("🔄 Refreshed", "🔄 Обновлено"),
    "t.paused": ("⏸ Paused", "⏸ Пауза"),
    "t.playing": ("▶️ Playing", "▶️ Играет"),
    "t.next": ("⏭ Next", "⏭ Следующий"),
    "t.prev": ("⏮ Previous", "⏮ Предыдущий"),
    "t.shuffle_on": ("🔀 Shuffle on", "🔀 Перемешивание включено"),
    "t.shuffle_off": ("🔀 Shuffle off", "🔀 Перемешивание выключено"),
    "t.repeat_off": ("🔁 Repeat off", "🔁 Повтор выключен"),
    "t.repeat_context": ("🔁 Repeat all", "🔁 Повтор всего"),
    "t.repeat_track": ("🔂 Repeat track", "🔂 Повтор трека"),
    "t.volume": ("🔊 Volume {v}%", "🔊 Громкость {v}%"),
    "t.no_volume": ("volume can't be changed on this device", "громкость на этом устройстве не регулируется"),
    "t.shuffled": ("🔀 Playing shuffled", "🔀 Играет вперемешку"),
    "t.go": ("▶️ Here we go!", "▶️ Поехали!"),
    "t.liked_empty": ("💚 No liked songs yet", "💚 В любимых пока пусто"),
    "t.liked_playing": ("💚 Playing your liked songs", "💚 Играют любимые треки"),
    "t.switching": ("📱 Switching device", "📱 Переключаю устройство"),
    "t.search_expired": ("⌛ This search has expired, send it again", "⌛ Поиск устарел, отправь запрос ещё раз"),
    "t.queued": ("✅ Queued: {name}", "✅ В очереди: {name}"),
    "t.track": ("track", "трек"),
    "t.spotify_error": ("⚠️ Spotify: {msg}", "⚠️ Spotify: {msg}"),
    # ---------- bot commands ----------
    "cmd.start": ("🎧 Player", "🎧 Плеер"),
    "cmd.queue": ("📜 Queue", "📜 Очередь"),
    "cmd.playlists": ("📚 Playlists", "📚 Плейлисты"),
    "cmd.devices": ("📱 Devices", "📱 Устройства"),
    "cmd.emoji": ("✨ Custom emoji", "✨ Свои эмодзи"),
    "cmd.language": ("🌐 Language", "🌐 Язык"),
    "cmd.help": ("❓ Help", "❓ Помощь"),
    # ---------- bot profile (shown before /start) ----------
    "bot.description": (
        "TuneCast: control Spotify from Telegram.\n\n"
        "▶️ A player with album art and colored buttons\n"
        "📜 Queue\n"
        "🔎 Track search: just send a name\n"
        "📚 Playlists, albums and artists from links\n\n"
        "This is a personal bot: it only answers its owner.",
        "TuneCast: управляй Spotify из Telegram.\n\n"
        "▶️ Плеер с обложкой и цветными кнопками\n"
        "📜 Очередь\n"
        "🔎 Поиск треков: просто напиши название\n"
        "📚 Плейлисты, альбомы и исполнители по ссылке\n\n"
        "Это личный бот: он отвечает только своему владельцу.",
    ),
    # ---------- Spotify sign-in page ----------
    "login.page_title": ("Spotify connected", "Spotify подключён"),
    "login.page_text": ("You can close this tab and go back to Telegram.", "Вкладку можно закрыть и вернуться в Telegram."),
    "login.denied": ("Sign-in was declined", "Вход отклонён"),
    "login.open": ("🎧 Sign in to Spotify with this link (it should open by itself):", "🎧 Войди в Spotify по ссылке (она должна открыться сама):"),
    # ---------- emoji labels (/emoji) ----------
    "label.play": ("Play", "Играть"),
    "label.pause": ("Pause", "Пауза"),
    "label.next": ("Next", "Следующий"),
    "label.prev": ("Previous", "Предыдущий"),
    "label.shuffle": ("Shuffle", "Перемешать"),
    "label.repeat": ("Repeat", "Повтор"),
    "label.repeat_one": ("Repeat track", "Повтор трека"),
    "label.vol_down": ("Volume down", "Тише"),
    "label.vol_up": ("Volume up", "Громче"),
    "label.queue": ("Queue", "Очередь"),
    "label.library": ("Playlists", "Плейлисты"),
    "label.devices": ("Devices", "Устройства"),
    "label.refresh": ("Refresh", "Обновить"),
    "label.search": ("Search", "Поиск"),
    "label.plus": ("Add to queue", "В очередь"),
    "label.close": ("Close", "Закрыть"),
    "label.back": ("Back", "Назад"),
    "label.computer": ("Computer", "Компьютер"),
    "label.phone": ("Phone", "Телефон"),
    "label.speaker": ("Speaker", "Колонка"),
    "label.music": ("Track", "Трек"),
    "label.heart_outline": ("Heart (outline)", "Сердце (контур)"),
    "label.disc": ("Album", "Альбом"),
    "label.clock": ("Duration", "Длительность"),
    "label.equalizer": ("Playing", "Играет"),
    "label.equalizer_paused": ("Paused", "На паузе"),
    "label.vinyl": ("Vinyl", "Винил"),
    "label.heart": ("Liked", "Любимые"),
    "label.note": ("Note", "Нота"),
    "label.live": ("Live", "В эфире"),
    "label.sleep": ("Nothing playing", "Ничего не играет"),
    # ---------- console: running bot ----------
    "run.title": ("{app} is running", "{app} работает"),
    "run.bot": ("bot", "бот"),
    "run.write_start": ("Send /start to your bot", "Напиши боту /start"),
    "run.profile": ("Track in profile", "Трек в профиле"),
    "run.on": ("on", "включён"),
    "run.off": ("off", "выключен"),
    "run.hint": ("The bot runs while this window is open. To stop: close the window or press Ctrl+C",
                 "Бот работает, пока открыто это окно. Остановить: закрыть окно или Ctrl+C"),
    "run.stopped": ("TuneCast stopped", "TuneCast остановлен"),
    "run.crashed": (
        "TuneCast stopped because of the error above. If you can't figure it out, open an issue on GitHub "
        "and attach the error text (without your keys!).",
        "TuneCast остановился из-за ошибки выше. Если не получается разобраться, создай issue на GitHub "
        "и приложи текст ошибки (без ключей!).",
    ),
    "run.press_enter": ("Press Enter to close this window…", "Нажми Enter, чтобы закрыть окно…"),
    "run.setup_interrupted": (
        "Setup interrupted. Everything entered so far is saved; the wizard will continue with these values next time.",
        "Настройка прервана. Уже введённое сохранено, при следующем запуске мастер продолжит с этими значениями.",
    ),
    "run.not_configured": ("Settings are missing: {keys}. Run TuneCast.exe --setup",
                           "Не заполнены настройки: {keys}. Запусти TuneCast.exe --setup"),
    # ---------- setup wizard: common ----------
    "w.step": ("Step {n} of {total} · {title}", "Шаг {n} из {total} · {title}"),
    "w.why": ("Why this is needed", "Зачем это нужно"),
    "w.where": ("Where to get it", "Где взять"),
    "w.keep": ("Enter keeps {value}", "Enter — оставить {value}"),
    "w.empty": ("Empty. Paste the value (in the console: right-click or Ctrl+V).",
                "Пусто. Вставь значение (в консоли: правая кнопка мыши или Ctrl+V)."),
    "w.opening": ("Opening in the browser:", "Открываю в браузере:"),
    "w.no_net": ("No connection to {service} ({err}). Check your internet and try again.",
                 "Нет связи с {service} ({err}). Проверь интернет и попробуй ещё раз."),
    "w.welcome_title": ("Welcome", "Добро пожаловать"),
    "w.welcome": (
        "Setup takes 5–10 minutes. You'll need:\n"
        "  • a Telegram account;\n"
        "  • a [bold]Spotify Premium[/] account (Spotify doesn't allow playback control without it);\n"
        "  • a browser: I'll open the right pages for you.\n\n"
        "[dim]All keys are saved only on this computer, in:[/]\n"
        "[dim]{path}[/]\n"
        "[dim]There is no TuneCast server: the app talks to Telegram and Spotify directly.[/]",
        "Сейчас настроим всё за 5–10 минут. Понадобится:\n"
        "  • аккаунт Telegram;\n"
        "  • аккаунт [bold]Spotify Premium[/] (без Premium Spotify не даёт управлять музыкой);\n"
        "  • браузер: нужные страницы я открою сам.\n\n"
        "[dim]Все ключи сохранятся только на этом компьютере, в файле:[/]\n"
        "[dim]{path}[/]\n"
        "[dim]Никакого сервера TuneCast нет: программа общается с Telegram и Spotify напрямую.[/]",
    ),
    "w.press_enter": ("Press Enter to start", "Нажми Enter, чтобы начать"),
    # ---------- step 1: bot token ----------
    "w.s1.title": ("Your Telegram bot", "Свой бот в Telegram"),
    "w.s1.why": (
        "TuneCast works as [bold]your personal bot[/]. The token is the bot's \"password\": with it, the app "
        "on your computer receives messages and replies on the bot's behalf. Nobody else needs it.",
        "TuneCast работает как [bold]твой личный бот[/]. Токен — это «пароль» бота: по нему программа "
        "на твоём компьютере получает сообщения и отвечает от его имени. Кроме тебя, токен никому не нужен.",
    ),
    "w.s1.w1": ("Open [bold]@BotFather[/] in Telegram (I'll open the link now).", "Открой [bold]@BotFather[/] в Telegram (сейчас открою ссылку)."),
    "w.s1.w2": ("Send it the [bold]/newbot[/] command.", "Отправь ему команду [bold]/newbot[/]."),
    "w.s1.w3": ("Pick a name, e.g. \"My TuneCast\".", "Придумай имя, например «Мой TuneCast»."),
    "w.s1.w4": ("Pick a username: Latin letters, ending in [bold]bot[/], e.g. [italic]john_tunecast_bot[/].",
                "Придумай адрес бота: латиницей и с [bold]bot[/] на конце, например [italic]ivan_tunecast_bot[/]."),
    "w.s1.w5": ("BotFather sends a token like [italic]123456789:AAH…[/]. Paste it here.",
                "BotFather пришлёт токен вида [italic]123456789:AAH…[/]. Скопируй его сюда."),
    "w.s1.prompt": ("Bot token", "Токен бота"),
    "w.s1.ok": ("Bot found: [bold]@{username}[/] ({name})", "Бот найден: [bold]@{username}[/] ({name})"),
    "w.s1.bad": ("Telegram didn't accept the token. Copy it from BotFather's message in full.",
                 "Telegram не принял токен. Скопируй его из сообщения BotFather целиком."),
    # ---------- step 2: owner ----------
    "w.s2.title": ("Bot owner", "Кто хозяин бота"),
    "w.s2.why": (
        "The bot will obey [bold]only you[/]. Otherwise anyone who finds it could control your music. "
        "That needs your Telegram ID — I'll detect it myself.",
        "Бот будет слушаться [bold]только тебя[/]. Иначе любой, кто найдёт его в поиске, "
        "сможет переключать твою музыку. Для этого нужен твой Telegram ID — я узнаю его сам.",
    ),
    "w.s2.w1": ("Open your bot [bold]@{username}[/] (I'll open the link now).", "Открой своего бота [bold]@{username}[/] (сейчас открою ссылку)."),
    "w.s2.w2": ("Press [bold]Start[/].", "Нажми [bold]Start[/] («Запустить»)."),
    "w.s2.keep": ("Keep the current owner (ID {id})?", "Оставить текущего владельца (ID {id})?"),
    "w.s2.waiting": ("Waiting for you to press Start in the bot…", "Жду, когда ты нажмёшь Start в боте…"),
    "w.s2.is_you": ("Is this you: [bold]{name}[/], ID {id}?", "Это ты: [bold]{name}[/], ID {id}?"),
    "w.s2.saved": ("Bot owner saved", "Владелец бота сохранён"),
    "w.s2.manual": ("Then enter the ID manually. @userinfobot shows it if you send it any message.",
                    "Тогда введи ID вручную. Его покажет бот @userinfobot, если написать ему любое сообщение."),
    "w.s2.prompt": ("Your Telegram ID", "Твой Telegram ID"),
    "w.s2.digits": ("The ID consists of digits only.", "ID состоит только из цифр."),
    # ---------- step 3: Spotify app ----------
    "w.s3.title": ("Spotify app", "Приложение Spotify"),
    "w.s3.why": (
        "Spotify only allows playback control through a \"developer app\". Every TuneCast user creates their own: "
        "this way the keys and limits belong only to you. It's free and takes a couple of minutes.",
        "Spotify пускает к управлению музыкой только через «приложение разработчика». "
        "Каждый пользователь TuneCast создаёт своё — так ключи и лимиты принадлежат только тебе. "
        "Это бесплатно и занимает пару минут.",
    ),
    "w.s3.w1": ("Open [bold]developer.spotify.com/dashboard[/] (I'll open it now) and sign in with your Spotify account.",
                "Открой [bold]developer.spotify.com/dashboard[/] (сейчас открою) и войди своим аккаунтом Spotify."),
    "w.s3.w2": ("Click [bold]Create app[/]. Name and description can be anything, e.g. TuneCast.",
                "Нажми [bold]Create app[/]. Название и описание — любые, например TuneCast."),
    "w.s3.w3": ("In [bold]Redirect URIs[/] paste [bold #1ed760]{uri}[/] and click [bold]Add[/]{copied}",
                "В поле [bold]Redirect URIs[/] вставь [bold #1ed760]{uri}[/] и нажми [bold]Add[/]{copied}"),
    "w.s3.copied": (" [dim](already copied, just press Ctrl+V)[/]", " [dim](адрес уже скопирован, просто нажми Ctrl+V)[/]"),
    "w.s3.w4": ("Under \"Which API/SDKs are you planning to use?\" tick [bold]Web API[/], accept the terms and click [bold]Save[/].",
                "В «Which API/SDKs are you planning to use?» отметь [bold]Web API[/], согласись с условиями и нажми [bold]Save[/]."),
    "w.s3.w5": ("Open [bold]Settings[/]: there you'll find the [bold]Client ID[/] and [bold]Client secret[/] (View client secret button).",
                "Открой [bold]Settings[/]: там будут [bold]Client ID[/] и [bold]Client secret[/] (кнопка View client secret)."),
    "w.s3.note": ("The address must be exact, with 127.0.0.1 (not localhost). Spotify sends you back to it after sign-in.",
                  "Адрес нужно вставить точно, с 127.0.0.1 (не localhost). На него Spotify вернёт тебя после входа."),
    "w.s3.ok": ("Spotify accepted the keys", "Spotify принял ключи"),
    "w.s3.bad": ("Spotify didn't accept the Client ID or Client secret. Copy them from the Settings page again.",
                 "Spotify не принял Client ID или Client secret. Скопируй их со страницы Settings ещё раз."),
    # ---------- step 4: Spotify sign-in ----------
    "w.s4.title": ("Spotify sign-in", "Вход в Spotify"),
    "w.s4.why": (
        "Spotify will ask whether you allow your app to control your music: pause, skip tracks, add to the queue. "
        "You do this once; the sign-in is then saved in the data folder on this computer.",
        "Spotify спросит, разрешаешь ли ты своему приложению управлять музыкой: ставить на паузу, "
        "переключать треки, добавлять в очередь. Это делается один раз — потом вход сохранится "
        "в папке data на этом компьютере.",
    ),
    "w.s4.w1": ("A Spotify page will open now.", "Сейчас откроется страница Spotify."),
    "w.s4.w2": ("Click [bold]Agree[/].", "Нажми [bold]Принять[/] (Agree)."),
    "w.s4.w3": ("Come back to this window.", "Вернись в это окно."),
    "w.s4.waiting": ("Waiting for you to click Agree in the browser…", "Жду, когда ты нажмёшь «Принять» в браузере…"),
    "w.s4.fail": ("Couldn't sign in: {err}", "Не получилось войти: {err}"),
    "w.s4.hint": ("A common cause: the Redirect URI {uri} isn't added in the Spotify app settings. Check it and try again.",
                  "Частая причина — в настройках приложения Spotify не добавлен Redirect URI {uri}. Проверь и попробуй ещё раз."),
    "w.s4.retry": ("Try again?", "Попробовать ещё раз?"),
    "w.s4.ok": ("Signed in: [bold]{name}[/]", "Вход выполнен: [bold]{name}[/]"),
    "w.s4.no_premium": ("This account has no Spotify Premium: Spotify won't allow playback control.",
                        "У этого аккаунта нет Spotify Premium: управлять музыкой Spotify не разрешит."),
    # ---------- step 5: profile track ----------
    "w.s5.title": ("Track in your Telegram profile (optional)", "Трек в профиле Telegram (необязательно)"),
    "w.s5.why": (
        "TuneCast can show what's playing in your profile's [bold]music section[/] — the \"♪ Track — Artist\" bar. "
        "Bots can't change profiles, so your own account does it through the official Telegram API: a silent track "
        "with the title and cover is uploaded to your profile.\n"
        "[yellow]This feature is experimental.[/] You can skip it and enable it later: TuneCast.exe --setup",
        "TuneCast может показывать то, что играет, в [bold]«Музыке профиля»[/] — плашке «♪ Трек — Исполнитель» "
        "в твоём профиле. Боты не умеют менять профиль, поэтому это делает твой собственный аккаунт "
        "через официальный API Telegram: в профиль загружается беззвучный трек с названием и обложкой.\n"
        "[yellow]Функция экспериментальная.[/] Можно пропустить и включить позже: TuneCast.exe --setup",
    ),
    "w.s5.w1": ("Open [bold]my.telegram.org[/] and sign in with your phone number (the code arrives in Telegram).",
                "Открой [bold]my.telegram.org[/] и войди по номеру телефона (код придёт в Telegram)."),
    "w.s5.w2": ("Choose [bold]API development tools[/].", "Выбери [bold]API development tools[/]."),
    "w.s5.w3": ("Fill in: App title — anything without the word \"Telegram\", Short name — 5–32 Latin letters or digits, "
                "Platform — Desktop, leave URL empty.",
                "Заполни: App title — любое без слова «Telegram», Short name — 5–32 латинских букв или цифр, "
                "Platform — Desktop, URL оставь пустым."),
    "w.s5.w4": ("Click Create application and copy [bold]api_id[/] and [bold]api_hash[/].",
                "Нажми Create application и скопируй [bold]api_id[/] и [bold]api_hash[/]."),
    "w.s5.note": ("If the site says \"Too many attempts\", wait a few hours and try without a VPN.",
                  "Если сайт пишет «Too many attempts», подожди несколько часов и попробуй без VPN."),
    "w.s5.ask": ("Set up the profile track now?", "Настроить трек в профиле сейчас?"),
    "w.s5.digits": ("api_id consists of digits only.", "api_id состоит только из цифр."),
    "w.s5.login": (
        "Now let's sign in to your Telegram account. Enter your phone number, then the code Telegram sends you.\n"
        "[bold]Never share this code[/] — TuneCast keeps the sign-in only in [italic]data/telegram_user.session[/] on this computer.",
        "Теперь войдём в твой аккаунт Telegram. Введи номер телефона, затем код, который придёт в Telegram.\n"
        "[bold]Никому не сообщай этот код[/] — TuneCast сохранит вход только в файле "
        "[italic]data/telegram_user.session[/] на этом компьютере.",
    ),
    "w.s5.phone": ("Phone number (international format, e.g. +1…)", "Номер телефона (в формате +7…)"),
    "w.s5.code": ("Code from Telegram", "Код из Telegram"),
    "w.s5.password": ("Cloud password (if enabled)", "Облачный пароль (если включён)"),
    "w.s5.ok": ("Account connected: [bold]{name}[/]", "Аккаунт подключён: [bold]{name}[/]"),
    "w.s5.fail": ("Couldn't sign in: {err}. The profile track stays off; everything else works.",
                  "Не получилось войти: {err}. Трек в профиле пока выключен, остальное работает."),
    # ---------- step 6: autostart ----------
    "w.s6.title": ("Autostart", "Автозапуск"),
    "w.s6.why": (
        "TuneCast works while its window is open: turn off the computer and the bot goes quiet. "
        "It can start automatically when you sign in to Windows, so you can forget about it.",
        "TuneCast работает, пока открыто его окно: выключил компьютер — бот замолчал. "
        "Можно запускать его автоматически при входе в Windows, тогда о нём можно не вспоминать.",
    ),
    "w.s6.ask": ("Start TuneCast with Windows?", "Запускать TuneCast вместе с Windows?"),
    "w.s6.on": ("Autostart enabled", "Автозапуск включён"),
    "w.s6.off": ("Autostart disabled", "Автозапуск выключен"),
    "w.s6.fail": ("Couldn't enable autostart: {err}", "Не получилось включить автозапуск: {err}"),
    # ---------- summary ----------
    "w.done": ("Done!", "Готово!"),
    "w.d1": ("Open your bot [bold]@{username}[/] and send [bold]/start[/] — the player will appear.",
             "Открой бота [bold]@{username}[/] и напиши [bold]/start[/] — появится плеер."),
    "w.d2": ("To find a track, just send the bot its name.", "Чтобы найти трек, просто отправь боту его название."),
    "w.d3": ("Send a Spotify link to play a playlist or album.", "Пришли ссылку из Spotify, чтобы включить плейлист или альбом."),
    "w.d4": ("Have Telegram Premium? The bot will draw animated emoji. The first time takes about 15 minutes: "
             "Telegram limits how fast packs can be created.",
             "Есть Telegram Premium? Бот нарисует анимированные эмодзи. В первый раз это займёт около 15 минут: "
             "Telegram ограничивает скорость создания паков."),
    "w.d5": ("Switch the language anytime with [bold]/language[/] in the bot.", "Сменить язык можно в любой момент командой [bold]/language[/] в боте."),
    "w.footer": ("Change settings: TuneCast.exe --setup · Stop the bot: close the window or Ctrl+C",
                 "Повторить настройку: TuneCast.exe --setup · Остановить бота: закрыть окно или Ctrl+C"),
}
