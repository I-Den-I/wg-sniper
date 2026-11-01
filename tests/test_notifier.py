from __future__ import annotations

from wg_sniper.models import Listing
from wg_sniper.notifier import format_listing


def _mk(**kwargs) -> Listing:
    defaults = dict(ad_id="1", source="wg-gesucht", url="https://example.de/1.html")
    defaults.update(kwargs)
    return Listing(**defaults)


class TestSuppressGarbageValues:
    def test_lone_colon_available_from_suppressed(self) -> None:
        listing = _mk(title="Test", available_from=":")
        msg = format_listing(listing)
        assert "From" not in msg

    def test_empty_string_wg_size_suppressed(self) -> None:
        listing = _mk(title="Test", wg_size="")
        msg = format_listing(listing)
        assert "👥" not in msg

    def test_whitespace_district_suppressed(self) -> None:
        listing = _mk(title="Test", city="München", district="   ")
        msg = format_listing(listing)
        assert "München" in msg
        assert "· " not in msg.split("📍")[1].split("\n")[0]


class TestPriceBreakdown:
    def test_shows_breakdown_when_both_components_present(self) -> None:
        listing = _mk(title="X", price_eur=900, rent_eur=800, utilities_eur=100)
        msg = format_listing(listing)
        assert "900" in msg
        assert "800+100" in msg

    def test_shows_only_total_when_no_components(self) -> None:
        listing = _mk(title="X", price_eur=900)
        msg = format_listing(listing)
        assert "900" in msg
        assert "800+100" not in msg
        assert "(" not in msg.split("💶")[1].split("·")[0]

    def test_shows_rent_when_no_total(self) -> None:
        listing = _mk(title="X", rent_eur=800)
        msg = format_listing(listing)
        assert "800" in msg


class TestLabels:
    def test_english_labels(self) -> None:
        listing = _mk(title="X", available_from="01.10.2026", deposit_eur=1500)
        msg = format_listing(listing)
        assert "From: 01.10.2026" in msg
        assert "Deposit: 1500 €" in msg
        assert "Listing →" in msg


class TestNoEmptyDepositLine:
    def test_zero_deposit_not_shown(self) -> None:
        listing = _mk(title="X", deposit_eur=0)
        msg = format_listing(listing)
        assert "🔐" not in msg

    def test_none_deposit_not_shown(self) -> None:
        listing = _mk(title="X", deposit_eur=None)
        msg = format_listing(listing)
        assert "🔐" not in msg


class TestHtmlEscaping:
    def test_title_with_html_escaped(self) -> None:
        listing = _mk(title="Test <script>alert(1)</script>")
        msg = format_listing(listing)
        assert "<script>" not in msg
        assert "&lt;script&gt;" in msg


class TestSourceLabel:
    def test_wg_gesucht_label(self) -> None:
        assert "WG-Gesucht" in format_listing(_mk(title="X"))

    def test_kleinanzeigen_label(self) -> None:
        listing = _mk(title="X", source="kleinanzeigen", ad_id="ka:1")
        assert "Kleinanzeigen" in format_listing(listing)
