from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    ad_id           TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT,
    city            TEXT,
    district        TEXT,
    price_eur       INTEGER,
    size_m2         INTEGER,
    available_from  TEXT,
    first_seen_at   TEXT NOT NULL,
    notified_at     TEXT,
    raw_snippet     TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_listings_city       ON listings(city);
"""


async def init_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.executescript(SCHEMA)
        await db.commit()


async def try_insert(db: aiosqlite.Connection, listing: Listing) -> bool:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cursor = await db.execute(
        """
        INSERT OR IGNORE INTO listings
            (ad_id, source, url, title, city, district, price_eur, size_m2,
             available_from, first_seen_at, raw_snippet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing.ad_id,
            listing.source,
            listing.url,
            listing.title,
            listing.city,
            listing.district,
            listing.price_eur,
            listing.size_m2,
            listing.available_from,
            now,
            listing.raw_snippet,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0


async def mark_notified(db: aiosqlite.Connection, ad_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    await db.execute(
        "UPDATE listings SET notified_at = ? WHERE ad_id = ?",
        (now, ad_id),
    )
    await db.commit()
