"""One-off backfill: re-fetch every previously-notified ad page with the
current (fixed) enricher and edit the already-sent Telegram message in place.

Usage:
    python -m wg_sniper.reenrich [--dry-run]

Safe to re-run: each listing is re-fetched and re-applied independently,
Telegram edit_message_text is idempotent for identical content.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import aiosqlite
import httpx

from . import db as dbmod
from .config import load_config
from .enricher import enrich
from .notifier import Sender, format_listing, make_bot
from .state import State

log = logging.getLogger("wg_sniper.reenrich")

DELAY_BETWEEN_FETCHES_SEC = 2.0


async def _amain(dry_run: bool) -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await dbmod.init_db(cfg.db_path)

    state = State(db_path=cfg.db_path)
    await state.load()

    bot = make_bot(cfg.telegram_bot_token)
    sender = Sender(bot, cfg.telegram_chat_id)
    http_client = httpx.AsyncClient(http2=True, timeout=15)

    async with aiosqlite.connect(cfg.db_path) as db:
        items = await dbmod.listings_with_message_id(db)

    log.info("found %d previously-notified listing(s) to re-enrich%s",
             len(items), " (dry-run, no writes)" if dry_run else "")

    updated = skipped = failed = 0
    try:
        for i, (listing, tg_message_id) in enumerate(items):
            if i > 0:
                await asyncio.sleep(DELAY_BETWEEN_FETCHES_SEC)

            enrichment = await enrich(http_client, listing.ad_id, listing.url)
            if enrichment is None:
                log.warning("skip ad_id=%s: fetch/parse failed", listing.ad_id)
                failed += 1
                continue

            before_price = listing.price_eur
            enrichment.apply_to(listing)

            if dry_run:
                log.info("[dry-run] ad_id=%s: price %s -> %s, title=%r",
                         listing.ad_id, before_price, listing.price_eur, listing.title)
                updated += 1
                continue

            async with aiosqlite.connect(cfg.db_path) as db:
                await dbmod.mark_enriched(db, listing)

            text = format_listing(listing, state.lang)
            ok = await sender.edit(tg_message_id, text)
            if ok:
                log.info("updated ad_id=%s (msg %s): price %s -> %s",
                         listing.ad_id, tg_message_id, before_price, listing.price_eur)
                updated += 1
            else:
                log.warning("DB updated but Telegram edit failed for ad_id=%s "
                            "(msg %s) — message may have been deleted",
                            listing.ad_id, tg_message_id)
                skipped += 1
    finally:
        await http_client.aclose()
        await bot.session.close()

    log.info("done: %d updated, %d edit-skipped, %d failed (of %d total)",
             updated, skipped, failed, len(items))


def main() -> None:
    dry_run = "--dry-run" in sys.argv[1:]
    asyncio.run(_amain(dry_run))


if __name__ == "__main__":
    main()
