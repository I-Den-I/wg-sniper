from __future__ import annotations

from wg_sniper.enricher import parse_ad_page


class TestPriceExtraction:
    def test_gesamtmiete_label(self) -> None:
        html = """
        <html><body>
          <div><span>Gesamtmiete</span></div>
          <div>550 €</div>
        </body></html>
        """
        e = parse_ad_page(html)
        assert e.price_eur == 550

    def test_fallback_price_from_body(self) -> None:
        html = """
        <html><body>
          <p>Das Zimmer kostet 480 € pro Monat.</p>
        </body></html>
        """
        e = parse_ad_page(html)
        assert e.price_eur == 480

    def test_no_price(self) -> None:
        html = "<html><body><p>Just some text.</p></body></html>"
        e = parse_ad_page(html)
        assert e.price_eur is None


class TestSizeExtraction:
    def test_size_from_body(self) -> None:
        html = "<html><body><p>Das Zimmer ist 18 m² groß.</p></body></html>"
        e = parse_ad_page(html)
        assert e.size_m2 == 18

    def test_no_size(self) -> None:
        html = "<html><body><p>Just some text.</p></body></html>"
        e = parse_ad_page(html)
        assert e.size_m2 is None


class TestDescriptionExtraction:
    def test_description_snippet_truncated(self) -> None:
        long_desc = "A" * 400
        html = f'<html><body><div id="ad_description_text">{long_desc}</div></body></html>'
        e = parse_ad_page(html)
        assert e.description_snippet is not None
        assert e.description_snippet.endswith("…")
        assert len(e.description_snippet) <= 281


class TestApplyEnrichmentToListing:
    def test_apply_only_non_none_fields(self) -> None:
        from wg_sniper.models import Enrichment, Listing
        listing = Listing(ad_id="1", source="wg-gesucht", url="x", title="orig",
                          city="München", price_eur=None)
        e = Enrichment(price_eur=500, district="Schwabing")
        e.apply_to(listing)
        assert listing.price_eur == 500
        assert listing.district == "Schwabing"
        assert listing.city == "München"
        assert listing.title == "orig"
