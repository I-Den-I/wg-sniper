from __future__ import annotations

import asyncio
import html
import logging
import time

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter

from .enricher import enrich
from .i18n import Lang, t
from .models import Listing

log = logging.getLogger(__name__)

_SEND_GAP_SEC = 1.1


def make_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


LABELS: dict[str, dict[Lang, str]] = {
    "price":   {"uk": "Ціна",    "en": "Price"},
    "size":    {"uk": "Площа",   "en": "Size"},
    "district":{"uk": "Район",   "en": "District"},
    "address": {"uk": "Адреса",  "en": "Address"},
    "from":    {"uk": "Заїзд",   "en": "From"},
    "until":   {"uk": "До",      "en": "Until"},
    "wg_size": {"uk": "Тип WG",  "en": "WG type"},
    "deposit": {"uk": "Застава", "en": "Deposit"},
    "open":    {"uk": "Оголошення →", "en": "Listing →"},
}


def _lbl(key: str, lang: Lang) -> str:
    return LABELS[key].get(lang, LABELS[key]["en"])


def format_listing(listing: Listing, lang: Lang) -> str:
    title = html.escape(listing.title or "WG-Zimmer")
    lines = [f"<b>🏠 {title}</b>"]

    where = []
    if listing.city:
        where.append(html.escape(listing.city))
    if listing.district:
        where.append(html.escape(listing.district))
    if where:
        lines.append("📍 " + " · ".join(where))
    if listing.address:
        lines.append("🏘 " + html.escape(listing.address))

    stats = []
    if listing.price_eur is not None:
        stats.append(f"💶 <b>{listing.price_eur} €</b>")
    if listing.size_m2 is not None:
        stats.append(f"📐 {listing.size_m2} m²")
    if listing.wg_size:
        stats.append(f"👥 {html.escape(listing.wg_size)}")
    if stats:
        lines.append(" · ".join(stats))

    when = []
    if listing.available_from:
        when.append(f"{_lbl('from', lang)}: {html.escape(listing.available_from)}")
    if listing.available_until:
        when.append(f"{_lbl('until', lang)}: {html.escape(listing.available_until)}")
    if when:
        lines.append("📅 " + " · ".join(when))

    if listing.deposit_eur is not None:
        lines.append(f"🔐 {_lbl('deposit', lang)}: {listing.deposit_eur} €")

    if listing.description_snippet:
        lines.append("")
        lines.append(f"<i>{html.escape(listing.description_snippet)}</i>")

    lines.append(f'\n<a href="{html.escape(listing.url)}">{_lbl("open", lang)}</a>')
    return "\n".join(lines)


class Sender:
    def __init__(self, bot: Bot, chat_id: int):
        self._bot = bot
        self._chat_id = chat_id
        self._lock = asyncio.Lock()
        self._last_sent = 0.0

    async def _throttle(self) -> None:
        now = time.monotonic()
        wait = _SEND_GAP_SEC - (now - self._last_sent)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_sent = time.monotonic()

    async def send(self, text: str) -> int | None:
        async with self._lock:
            await self._throttle()
            for attempt in range(3):
                try:
                    msg = await self._bot.send_message(
                        self._chat_id, text, disable_web_page_preview=False,
                    )
                    return msg.message_id
                except TelegramRetryAfter as e:
                    log.warning("tg retry_after=%s (attempt %d)", e.retry_after, attempt)
                    await asyncio.sleep(e.retry_after + 0.5)
                except Exception:
                    log.exception("send_message failed (attempt %d)", attempt)
                    await asyncio.sleep(2)
            return None

    async def edit(self, message_id: int, text: str) -> bool:
        async with self._lock:
            await self._throttle()
            for attempt in range(3):
                try:
                    await self._bot.edit_message_text(
                        text=text, chat_id=self._chat_id, message_id=message_id,
                        disable_web_page_preview=False,
                    )
                    return True
                except TelegramRetryAfter as e:
                    log.warning("tg edit retry_after=%s", e.retry_after)
                    await asyncio.sleep(e.retry_after + 0.5)
                except Exception:
                    log.exception("edit_message_text failed (attempt %d)", attempt)
                    await asyncio.sleep(2)
            return False


async def send_and_enrich(
    sender: Sender,
    http_client: httpx.AsyncClient,
    listing: Listing,
    lang: Lang,
    on_enriched=None,
) -> int | None:
    text = format_listing(listing, lang)
    message_id = await sender.send(text)
    if message_id is None:
        return None

    enrichment = await enrich(http_client, listing.ad_id, listing.url)
    if enrichment is None:
        return message_id

    enrichment.apply_to(listing)
    if on_enriched is not None:
        try:
            await on_enriched(listing)
        except Exception:
            log.exception("on_enriched callback failed")

    updated = format_listing(listing, lang)
    if updated != text:
        await sender.edit(message_id, updated)
    return message_id


async def notify_plain(sender: Sender, text: str) -> None:
    await sender.send(text)
