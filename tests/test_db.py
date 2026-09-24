from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from wg_sniper import db as dbmod
from wg_sniper.models import Listing


@pytest.fixture()
async def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    await dbmod.init_db(path)
    return path


def _mk_listing(ad_id: str, **kwargs) -> Listing:
    defaults = dict(source="wg-gesucht", url=f"https://example.de/{ad_id}.html")
    defaults.update(kwargs)
    return Listing(ad_id=ad_id, **defaults)


class TestTryInsertDedup:
    async def test_first_insert_returns_true(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            assert await dbmod.try_insert(db, _mk_listing("1")) is True

    async def test_duplicate_insert_returns_false(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            await dbmod.try_insert(db, _mk_listing("1"))
            assert await dbmod.try_insert(db, _mk_listing("1")) is False


class TestListingsWithMessageId:
    async def test_excludes_unsent_listings(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            await dbmod.try_insert(db, _mk_listing("1"))
            # never notified -> no tg_message_id
            result = await dbmod.listings_with_message_id(db)
        assert result == []

    async def test_includes_only_listings_with_message_id(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            await dbmod.try_insert(db, _mk_listing("1"))
            await dbmod.try_insert(db, _mk_listing("2"))
            await dbmod.mark_notified(db, "1", tg_message_id=555)
            # "2" notified but Telegram send failed -> no message id
            await dbmod.mark_notified(db, "2", tg_message_id=None)

            result = await dbmod.listings_with_message_id(db)

        assert len(result) == 1
        listing, tg_message_id = result[0]
        assert listing.ad_id == "1"
        assert tg_message_id == 555

    async def test_returns_full_listing_fields(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            listing = _mk_listing("1", title="Test Room", city="München",
                                  price_eur=900, rent_eur=800, utilities_eur=100)
            await dbmod.try_insert(db, listing)
            await dbmod.mark_notified(db, "1", tg_message_id=42)
            result = await dbmod.listings_with_message_id(db)

        loaded, msg_id = result[0]
        assert loaded.title == "Test Room"
        assert loaded.city == "München"
        assert loaded.price_eur == 900
        assert loaded.rent_eur == 800
        assert loaded.utilities_eur == 100
        assert msg_id == 42


class TestMarkEnrichedPreservesAdId:
    async def test_enriched_fields_update_correct_row(self, db_path: Path) -> None:
        async with aiosqlite.connect(db_path) as db:
            await dbmod.try_insert(db, _mk_listing("1", price_eur=58))
            await dbmod.try_insert(db, _mk_listing("2", price_eur=58))

            fixed = _mk_listing("1", price_eur=900, title="Fixed title")
            await dbmod.mark_enriched(db, fixed)

            result = await dbmod.recent_listings(db, limit=10)
            await dbmod.mark_notified(db, "1", 1)
            await dbmod.mark_notified(db, "2", 2)
            result = await dbmod.recent_listings(db, limit=10)

        by_id = {l.ad_id: l for l in result}
        assert by_id["1"].price_eur == 900
        assert by_id["1"].title == "Fixed title"
        assert by_id["2"].price_eur == 58
