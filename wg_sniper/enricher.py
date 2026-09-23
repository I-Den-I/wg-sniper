from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .models import Enrichment

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

NUM_RE = re.compile(r"(\d{1,4}(?:[.,]\d{3})?(?:[.,]\d{1,2})?)")


def _to_int(text: str | None) -> int | None:
    if not text:
        return None
    m = NUM_RE.search(text.replace(" ", " "))
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except ValueError:
        return None


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned or None


def _find_label_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        for node in soup.find_all(string=re.compile(rf"\b{re.escape(label)}\b", re.I)):
            parent = node.parent
            if not parent:
                continue
            sibling = parent.find_next_sibling()
            if sibling:
                text = _clean(sibling.get_text(" ", strip=True))
                if text and text.lower() != label.lower():
                    return text
            after = parent.get_text(" ", strip=True)
            if after and label.lower() in after.lower():
                remainder = re.split(rf"\b{re.escape(label)}\b", after, flags=re.I, maxsplit=1)
                if len(remainder) == 2 and remainder[1].strip():
                    return _clean(remainder[1])
    return None


def parse_ad_page(html: str) -> Enrichment:
    soup = BeautifulSoup(html, "lxml")
    e = Enrichment()

    for sel in ("h2.headline-key-facts", "h2.headline-detailed-view-title",
                "h1.headline", "h2"):
        node = soup.select_one(sel)
        if node:
            _clean(node.get_text(" ", strip=True))
            break

    for label, key in (("Gesamtmiete", "price_eur"),
                       ("Miete", "price_eur"),
                       ("Kaltmiete", "price_eur"),
                       ("Warmmiete", "price_eur")):
        v = _find_label_value(soup, (label,))
        if v:
            n = _to_int(v)
            if n and (getattr(e, key) is None or key == "price_eur"):
                setattr(e, key, n)
                if key == "price_eur":
                    break

    size_txt = _find_label_value(soup, ("Zimmergröße", "Wohnfläche", "Größe"))
    if size_txt:
        e.size_m2 = _to_int(size_txt)

    dep_txt = _find_label_value(soup, ("Kaution",))
    if dep_txt:
        e.deposit_eur = _to_int(dep_txt)

    e.district = _clean(_find_label_value(soup, ("Stadtteil", "Ortsteil")))
    e.address = _clean(_find_label_value(soup, ("Adresse", "Straße")))
    e.available_from = _clean(_find_label_value(soup, ("Frei ab", "Verfügbar ab", "Einzugsdatum")))
    e.available_until = _clean(_find_label_value(soup, ("Frei bis", "Verfügbar bis")))
    e.wg_size = _clean(_find_label_value(soup, ("WG-Größe", "WG Größe", "Wohnungsgröße")))

    for sel in ("#ad_description_text", ".freitext", "#description_body",
                "div[itemprop='description']"):
        node = soup.select_one(sel)
        if node:
            text = _clean(node.get_text(" ", strip=True))
            if text:
                e.description_snippet = text[:280] + ("…" if len(text) > 280 else "")
                break

    if e.price_eur is None:
        body_text = soup.get_text(" ", strip=True)
        m = re.search(r"(\d{2,4})\s*€", body_text)
        if m:
            try:
                e.price_eur = int(m.group(1))
            except ValueError:
                pass

    if e.size_m2 is None:
        body_text = body_text if "body_text" in dir() else soup.get_text(" ", strip=True)
        m = re.search(r"(\d{1,3})\s*m²", body_text)
        if m:
            try:
                e.size_m2 = int(m.group(1))
            except ValueError:
                pass

    return e


async def fetch_ad(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, headers=DEFAULT_HEADERS, timeout=15,
                                follow_redirects=True)
    except httpx.HTTPError as exc:
        log.warning("enrich fetch failed for %s: %s", url, exc)
        return None
    if resp.status_code != 200:
        log.warning("enrich fetch got HTTP %s for %s", resp.status_code, url)
        if os.environ.get("WG_ENRICH_DUMP") == "1":
            _dump(url, resp.status_code, resp.text)
        return None
    return resp.text


async def enrich(client: httpx.AsyncClient, ad_id: str, url: str) -> Enrichment | None:
    html = await fetch_ad(client, url)
    if not html:
        return None
    try:
        result = parse_ad_page(html)
    except Exception:
        log.exception("enrich parse failed for ad_id=%s", ad_id)
        return None
    if os.environ.get("WG_ENRICH_DUMP") == "1" and result.price_eur is None:
        _dump(url, 200, html)
    return result


def _dump(url: str, status: int, body: str) -> None:
    debug_dir = Path(os.environ.get("WG_DEBUG_DIR", "./debug"))
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    stem = debug_dir / f"enrich_{ts}_{status}"
    stem.with_suffix(".html").write_text(body, encoding="utf-8")
    stem.with_suffix(".url.txt").write_text(url, encoding="utf-8")
