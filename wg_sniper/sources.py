"""Registry of listing sources: which sender each one mails from and how to parse it."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from typing import Callable

from . import kleinanzeigen, parser
from .enricher import parse_ad_page as wg_parse_ad_page
from .models import Enrichment, Listing


@dataclass(frozen=True, slots=True)
class Source:
    name: str
    label: str
    sender: str
    subject_hint: str
    parse_email: Callable[[Message], list[Listing]]
    parse_ad_page: Callable[[str], Enrichment]


SOURCES: tuple[Source, ...] = (
    Source("wg-gesucht", "WG-Gesucht", "wg-gesucht.de", "Suchauftrag",
           parser.parse_email, wg_parse_ad_page),
    Source(kleinanzeigen.SOURCE, "Kleinanzeigen", "kleinanzeigen.de", "Neue Treffer",
           kleinanzeigen.parse_email, kleinanzeigen.parse_ad_page),
)

SEARCHES: tuple[tuple[str, str], ...] = tuple((s.sender, s.subject_hint) for s in SOURCES)
_BY_NAME = {s.name: s for s in SOURCES}


def by_name(name: str) -> Source | None:
    return _BY_NAME.get(name)


def for_sender(from_header: str | None) -> Source | None:
    if not from_header:
        return None
    lowered = from_header.lower()
    for s in SOURCES:
        if s.sender in lowered:
            return s
    return None


def label_for(name: str) -> str:
    s = _BY_NAME.get(name)
    return s.label if s else name
