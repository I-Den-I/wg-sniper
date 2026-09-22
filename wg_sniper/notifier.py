from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .models import Listing

log = logging.getLogger(__name__)


def make_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def format_listing(listing: Listing) -> str:
    title = html.escape(listing.title or "WG-Zimmer")
    lines = [f"<b>🏠 {title}</b>"]

    meta = []
    if listing.city:
        meta.append(html.escape(listing.city))
    if listing.district:
        meta.append(html.escape(listing.district))
    if meta:
        lines.append("📍 " + " · ".join(meta))

    stats = []
    if listing.price_eur is not None:
        stats.append(f"💶 <b>{listing.price_eur} €</b>")
    if listing.size_m2 is not None:
        stats.append(f"📐 {listing.size_m2} m²")
    if listing.available_from:
        stats.append(f"📅 {html.escape(listing.available_from)}")
    if stats:
        lines.append(" · ".join(stats))

    lines.append(f'\n<a href="{html.escape(listing.url)}">Оголошення →</a>')
    return "\n".join(lines)


async def send_listing(bot: Bot, chat_id: int, listing: Listing) -> None:
    text = format_listing(listing)
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=False)
    except Exception:
        log.exception("failed to send tg message for ad_id=%s", listing.ad_id)
