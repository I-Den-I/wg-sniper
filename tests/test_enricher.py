from __future__ import annotations

from pathlib import Path

import pytest

from wg_sniper.enricher import (
    _district_from_address,
    _valid_deposit,
    _valid_price,
    _valid_size,
    parse_ad_page,
)
from wg_sniper.models import Enrichment, Listing


FIXTURES = Path(__file__).parent / "fixtures" / "ad_pages"


class TestSanityBounds:
    def test_valid_price_accepts_normal(self) -> None:
        assert _valid_price(500) == 500
        assert _valid_price(50) == 50
        assert _valid_price(5000) == 5000

    def test_valid_price_rejects_obviously_low(self) -> None:
        """Prices below 50 € are almost certainly parse errors
        (e.g. the '35' from the banner '35,58 €')."""
        assert _valid_price(35) is None
        assert _valid_price(10) is None
        assert _valid_price(0) is None
        assert _valid_price(None) is None

    def test_valid_price_rejects_absurdly_high(self) -> None:
        assert _valid_price(99999) is None
        assert _valid_price(5001) is None

    def test_valid_size_accepts_normal(self) -> None:
        assert _valid_size(15) == 15
        assert _valid_size(100) == 100

    def test_valid_size_rejects_out_of_range(self) -> None:
        assert _valid_size(1) is None
        assert _valid_size(500) is None
        assert _valid_size(None) is None

    def test_valid_deposit_accepts_zero(self) -> None:
        assert _valid_deposit(0) == 0
        assert _valid_deposit(1500) == 1500

    def test_valid_deposit_rejects_absurd(self) -> None:
        assert _valid_deposit(50000) is None


class TestDistrictExtraction:
    def test_district_after_zip_and_city(self) -> None:
        assert _district_from_address("Hellensteinstraße 81245 München Aubing-Lochhausen-Langwied") == "Aubing-Lochhausen-Langwied"

    def test_district_short(self) -> None:
        assert _district_from_address("heiterwangerstraße 34 81373 München Sendling-Westpark") == "Sendling-Westpark"

    def test_no_zip_returns_none(self) -> None:
        assert _district_from_address("Just a street name") is None

    def test_none_input(self) -> None:
        assert _district_from_address(None) is None


class TestRealAdPage14149422:
    """The 'zwei zimmer in wg' listing that was previously mis-parsed
    as '58 €' (from the promo banner) and 70m² for wg_size."""

    @pytest.fixture()
    def enrichment(self) -> Enrichment:
        html = (FIXTURES / "ad_14149422.html").read_text(encoding="utf-8")
        return parse_ad_page(html)

    def test_price_from_gesamtmiete_not_banner(self, enrichment: Enrichment) -> None:
        assert enrichment.price_eur == 900

    def test_rent_component_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.rent_eur == 800

    def test_utilities_component_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.utilities_eur == 100

    def test_deposit_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.deposit_eur == 2400

    def test_size_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.size_m2 == 66

    def test_wg_size_extracted_as_readable_string(self, enrichment: Enrichment) -> None:
        assert enrichment.wg_size == "3er WG"

    def test_available_from_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.available_from == "01.10.2026"

    def test_address_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.address is not None
        assert "heiterwangerstraße 34" in enrichment.address
        assert "81373" in enrichment.address

    def test_district_extracted(self, enrichment: Enrichment) -> None:
        assert enrichment.district == "Sendling-Westpark"

    def test_title_from_h1(self, enrichment: Enrichment) -> None:
        assert enrichment.title is not None
        assert "zwei zimmer" in enrichment.title.lower()


class TestRealAdPage14149247:
    """Second listing to confirm the layout works across different listings."""

    @pytest.fixture()
    def enrichment(self) -> Enrichment:
        html = (FIXTURES / "ad_14149247.html").read_text(encoding="utf-8")
        return parse_ad_page(html)

    def test_price_from_gesamtmiete(self, enrichment: Enrichment) -> None:
        assert enrichment.price_eur == 850

    def test_rent_component(self, enrichment: Enrichment) -> None:
        assert enrichment.rent_eur == 680

    def test_utilities_component(self, enrichment: Enrichment) -> None:
        assert enrichment.utilities_eur == 170

    def test_size(self, enrichment: Enrichment) -> None:
        assert enrichment.size_m2 == 10

    def test_wg_size_from_four_person_wg(self, enrichment: Enrichment) -> None:
        assert enrichment.wg_size == "4er WG"

    def test_available_from(self, enrichment: Enrichment) -> None:
        assert enrichment.available_from == "01.11.2026"

    def test_district(self, enrichment: Enrichment) -> None:
        assert enrichment.district == "Aubing-Lochhausen-Langwied"

    def test_title_from_h1(self, enrichment: Enrichment) -> None:
        assert enrichment.title is not None
        assert "möblierte WG-Zimmer" in enrichment.title
        assert "Aubing" in enrichment.title


class TestBrokenHTMLFallback:
    def test_empty_html_returns_empty_enrichment(self) -> None:
        e = parse_ad_page("")
        assert e.price_eur is None
        assert e.size_m2 is None
        assert e.title is None

    def test_malformed_html_does_not_crash(self) -> None:
        e = parse_ad_page("<html><body>random text no structure</body></html>")
        assert e.price_eur is None

    def test_no_whole_page_regex_fallback_for_price(self) -> None:
        """A stray '58 €' in body text (like the promo banner) must NOT
        become the price when key_fact/section_panel are missing."""
        html = """
        <html><body>
          <p>Schon ab 35,58 € - boosten Sie jetzt Ihre Anzeige!</p>
          <p>Some other text 999 €</p>
        </body></html>
        """
        e = parse_ad_page(html)
        assert e.price_eur is None


class TestApplyEnrichmentToListing:
    def test_apply_only_non_none_fields(self) -> None:
        listing = Listing(ad_id="1", source="wg-gesucht", url="x",
                          title="orig", city="München", price_eur=None)
        e = Enrichment(price_eur=500, district="Schwabing")
        e.apply_to(listing)
        assert listing.price_eur == 500
        assert listing.district == "Schwabing"
        assert listing.city == "München"
        assert listing.title == "orig"

    def test_enrichment_title_overrides_listing_title(self) -> None:
        listing = Listing(ad_id="1", source="wg-gesucht", url="x",
                          title="email-guessed title")
        e = Enrichment(title="Real full title from h1")
        e.apply_to(listing)
        assert listing.title == "Real full title from h1"

    def test_enrichment_none_title_keeps_original(self) -> None:
        listing = Listing(ad_id="1", source="wg-gesucht", url="x",
                          title="email title")
        e = Enrichment(price_eur=500, title=None)
        e.apply_to(listing)
        assert listing.title == "email title"
