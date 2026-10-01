from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from wg_sniper import sources
from wg_sniper.kleinanzeigen import (
    AD_URL_RE,
    _number,
    city_from_subject,
    parse_ad_page,
    parse_email,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kleinanzeigen"
SUBJECT = "Neue Treffer zu deiner Suche „Auf Zeit & WG - Art der Unterkunft: Privatzimmer in {} (+{} km)“"


def _mk_msg(subject: str, html: str) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = "Kleinanzeigen <noreply@kleinanzeigen.de>"
    m.set_content(html, subtype="html")
    return m


def _alert(name: str, city: str, km: int) -> EmailMessage:
    html = (FIXTURES / name).read_text(encoding="utf-8")
    return _mk_msg(SUBJECT.format(city, km), html)


class TestAdUrl:
    def test_id_only_url(self) -> None:
        m = AD_URL_RE.search("https://www.kleinanzeigen.de/s-anzeige/3527662640?savedSearchId=1&utm_source=x")
        assert m and m.group("ad_id") == "3527662640"

    def test_slug_url(self) -> None:
        m = AD_URL_RE.search("https://www.kleinanzeigen.de/s-anzeige/wg-zimmer-frei/3527662640-199-6411")
        assert m and m.group("ad_id") == "3527662640"

    def test_non_ad_urls_ignored(self) -> None:
        assert AD_URL_RE.search("https://www.kleinanzeigen.de/m-suche-verwenden.html?id=768800152") is None
        assert AD_URL_RE.search("https://www.kleinanzeigen.de/impressum.html") is None


class TestNumber:
    @pytest.mark.parametrize("text,expected", [
        ("700 €", 700), ("1.000 €", 1000), ("63,38 m²", 63),
        ("450 € VB", 450), ("VB", None), (None, None),
    ])
    def test_german_numbers(self, text, expected) -> None:
        assert _number(text) == expected


class TestSubjectCity:
    def test_city_with_radius(self) -> None:
        assert city_from_subject(SUBJECT.format("München", 50)) == "München"

    def test_two_word_city(self) -> None:
        assert city_from_subject(SUBJECT.format("Mühldorf am Inn", 15)) == "Mühldorf am Inn"

    def test_unrelated_subject(self) -> None:
        assert city_from_subject("Willkommen bei Kleinanzeigen") is None


class TestAlertEmails:
    def test_muenchen_two_ads(self) -> None:
        listings = parse_email(_alert("alert_muenchen_two_ads.html", "München", 50))
        assert [l.ad_id for l in listings] == ["ka:3513084944", "ka:3527761401"]

        first, second = listings
        assert first.title == "12 qm WG Zimmer in Gröbenzell zu vermieten"
        assert first.price_eur == 700
        assert first.url == "https://www.kleinanzeigen.de/s-anzeige/3513084944"
        # second listing has no photo (placeholder image) — title must still pair up
        assert second.title == "WG Zimmer zu vermieten Im Norden von München"
        assert second.price_eur == 680
        assert all(l.source == "kleinanzeigen" and l.city == "München" for l in listings)

    def test_landshut_one_ad(self) -> None:
        (l,) = parse_email(_alert("alert_landshut_one_ad.html", "Landshut", 15))
        assert l.ad_id == "ka:3527662640"
        assert l.title == "WG-Zimmer ab November/Dezember für 1 Person"
        assert l.price_eur == 450
        assert l.city == "Landshut"

    def test_augsburg_one_ad(self) -> None:
        (l,) = parse_email(_alert("alert_augsburg_one_ad.html", "Augsburg", 15))
        assert l.ad_id == "ka:3527579194"
        assert l.price_eur == 500
        assert "tracking" not in l.url and "utm_" not in l.url

    def test_email_without_ads(self) -> None:
        html = '<a href="https://www.kleinanzeigen.de/impressum.html">Impressum</a>'
        assert parse_email(_mk_msg("Willkommen", html)) == []


class TestAdPage:
    def test_single_room_listing(self) -> None:
        e = parse_ad_page((FIXTURES / "ad_3527662640.html").read_text(encoding="utf-8"))
        # hidden "Reserviert • Gelöscht •" spans must not leak into the title
        assert e.title == "WG-Zimmer ab November/Dezember für 1 Person"
        assert e.price_eur == 450
        assert e.size_m2 == 14
        assert e.address == "84169 Bayern - Altfraunhofen"
        assert e.district == "Altfraunhofen"
        assert e.available_from == "November 2026"
        assert e.wg_size is None
        assert e.description_snippet and e.description_snippet.startswith("3er-WG")

    def test_flatmates_become_wg_size(self) -> None:
        e = parse_ad_page((FIXTURES / "ad_3513084944.html").read_text(encoding="utf-8"))
        assert e.price_eur == 700
        assert e.size_m2 == 12
        assert e.wg_size == "3er WG"
        assert e.district == "Gröbenzell"

    def test_whole_flat_area_not_reported_as_room_size(self) -> None:
        """'Wohnfläche 78 m², Zimmer 3' is the flat, not the room."""
        e = parse_ad_page((FIXTURES / "ad_3527761401.html").read_text(encoding="utf-8"))
        assert e.price_eur == 680
        assert e.size_m2 is None
        assert e.district == "Milbertshofen - Am Hart"
        assert e.wg_size == "2er WG"

    def test_garbage_html(self) -> None:
        e = parse_ad_page("<html><body>nothing</body></html>")
        assert e.price_eur is None and e.title is None


class TestSourceRegistry:
    def test_dispatch_by_sender(self) -> None:
        assert sources.for_sender("Kleinanzeigen <noreply@kleinanzeigen.de>").name == "kleinanzeigen"
        assert sources.for_sender("WG-Gesucht.de <webmaster@wg-gesucht.de>").name == "wg-gesucht"
        assert sources.for_sender("someone@example.com") is None
        assert sources.for_sender(None) is None

    def test_searches_cover_both_sources(self) -> None:
        assert ("wg-gesucht.de", "Suchauftrag") in sources.SEARCHES
        assert ("kleinanzeigen.de", "Neue Treffer") in sources.SEARCHES

    def test_subject_hints_match_real_subjects(self) -> None:
        assert "Neue Treffer" in SUBJECT
        assert "Suchauftrag" in '"München": 2 neue Angebote zu Ihrem Suchauftrag gefunden'
        assert "Suchauftrag" in '"Rosenheim": 1 neues Angebot zu Ihrem Suchauftrag gefunden'

    def test_ids_do_not_collide_across_sources(self) -> None:
        (ka,) = parse_email(_alert("alert_landshut_one_ad.html", "Landshut", 15))
        assert ka.ad_id.startswith("ka:")
