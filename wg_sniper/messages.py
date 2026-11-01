"""User-facing bot texts (English)."""
from __future__ import annotations


STRINGS: dict[str, str] = {
    'start_greeting': "👋 Hi! I'm WG-Sniper — I watch new WG-Gesucht listings and push them here.\n\nType /help for the full command list.",
    'help_body': '<b>Commands:</b>\n/start — greeting\n/help — this list\n/ping — liveness + uptime\n/status — IMAP state and recent events\n/stats — listing statistics\n/recent [N] — last N listings (default 5)\n/mem — server memory\n/cpu — CPU load\n/pause — stop notifications (processing continues)\n/resume — resume notifications\n/version — code version',
    'pong': '🏓 pong · uptime {uptime}',
    'status_title': '📡 <b>Status</b>',
    'status_uptime': 'Uptime: {uptime}',
    'status_paused': 'Notifications: {state}',
    'status_last_email': 'Last email: {when}',
    'status_last_connect': 'Last IMAP connect: {when}',
    'status_last_crash': '⚠️ Last crash: {when} — <code>{detail}</code>',
    'state_active': 'active ✅',
    'state_paused': 'paused ⏸',
    'stats_title': '📊 <b>Statistics</b>',
    'stats_total': 'Total: {n}',
    'stats_today': 'Today: {n}',
    'stats_week': 'Last 7 days: {n}',
    'stats_by_city': 'By city:',
    'recent_title': '🕒 Last {n} listings:',
    'recent_empty': 'No processed listings yet.',
    'mem_body': '💾 <b>Memory</b>\nTotal: {total}\nUsed: {used} ({pct}%)\nFree: {free}',
    'cpu_body': '🔥 <b>CPU</b>\nLoad: {pct}%\nLoad average (1/5/15): {la1} / {la5} / {la15}\nCores: {cores}',
    'paused_now': '⏸ Notifications paused. /resume to re-enable.',
    'already_paused': 'Already paused. /resume to re-enable.',
    'resumed_now': '▶️ Notifications resumed.',
    'already_active': 'Notifications are already active.',
    'version_body': '📦 <b>Version</b>\nCommit: <code>{sha}</code>\nBranch: <code>{branch}</code>\nStarted: {started}',
    'unknown_cmd': '🤷 Unknown command. Try /help.',
    'unauthorized': '⛔ This bot is private.',
    'crash_notice': '🚨 <b>WG-Sniper crashed</b>\n<code>{err}</code>\nsystemd should restart it.',
    'startup_notice': '▶️ WG-Sniper started ({sha}).',
}


def t(key: str, **kwargs: object) -> str:
    template = STRINGS.get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
