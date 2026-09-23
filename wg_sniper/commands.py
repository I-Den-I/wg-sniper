from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import aiosqlite
import psutil
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from . import db as dbmod
from .i18n import t
from .notifier import format_listing
from .state import State

log = logging.getLogger(__name__)


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _iso_ago(iso_str: str | None, lang) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
    except ValueError:
        return iso_str
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago" if lang == "en" else f"{secs} с тому"
    if secs < 3600:
        return f"{secs // 60}m ago" if lang == "en" else f"{secs // 60} хв тому"
    if secs < 86400:
        return f"{secs // 3600}h ago" if lang == "en" else f"{secs // 3600} год тому"
    return f"{secs // 86400}d ago" if lang == "en" else f"{secs // 86400} дн тому"


def build_dispatcher(state: State, chat_id: int) -> Dispatcher:
    dp = Dispatcher()
    router = Router()

    @router.message(F.chat.id != chat_id)
    async def deny_others(msg: Message) -> None:
        await msg.answer(t("unauthorized", state.lang))

    @router.message(CommandStart())
    async def cmd_start(msg: Message) -> None:
        await msg.answer(t("start_greeting", state.lang))

    @router.message(Command("help"))
    async def cmd_help(msg: Message) -> None:
        await msg.answer(t("help_body", state.lang))

    @router.message(Command("ping"))
    async def cmd_ping(msg: Message) -> None:
        await msg.answer(t("pong", state.lang, uptime=state.uptime_str()))

    @router.message(Command("status"))
    async def cmd_status(msg: Message) -> None:
        async with aiosqlite.connect(state.db_path) as db:
            last_connect = await dbmod.last_event(db, "imap_connect")
            last_email = await dbmod.last_event(db, "email_processed")
            last_crash = await dbmod.last_event(db, "crash")

        lines = [
            t("status_title", state.lang),
            t("status_uptime", state.lang, uptime=state.uptime_str()),
            t("status_paused", state.lang,
              state=t("state_paused" if state.paused else "state_active", state.lang)),
            t("status_last_connect", state.lang,
              when=_iso_ago(last_connect[0] if last_connect else None, state.lang)),
            t("status_last_email", state.lang,
              when=_iso_ago(last_email[0] if last_email else None, state.lang)),
        ]
        if last_crash:
            since = datetime.fromisoformat(last_crash[0])
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - since < timedelta(days=1):
                lines.append(t("status_last_crash", state.lang,
                               when=_iso_ago(last_crash[0], state.lang),
                               detail=last_crash[1][:120]))
        await msg.answer("\n".join(lines))

    @router.message(Command("stats"))
    async def cmd_stats(msg: Message) -> None:
        now = datetime.now(timezone.utc)
        day_ago = (now - timedelta(days=1)).isoformat(timespec="seconds")
        week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
        async with aiosqlite.connect(state.db_path) as db:
            total = await dbmod.count_total(db)
            today = await dbmod.count_since(db, day_ago)
            week = await dbmod.count_since(db, week_ago)
            cities = await dbmod.top_cities(db, limit=8)
        lines = [
            t("stats_title", state.lang),
            t("stats_total", state.lang, n=total),
            t("stats_today", state.lang, n=today),
            t("stats_week", state.lang, n=week),
        ]
        if cities:
            lines.append("")
            lines.append(t("stats_by_city", state.lang))
            for city, n in cities:
                lines.append(f"  · {city}: {n}")
        await msg.answer("\n".join(lines))

    @router.message(Command("recent"))
    async def cmd_recent(msg: Message) -> None:
        parts = (msg.text or "").split()
        n = 5
        if len(parts) > 1 and parts[1].isdigit():
            n = max(1, min(20, int(parts[1])))
        async with aiosqlite.connect(state.db_path) as db:
            items = await dbmod.recent_listings(db, limit=n)
        if not items:
            await msg.answer(t("recent_empty", state.lang))
            return
        await msg.answer(t("recent_title", state.lang, n=len(items)))
        for l in items:
            await msg.answer(format_listing(l, state.lang),
                             disable_web_page_preview=False)

    @router.message(Command("mem"))
    async def cmd_mem(msg: Message) -> None:
        vm = psutil.virtual_memory()
        await msg.answer(t("mem_body", state.lang,
                           total=_fmt_bytes(vm.total),
                           used=_fmt_bytes(vm.used),
                           free=_fmt_bytes(vm.available),
                           pct=f"{vm.percent:.1f}"))

    @router.message(Command("cpu"))
    async def cmd_cpu(msg: Message) -> None:
        pct = psutil.cpu_percent(interval=0.5)
        try:
            la1, la5, la15 = os.getloadavg()
        except (AttributeError, OSError):
            la1 = la5 = la15 = 0.0
        await msg.answer(t("cpu_body", state.lang,
                           pct=f"{pct:.1f}",
                           la1=f"{la1:.2f}", la5=f"{la5:.2f}", la15=f"{la15:.2f}",
                           cores=psutil.cpu_count(logical=True) or 1))

    @router.message(Command("pause"))
    async def cmd_pause(msg: Message) -> None:
        if state.paused:
            await msg.answer(t("already_paused", state.lang))
            return
        await state.set_paused(True)
        await msg.answer(t("paused_now", state.lang))

    @router.message(Command("resume"))
    async def cmd_resume(msg: Message) -> None:
        if not state.paused:
            await msg.answer(t("already_active", state.lang))
            return
        await state.set_paused(False)
        await msg.answer(t("resumed_now", state.lang))

    @router.message(Command("lang"))
    async def cmd_lang(msg: Message) -> None:
        new_lang = await state.toggle_lang()
        await msg.answer(t("lang_switched", new_lang))

    @router.message(Command("version"))
    async def cmd_version(msg: Message) -> None:
        started = datetime.fromtimestamp(state.started_at, tz=timezone.utc)
        await msg.answer(t("version_body", state.lang,
                           sha=state.git_sha[:12],
                           branch=state.git_branch,
                           started=started.strftime("%Y-%m-%d %H:%M UTC")))

    @router.message(F.text.startswith("/"))
    async def cmd_unknown(msg: Message) -> None:
        await msg.answer(t("unknown_cmd", state.lang))

    dp.include_router(router)
    return dp


async def run_bot(bot: Bot, dispatcher: Dispatcher) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot, handle_signals=False)
