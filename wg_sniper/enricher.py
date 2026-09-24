from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

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

INT_RE = re.compile(r"(\d[\d.,]*)")
WG_SIZE_RE = re.compile(r"\b(\d+)er[  -]*WG\b", re.IGNORECASE)
ZIP_CITY_RE = re.compile(r"\b\d{5}\s+([\w\-äöüÄÖÜß]+)(?:\s+(.+))?", re.UNICODE)

PRICE_MIN, PRICE_MAX = 50, 5000
SIZE_MIN, SIZE_MAX = 3, 300
DEPOSIT_MAX = 25000


def _norm_ws(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned or None


def _to_int(text: str | None) -> int | None:
    if not text:
        return None
    m = INT_RE.search(text.replace(" ", " "))
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except ValueError:
        return None


def _valid_price(n: int | None) -> int | None:
    return n if n is not None and PRICE_MIN <= n <= PRICE_MAX else None


def _valid_size(n: int | None) -> int | None:
    return n if n is not None and SIZE_MIN <= n <= SIZE_MAX else None


def _valid_deposit(n: int | None) -> int | None:
    return n if n is not None and 0 <= n <= DEPOSIT_MAX else None


def _key_facts(soup: BeautifulSoup) -> dict[str, str]:
    facts: dict[str, str] = {}
    for label_el in soup.select(".key_fact_detail"):
        col = label_el.find_parent(class_="col-xs-6")
        if not col:
            continue
        value_el = col.select_one(".key_fact_value")
        if not value_el:
            continue
        label = _norm_ws(label_el.get_text(" ", strip=True))
        value = _norm_ws(value_el.get_text(" ", strip=True))
        if label and value:
            facts[label] = value
    return facts


def _section_pairs(soup: BeautifulSoup) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for label_el in soup.select(".section_panel_detail"):
        row = label_el.find_parent(class_="row")
        if not row:
            continue
        value_el = row.select_one(".section_panel_value")
        if not value_el:
            continue
        raw_label = label_el.get_text(" ", strip=True)
        label = _norm_ws(raw_label.rstrip(":"))
        value = _norm_ws(value_el.get_text(" ", strip=True))
        if not label or not value or value.lower() == "n.a.":
            continue
        pairs[label] = value
    return pairs


def _address_block(soup: BeautifulSoup) -> str | None:
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        if h.get_text(strip=True) == "Adresse":
            parent = h.find_parent(class_="col-xs-12") or h.parent
            if not parent:
                return None
            detail = parent.select_one(".section_panel_detail")
            if not detail:
                return None
            return _norm_ws(detail.get_text(" ", strip=True))
    return None


def _district_from_address(address: str | None) -> str | None:
    if not address:
        return None
    m = ZIP_CITY_RE.search(address)
    if not m:
        return None
    district = m.group(2)
    return _norm_ws(district)


def _wg_details_text(soup: BeautifulSoup) -> str:
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        if "WG-Details" in h.get_text(strip=True):
            row = h.find_parent(class_="row") or h.parent
            if isinstance(row, Tag):
                return row.get_text(" ", strip=True)
    return ""


def _description(soup: BeautifulSoup) -> str | None:
    candidates = []
    for el in soup.select("#ad_description_text, .freitext, .section_panel_content"):
        text = _norm_ws(el.get_text(" ", strip=True))
        if not text:
            continue
        if "googletag" in text.lower() or len(text) < 40:
            continue
        candidates.append(text)
    if not candidates:
        return None
    best = max(candidates, key=len)
    return best[:280] + ("…" if len(best) > 280 else "")


def _title(soup: BeautifulSoup) -> str | None:
    h1 = soup.select_one("h1")
    if h1:
        return _norm_ws(h1.get_text(" ", strip=True))
    return None


def parse_ad_page(html: str) -> Enrichment:
    soup = BeautifulSoup(html, "lxml")
    e = Enrichment()

    kf = _key_facts(soup)
    sp = _section_pairs(soup)

    e.price_eur = _valid_price(_to_int(kf.get("Gesamtmiete")))
    if e.price_eur is None:
        miete = _to_int(sp.get("Miete"))
        neben = _to_int(sp.get("Nebenkosten"))
        if miete is not None:
            total = miete + (neben or 0)
            e.price_eur = _valid_price(total)

    e.rent_eur = _valid_price(_to_int(sp.get("Miete")))
    e.utilities_eur = _valid_price(_to_int(sp.get("Nebenkosten")))
    e.deposit_eur = _valid_deposit(_to_int(sp.get("Kaution")))

    e.size_m2 = _valid_size(_to_int(kf.get("Zimmergröße")))

    e.available_from = _norm_ws(sp.get("frei ab"))
    e.available_until = _norm_ws(sp.get("frei bis"))

    e.address = _address_block(soup)
    e.district = _district_from_address(e.address)

    wg_text = _wg_details_text(soup)
    if wg_text:
        m = WG_SIZE_RE.search(wg_text)
        if m:
            e.wg_size = f"{m.group(1)}er WG"

    e.title = _title(soup)
    e.description_snippet = _description(soup)

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
