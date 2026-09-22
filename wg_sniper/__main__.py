from __future__ import annotations

import asyncio
import logging
from email.message import Message

import aiosqlite

from .config import load_config
from .db import init_db, mark_notified, try_insert
from .imap_listener import run_listener
from .notifier import make_bot, send_listing
from .parser import is_relevant_sender, parse_email

log = logging.getLogger("wg_sniper")


async def _amain() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await init_db(cfg.db_path)
    bot = make_bot(cfg.telegram_bot_token)

    async def on_email(msg: Message) -> None:
        from_hdr = msg.get("From", "")
        if not is_relevant_sender(from_hdr, cfg.wg_sender_filter):
            return

        listings = parse_email(msg)
        if not listings:
            log.info("no listings extracted from message: %s", msg.get("Subject", ""))
            return

        async with aiosqlite.connect(cfg.db_path) as db:
            for listing in listings:
                is_new = await try_insert(db, listing)
                if not is_new:
                    continue
                log.info("new listing %s: %s (%s €)",
                         listing.ad_id, listing.title, listing.price_eur)
                await send_listing(bot, cfg.telegram_chat_id, listing)
                await mark_notified(db, listing.ad_id)

    try:
        await run_listener(
            host=cfg.imap_host,
            port=cfg.imap_port,
            user=cfg.imap_user,
            password=cfg.imap_password,
            folder=cfg.imap_folder,
            on_email=on_email,
            sender_filter=cfg.wg_sender_filter,
        )
    finally:
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
