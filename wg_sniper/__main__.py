from __future__ import annotations

import asyncio
import html
import logging
import traceback
from email.message import Message

import aiosqlite
import httpx

from . import db as dbmod
from .commands import build_dispatcher, run_bot
from .config import load_config
from .i18n import t
from .imap_listener import run_listener
from .notifier import make_bot, notify_plain, send_and_enrich, Sender
from .parser import is_relevant_sender, parse_email
from .state import State
from .version import git_info

log = logging.getLogger("wg_sniper")


async def _amain() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await dbmod.init_db(cfg.db_path)

    state = State(db_path=cfg.db_path)
    state.git_sha, state.git_branch = git_info()
    await state.load()

    bot = make_bot(cfg.telegram_bot_token)
    sender = Sender(bot, cfg.telegram_chat_id)
    dispatcher = build_dispatcher(state, cfg.telegram_chat_id)

    async with aiosqlite.connect(cfg.db_path) as db:
        await dbmod.log_event(db, "startup", state.git_sha[:12])

    await notify_plain(sender, t("startup_notice", state.lang, sha=state.git_sha[:7]))

    http_client = httpx.AsyncClient(http2=True, timeout=15)

    async def persist_enrichment(listing) -> None:
        async with aiosqlite.connect(cfg.db_path) as db:
            await dbmod.mark_enriched(db, listing)

    async def _resend_pending() -> None:
        async with aiosqlite.connect(cfg.db_path) as db:
            pending = await dbmod.pending_notifications(db)
        if not pending:
            return
        log.info("re-sending %d pending listing(s) from previous run", len(pending))
        for listing in pending:
            if state.paused:
                break
            message_id = await send_and_enrich(
                sender, http_client, listing, state.lang,
                on_enriched=persist_enrichment,
            )
            async with aiosqlite.connect(cfg.db_path) as db:
                await dbmod.mark_notified(db, listing.ad_id, message_id)

    asyncio.create_task(_resend_pending())

    async def on_email(msg: Message) -> None:
        from_hdr = msg.get("From", "")
        if not is_relevant_sender(from_hdr, cfg.wg_sender_filter):
            return

        listings = parse_email(msg)
        if not listings:
            log.info("no listings extracted from message: %s", msg.get("Subject", ""))
            return

        async with aiosqlite.connect(cfg.db_path) as db:
            await dbmod.log_event(db, "email_processed",
                                  f"{len(listings)} listing(s)")
            new_listings = []
            for listing in listings:
                if await dbmod.try_insert(db, listing):
                    new_listings.append(listing)

        for listing in new_listings:
            log.info("new listing %s: %s", listing.ad_id, listing.title)
            if state.paused:
                log.info("skip send (paused): %s", listing.ad_id)
                continue
            message_id = await send_and_enrich(
                sender, http_client, listing, state.lang,
                on_enriched=persist_enrichment,
            )
            if message_id is None:
                log.warning("send failed for ad_id=%s — will retry on next startup",
                            listing.ad_id)
                continue
            async with aiosqlite.connect(cfg.db_path) as db:
                await dbmod.mark_notified(db, listing.ad_id, message_id)

    async def imap_task() -> None:
        async with aiosqlite.connect(cfg.db_path) as db:
            await dbmod.log_event(db, "imap_connect", "start")
        await run_listener(
            host=cfg.imap_host,
            port=cfg.imap_port,
            user=cfg.imap_user,
            password=cfg.imap_password,
            folder=cfg.imap_folder,
            on_email=on_email,
            sender_filter=cfg.wg_sender_filter,
        )

    try:
        await asyncio.gather(imap_task(), run_bot(bot, dispatcher))
    except Exception as exc:
        err_summary = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        log.exception("fatal error, notifying and exiting")
        try:
            async with aiosqlite.connect(cfg.db_path) as db:
                await dbmod.log_event(db, "crash", err_summary[:500])
            await notify_plain(
                sender,
                t("crash_notice", state.lang, err=html.escape(err_summary[:200])),
            )
        except Exception:
            log.exception("failed to send crash notice")
        raise
    finally:
        await http_client.aclose()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
