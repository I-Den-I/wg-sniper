from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    ad_id               TEXT PRIMARY KEY,
    source              TEXT NOT NULL,
    url                 TEXT NOT NULL,
    title               TEXT,
    city                TEXT,
    district            TEXT,
    address             TEXT,
    price_eur           INTEGER,
    size_m2             INTEGER,
    available_from      TEXT,
    available_until     TEXT,
    wg_size             TEXT,
    deposit_eur         INTEGER,
    description_snippet TEXT,
    first_seen_at       TEXT NOT NULL,
    notified_at         TEXT,
    tg_message_id       INTEGER,
    enriched_at         TEXT,
    raw_snippet         TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_listings_city       ON listings(city);

CREATE TABLE IF NOT EXISTS prefs (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    detail     TEXT,
    created_at TEXT NOT NULL
);
"""

MIGRATIONS = [
    "ALTER TABLE listings ADD COLUMN address TEXT",
    "ALTER TABLE listings ADD COLUMN available_until TEXT",
    "ALTER TABLE listings ADD COLUMN wg_size TEXT",
    "ALTER TABLE listings ADD COLUMN deposit_eur INTEGER",
    "ALTER TABLE listings ADD COLUMN description_snippet TEXT",
    "ALTER TABLE listings ADD COLUMN tg_message_id INTEGER",
    "ALTER TABLE listings ADD COLUMN enriched_at TEXT",
]


async def init_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.executescript(SCHEMA)
        for stmt in MIGRATIONS:
            try:
                await db.execute(stmt)
            except aiosqlite.OperationalError:
                pass
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def try_insert(db: aiosqlite.Connection, listing: Listing) -> bool:
    cursor = await db.execute(
        """
        INSERT OR IGNORE INTO listings
            (ad_id, source, url, title, city, district, address, price_eur,
             size_m2, available_from, available_until, wg_size, deposit_eur,
             description_snippet, first_seen_at, raw_snippet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing.ad_id, listing.source, listing.url, listing.title,
            listing.city, listing.district, listing.address, listing.price_eur,
            listing.size_m2, listing.available_from, listing.available_until,
            listing.wg_size, listing.deposit_eur, listing.description_snippet,
            _now(), listing.raw_snippet,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0


async def mark_notified(db: aiosqlite.Connection, ad_id: str,
                        tg_message_id: int | None = None) -> None:
    await db.execute(
        "UPDATE listings SET notified_at = ?, tg_message_id = ? WHERE ad_id = ?",
        (_now(), tg_message_id, ad_id),
    )
    await db.commit()


async def mark_enriched(db: aiosqlite.Connection, listing: Listing) -> None:
    await db.execute(
        """
        UPDATE listings
        SET price_eur = ?, size_m2 = ?, district = ?, address = ?,
            available_from = ?, available_until = ?, wg_size = ?,
            deposit_eur = ?, description_snippet = ?, enriched_at = ?
        WHERE ad_id = ?
        """,
        (
            listing.price_eur, listing.size_m2, listing.district,
            listing.address, listing.available_from, listing.available_until,
            listing.wg_size, listing.deposit_eur, listing.description_snippet,
            _now(), listing.ad_id,
        ),
    )
    await db.commit()


async def get_pref(db: aiosqlite.Connection, key: str, default: str) -> str:
    async with db.execute("SELECT value FROM prefs WHERE key = ?", (key,)) as cur:
        row = await cur.fetchone()
    return row[0] if row else default


async def set_pref(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO prefs (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


async def log_event(db: aiosqlite.Connection, kind: str, detail: str = "") -> None:
    await db.execute(
        "INSERT INTO runtime_events (kind, detail, created_at) VALUES (?, ?, ?)",
        (kind, detail, _now()),
    )
    await db.commit()


async def count_since(db: aiosqlite.Connection, since_iso: str) -> int:
    async with db.execute(
        "SELECT COUNT(*) FROM listings WHERE first_seen_at >= ?", (since_iso,)
    ) as cur:
        row = await cur.fetchone()
    return int(row[0] if row else 0)


async def count_total(db: aiosqlite.Connection) -> int:
    async with db.execute("SELECT COUNT(*) FROM listings") as cur:
        row = await cur.fetchone()
    return int(row[0] if row else 0)


async def top_cities(db: aiosqlite.Connection, limit: int = 10) -> list[tuple[str, int]]:
    async with db.execute(
        "SELECT COALESCE(city, '?'), COUNT(*) FROM listings "
        "GROUP BY city ORDER BY COUNT(*) DESC LIMIT ?",
        (limit,),
    ) as cur:
        rows = await cur.fetchall()
    return [(r[0], int(r[1])) for r in rows]


async def recent_listings(db: aiosqlite.Connection, limit: int = 5) -> list[Listing]:
    async with db.execute(
        """
        SELECT ad_id, source, url, title, city, district, address, price_eur,
               size_m2, available_from, available_until, wg_size, deposit_eur,
               description_snippet, raw_snippet
        FROM listings
        WHERE notified_at IS NOT NULL
        ORDER BY first_seen_at DESC
        LIMIT ?
        """,
        (limit,),
    ) as cur:
        rows = await cur.fetchall()
    return [
        Listing(
            ad_id=r[0], source=r[1], url=r[2], title=r[3], city=r[4],
            district=r[5], address=r[6], price_eur=r[7], size_m2=r[8],
            available_from=r[9], available_until=r[10], wg_size=r[11],
            deposit_eur=r[12], description_snippet=r[13], raw_snippet=r[14],
        )
        for r in rows
    ]


async def last_event(db: aiosqlite.Connection, kind: str) -> tuple[str, str] | None:
    async with db.execute(
        "SELECT created_at, detail FROM runtime_events "
        "WHERE kind = ? ORDER BY id DESC LIMIT 1",
        (kind,),
    ) as cur:
        row = await cur.fetchone()
    return (row[0], row[1]) if row else None
