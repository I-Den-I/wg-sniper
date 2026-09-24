from __future__ import annotations

from dataclasses import dataclass, field


_ENRICHABLE_FIELDS = (
    "title", "price_eur", "rent_eur", "utilities_eur", "deposit_eur",
    "size_m2", "district", "address", "available_from", "available_until",
    "wg_size", "description_snippet",
)


@dataclass(slots=True)
class Listing:
    ad_id: str
    source: str
    url: str
    title: str | None = None
    city: str | None = None
    district: str | None = None
    address: str | None = None
    price_eur: int | None = None
    rent_eur: int | None = None
    utilities_eur: int | None = None
    size_m2: int | None = None
    available_from: str | None = None
    available_until: str | None = None
    wg_size: str | None = None
    deposit_eur: int | None = None
    description_snippet: str | None = None
    raw_snippet: str | None = None


@dataclass(slots=True)
class Enrichment:
    title: str | None = None
    price_eur: int | None = None
    rent_eur: int | None = None
    utilities_eur: int | None = None
    deposit_eur: int | None = None
    size_m2: int | None = None
    district: str | None = None
    address: str | None = None
    available_from: str | None = None
    available_until: str | None = None
    wg_size: str | None = None
    description_snippet: str | None = None

    def apply_to(self, listing: Listing) -> Listing:
        for f in _ENRICHABLE_FIELDS:
            v = getattr(self, f)
            if v is not None:
                setattr(listing, f, v)
        return listing
