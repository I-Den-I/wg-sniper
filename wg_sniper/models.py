from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Listing:
    ad_id: str
    source: str
    url: str
    title: str | None = None
    city: str | None = None
    district: str | None = None
    price_eur: int | None = None
    size_m2: int | None = None
    available_from: str | None = None
    raw_snippet: str | None = None
