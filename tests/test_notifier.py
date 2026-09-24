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
        msg = format_listing(listing, "uk")
        assert "Заїзд" not in msg

    def test_empty_string_wg_size_suppressed(self) -> None:
        listing = _mk(title="Test", wg_size="")
        msg = format_listing(listing, "uk")
        assert "👥" not in msg

    def test_whitespace_district_suppressed(self) -> None:
        listing = _mk(title="Test", city="München", district="   ")
        msg = format_listing(listing, "uk")
        assert "München" in msg
        assert "· " not in msg.split("📍")[1].split("\n")[0]


class TestPriceBreakdown:
    def test_shows_breakdown_when_both_components_present(self) -> None:
        listing = _mk(title="X", price_eur=900, rent_eur=800, utilities_eur=100)
        msg = format_listing(listing, "uk")
        assert "900" in msg
        assert "800+100" in msg

    def test_shows_only_total_when_no_components(self) -> None:
        listing = _mk(title="X", price_eur=900)
        msg = format_listing(listing, "uk")
        assert "900" in msg
        assert "800+100" not in msg
        assert "(" not in msg.split("💶")[1].split("·")[0]

    def test_shows_rent_when_no_total(self) -> None:
        listing = _mk(title="X", rent_eur=800)
        msg = format_listing(listing, "uk")
        assert "800" in msg


class TestLocalizedLabels:
    def test_uk_labels(self) -> None:
        listing = _mk(title="X", available_from="01.10.2026",
                      deposit_eur=1500)
        msg = format_listing(listing, "uk")
        assert "Заїзд" in msg
        assert "Застава" in msg
        assert "Оголошення" in msg

    def test_en_labels(self) -> None:
        listing = _mk(title="X", available_from="01.10.2026",
                      deposit_eur=1500)
        msg = format_listing(listing, "en")
        assert "From" in msg
        assert "Deposit" in msg
        assert "Listing" in msg

    def test_link_localization_differs(self) -> None:
        listing = _mk(title="X")
        uk_msg = format_listing(listing, "uk")
        en_msg = format_listing(listing, "en")
        assert "Оголошення" in uk_msg
        assert "Listing" in en_msg


class TestNoEmptyDepositLine:
    def test_zero_deposit_not_shown(self) -> None:
        listing = _mk(title="X", deposit_eur=0)
        msg = format_listing(listing, "uk")
        assert "🔐" not in msg

    def test_none_deposit_not_shown(self) -> None:
        listing = _mk(title="X", deposit_eur=None)
        msg = format_listing(listing, "uk")
        assert "🔐" not in msg


class TestHtmlEscaping:
    def test_title_with_html_escaped(self) -> None:
        listing = _mk(title="Test <script>alert(1)</script>")
        msg = format_listing(listing, "uk")
        assert "<script>" not in msg
        assert "&lt;script&gt;" in msg
