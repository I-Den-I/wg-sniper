"""Kleinanzeigen source: saved-search alert emails and ad pages."""
from __future__ import annotations

import logging
import re
from email.message import Message

from bs4 import BeautifulSoup, Tag

from .enricher import _norm_ws, _valid_price, _valid_size
from .models import Enrichment, Listing
from .parser import _decode_subject, extract_html

log = logging.getLogger(__name__)

SOURCE = "kleinanzeigen"
ID_PREFIX = "ka:"

AD_URL_RE = re.compile(
    r"https?://(?:www\.)?kleinanzeigen\.de/s-anzeige/(?:[^/?#\s]+/)?(?P<ad_id>\d{6,12})(?:-[\d-]+)?(?=[?#/]|$)",
    re.IGNORECASE,
)
SUBJECT_CITY_RE = re.compile(r"\bin\s+(?P<city>[^„“\"()]+?)\s*(?:\(\+\d+\s*km\))?\s*[“\"]?\s*$")
NUMBER_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
ALT_PREFIX = "Bild zur Anzeige"


def _number(text: str | None) -> int | None:
    """German-formatted number: '1.000 €' -> 1000, '63,38 m²' -> 63."""
    if not text:
        return None
    m = NUMBER_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(".", ""))


def ad_url(raw_id: str) -> str:
    return f"https://www.kleinanzeigen.de/s-anzeige/{raw_id}"


def city_from_subject(subject: str) -> str | None:
    m = SUBJECT_CITY_RE.search(subject.strip())
    return _norm_ws(m.group("city")) if m else None


def _block_title(block: Tag) -> str | None:
    img = block.find("img", alt=True)
    if img and img["alt"].startswith(ALT_PREFIX):
        title = _norm_ws(img["alt"][len(ALT_PREFIX):])
        if title:
            return title
    for td in block.find_all("td"):
        if td.find(["table", "img"]):
            continue
        if "font-weight:700" in (td.get("style") or "").replace(" ", ""):
            return _norm_ws(td.get_text(" ", strip=True))
    return None


def _block_price(block: Tag) -> int | None:
    for span in block.find_all("span"):
        text = span.get_text(" ", strip=True)
        if "€" in text:
            return _valid_price(_number(text))
    return None


def parse_email(msg: Message) -> list[Listing]:
    html = extract_html(msg)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    city = city_from_subject(_decode_subject(msg))

    listings: list[Listing] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = AD_URL_RE.search(a["href"])
        if not m:
            continue
        raw_id = m.group("ad_id")
        if raw_id in seen:
            continue
        seen.add(raw_id)

        block = a.find_previous("tr", class_="re_mobile_stack")
        title = _block_title(block) if block else None
        price = _block_price(block) if block else None
        if title is None:
            log.warning("kleinanzeigen: no title block for ad %s", raw_id)

        listings.append(Listing(
            ad_id=f"{ID_PREFIX}{raw_id}",
            source=SOURCE,
            url=ad_url(raw_id),
            title=title or "WG-Zimmer",
            city=city,
            price_eur=price,
        ))
    return listings


def _details(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for li in soup.select(".addetailslist--detail"):
        value_el = li.select_one(".addetailslist--detail--value")
        if not value_el:
            continue
        value = _norm_ws(value_el.get_text(" ", strip=True))
        label = _norm_ws("".join(t for t in li.find_all(string=True, recursive=False)))
        if label and value:
            out[label] = value
    return out


def parse_ad_page(html: str) -> Enrichment:
    soup = BeautifulSoup(html, "lxml")
    e = Enrichment()

    h1 = soup.select_one("#viewad-title")
    if h1:
        # "Reserviert • " / "Gelöscht • " live in hidden spans inside the h1
        title = "".join(t for t in h1.find_all(string=True, recursive=False))
        e.title = _norm_ws(title)

    price_el = soup.select_one("#viewad-price")
    if price_el:
        e.price_eur = _valid_price(_number(price_el.get_text(" ", strip=True)))

    loc_el = soup.select_one("#viewad-locality")
    locality = _norm_ws(loc_el.get_text(" ", strip=True)) if loc_el else None
    if locality:
        e.address = locality
        parts = locality.split(" - ", 1)
        if len(parts) == 2:
            e.district = _norm_ws(parts[1])

    det = _details(soup)
    rooms = _number(det.get("Zimmer"))
    if rooms in (None, 1):
        e.size_m2 = _valid_size(_number(det.get("Wohnfläche")))
    e.available_from = det.get("Verfügbar ab")
    mates = _number(det.get("Anzahl Mitbewohner"))
    if mates is not None and 1 <= mates <= 15:
        e.wg_size = f"{mates + 1}er WG"

    desc_el = soup.select_one("#viewad-description-text")
    if desc_el:
        text = _norm_ws(desc_el.get_text(" ", strip=True))
        if text:
            e.description_snippet = text[:280] + ("…" if len(text) > 280 else "")

    return e
