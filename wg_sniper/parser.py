from __future__ import annotations

import logging
import os
import re
import time
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from .models import Listing

log = logging.getLogger(__name__)

AD_URL_RE = re.compile(
    r"https?://(?:www\.)?wg-gesucht\.de/(?:(?P<slug>[a-zA-Z][\w\-]*)\.)?(?P<ad_id>\d{6,10})\.html",
    re.IGNORECASE,
)
SUBJECT_CITY_RE = re.compile(r'["„”]([^"„”\n\r]{2,60})["„”]')
QUOTE_CHAR_RE = re.compile(r'["„”]')


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def extract_html(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return _decode_part(part)
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return _decode_part(part)
        return ""
    return _decode_part(msg)


def _slug_to_title(slug: str | None) -> str:
    if not slug:
        return "WG-Zimmer"
    words = slug.replace("-", " ").split()
    return " ".join(w.capitalize() for w in words) or "WG-Zimmer"


def _city_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    m = re.search(r"in-([A-Za-zÄÖÜäöüß\-]+)", slug)
    if not m:
        return None
    parts = m.group(1).split("-")
    return parts[0] if parts else None


def _decode_subject(msg: Message) -> str:
    raw = msg.get("Subject", "")
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _city_from_subject(subject: str) -> str | None:
    m = SUBJECT_CITY_RE.search(subject)
    return m.group(1).strip() if m else None


def _unwrap_tracking(href: str) -> str:
    try:
        parsed = urlparse(href)
    except ValueError:
        return href
    qs = parse_qs(parsed.query)
    for key in ("url", "redirect", "u", "link", "target", "goto"):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])
            if "wg-gesucht.de" in candidate:
                return candidate
    return href


def _extract_ad_titles(body_text: str, subject_city: str | None) -> list[str]:
    positions = [m.start() for m in QUOTE_CHAR_RE.finditer(body_text)]
    subject_norm = (subject_city or "").strip().lower()
    result: list[str] = []
    for i in range(0, len(positions) - 1, 2):
        start, end = positions[i], positions[i + 1]
        title = body_text[start + 1:end].strip()
        if len(title) < 15:
            continue
        if title.lower() == subject_norm:
            continue
        result.append(title)
    return result


def parse_email(msg: Message) -> list[Listing]:
    html = extract_html(msg)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    subject = _decode_subject(msg)
    subject_city = _city_from_subject(subject)

    body_text = soup.get_text(" ", strip=True)
    titles_in_order = _extract_ad_titles(body_text, subject_city)

    ordered_ads: list[tuple[str, str | None]] = []
    seen_ids: set[str] = set()
    all_hrefs: list[str] = []
    for a in soup.find_all("a", href=True):
        raw_href = a["href"]
        all_hrefs.append(raw_href)
        href = _unwrap_tracking(raw_href)
        m = AD_URL_RE.search(href)
        if not m:
            continue
        ad_id = m.group("ad_id")
        if ad_id in seen_ids:
            continue
        seen_ids.add(ad_id)
        ordered_ads.append((ad_id, m.group("slug")))

    if ordered_ads and len(titles_in_order) != len(ordered_ads):
        log.warning(
            "parser mismatch: %d ad_id(s) vs %d title(s) in email %r — "
            "pairing may be off. Set WG_DEBUG_DUMP=1 to save the raw HTML.",
            len(ordered_ads), len(titles_in_order), subject[:120],
        )
        if os.environ.get("WG_DEBUG_DUMP") == "1":
            _dump_debug(msg, html, all_hrefs)

    listings: list[Listing] = []
    for i, (ad_id, slug) in enumerate(ordered_ads):
        url = (
            f"https://www.wg-gesucht.de/{slug}.{ad_id}.html"
            if slug
            else f"https://www.wg-gesucht.de/{ad_id}.html"
        )
        title = titles_in_order[i] if i < len(titles_in_order) else _slug_to_title(slug)
        listings.append(Listing(
            ad_id=ad_id,
            source="wg-gesucht",
            url=url,
            title=title,
            city=_city_from_slug(slug) or subject_city,
        ))

    if not listings and os.environ.get("WG_DEBUG_DUMP") == "1":
        _dump_debug(msg, html, all_hrefs)

    return listings


def _dump_debug(msg: Message, html: str, hrefs: list[str]) -> None:
    debug_dir = Path(os.environ.get("WG_DEBUG_DIR", "./debug"))
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    stem = debug_dir / f"unparsed_{ts}"
    stem.with_suffix(".html").write_text(html, encoding="utf-8")
    stem.with_suffix(".hrefs.txt").write_text("\n".join(hrefs), encoding="utf-8")
    wg_hrefs = [h for h in hrefs if "wg-gesucht" in h.lower()]
    log.warning(
        "no listings extracted; dumped html to %s. subject=%r; wg-gesucht hrefs sample: %s",
        stem.with_suffix(".html"),
        msg.get("Subject", ""),
        wg_hrefs[:3],
    )


def is_relevant_sender(from_header: str | None, sender_filter: str) -> bool:
    if not from_header:
        return False
    return sender_filter.lower() in from_header.lower()
