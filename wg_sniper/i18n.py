from __future__ import annotations

from typing import Literal

Lang = Literal["uk", "en"]
SUPPORTED: tuple[Lang, ...] = ("uk", "en")
DEFAULT_LANG: Lang = "uk"

STRINGS: dict[str, dict[Lang, str]] = {
    "start_greeting": {
        "uk": (
            "👋 Привіт! Я WG-Sniper — моніторю нові оголошення на WG-Gesucht "
            "і надсилаю їх сюди.\n\n"
            "Напиши /help, щоб побачити всі команди."
        ),
        "en": (
            "👋 Hi! I'm WG-Sniper — I watch new WG-Gesucht listings and push "
            "them here.\n\n"
            "Type /help for the full command list."
        ),
    },
    "help_body": {
        "uk": (
            "<b>Команди:</b>\n"
            "/start — привітання\n"
            "/help — цей список\n"
            "/ping — жива відповідь + uptime\n"
            "/status — стан IMAP та останні події\n"
            "/stats — статистика по оголошеннях\n"
            "/recent [N] — останні N оголошень (за замовч. 5)\n"
            "/mem — памʼять сервера\n"
            "/cpu — навантаження CPU\n"
            "/pause — зупинити сповіщення (обробка триває)\n"
            "/resume — відновити сповіщення\n"
            "/lang — переключити мову (UA ⇄ EN)\n"
            "/version — версія коду"
        ),
        "en": (
            "<b>Commands:</b>\n"
            "/start — greeting\n"
            "/help — this list\n"
            "/ping — liveness + uptime\n"
            "/status — IMAP state and recent events\n"
            "/stats — listing statistics\n"
            "/recent [N] — last N listings (default 5)\n"
            "/mem — server memory\n"
            "/cpu — CPU load\n"
            "/pause — stop notifications (processing continues)\n"
            "/resume — resume notifications\n"
            "/lang — switch language (UA ⇄ EN)\n"
            "/version — code version"
        ),
    },
    "pong": {
        "uk": "🏓 pong · uptime {uptime}",
        "en": "🏓 pong · uptime {uptime}",
    },
    "status_title": {
        "uk": "📡 <b>Статус</b>",
        "en": "📡 <b>Status</b>",
    },
    "status_uptime": {"uk": "Uptime: {uptime}", "en": "Uptime: {uptime}"},
    "status_paused": {
        "uk": "Сповіщення: {state}",
        "en": "Notifications: {state}",
    },
    "status_last_email": {
        "uk": "Останній лист: {when}",
        "en": "Last email: {when}",
    },
    "status_last_connect": {
        "uk": "Останній IMAP-конект: {when}",
        "en": "Last IMAP connect: {when}",
    },
    "status_last_crash": {
        "uk": "⚠️ Останній збій: {when} — <code>{detail}</code>",
        "en": "⚠️ Last crash: {when} — <code>{detail}</code>",
    },
    "state_active": {"uk": "активні ✅", "en": "active ✅"},
    "state_paused": {"uk": "на паузі ⏸", "en": "paused ⏸"},
    "stats_title": {
        "uk": "📊 <b>Статистика</b>",
        "en": "📊 <b>Statistics</b>",
    },
    "stats_total": {"uk": "Всього: {n}", "en": "Total: {n}"},
    "stats_today": {"uk": "Сьогодні: {n}", "en": "Today: {n}"},
    "stats_week": {"uk": "За 7 днів: {n}", "en": "Last 7 days: {n}"},
    "stats_by_city": {"uk": "По містах:", "en": "By city:"},
    "recent_title": {
        "uk": "🕒 Останні {n} оголошень:",
        "en": "🕒 Last {n} listings:",
    },
    "recent_empty": {
        "uk": "Ще немає оброблених оголошень.",
        "en": "No processed listings yet.",
    },
    "mem_body": {
        "uk": (
            "💾 <b>Памʼять</b>\n"
            "Всього: {total}\n"
            "Використано: {used} ({pct}%)\n"
            "Вільно: {free}"
        ),
        "en": (
            "💾 <b>Memory</b>\n"
            "Total: {total}\n"
            "Used: {used} ({pct}%)\n"
            "Free: {free}"
        ),
    },
    "cpu_body": {
        "uk": (
            "🔥 <b>CPU</b>\n"
            "Навантаження: {pct}%\n"
            "Load average (1/5/15): {la1} / {la5} / {la15}\n"
            "Ядер: {cores}"
        ),
        "en": (
            "🔥 <b>CPU</b>\n"
            "Load: {pct}%\n"
            "Load average (1/5/15): {la1} / {la5} / {la15}\n"
            "Cores: {cores}"
        ),
    },
    "paused_now": {
        "uk": "⏸ Сповіщення зупинено. /resume — відновити.",
        "en": "⏸ Notifications paused. /resume to re-enable.",
    },
    "already_paused": {
        "uk": "Уже на паузі. /resume — відновити.",
        "en": "Already paused. /resume to re-enable.",
    },
    "resumed_now": {
        "uk": "▶️ Сповіщення відновлено.",
        "en": "▶️ Notifications resumed.",
    },
    "already_active": {
        "uk": "Сповіщення вже активні.",
        "en": "Notifications are already active.",
    },
    "lang_switched": {
        "uk": "🇺🇦 Мову переключено на українську.",
        "en": "🇬🇧 Language switched to English.",
    },
    "version_body": {
        "uk": (
            "📦 <b>Версія</b>\n"
            "Commit: <code>{sha}</code>\n"
            "Гілка: <code>{branch}</code>\n"
            "Запущено: {started}"
        ),
        "en": (
            "📦 <b>Version</b>\n"
            "Commit: <code>{sha}</code>\n"
            "Branch: <code>{branch}</code>\n"
            "Started: {started}"
        ),
    },
    "unknown_cmd": {
        "uk": "🤷 Не знаю такої команди. Спробуй /help.",
        "en": "🤷 Unknown command. Try /help.",
    },
    "unauthorized": {
        "uk": "⛔ Цей бот приватний.",
        "en": "⛔ This bot is private.",
    },
    "crash_notice": {
        "uk": (
            "🚨 <b>WG-Sniper впав</b>\n"
            "<code>{err}</code>\n"
            "systemd має перезапустити."
        ),
        "en": (
            "🚨 <b>WG-Sniper crashed</b>\n"
            "<code>{err}</code>\n"
            "systemd should restart it."
        ),
    },
    "startup_notice": {
        "uk": "▶️ WG-Sniper запущено ({sha}).",
        "en": "▶️ WG-Sniper started ({sha}).",
    },
}


def t(key: str, lang: Lang, **kwargs: object) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    template = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def normalize(lang: str | None) -> Lang:
    if lang in SUPPORTED:
        return lang  # type: ignore[return-value]
    return DEFAULT_LANG
