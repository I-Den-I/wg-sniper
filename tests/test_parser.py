from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from wg_sniper.parser import (
    AD_URL_RE,
    _unwrap_tracking,
    is_relevant_sender,
    parse_email,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _mk_msg(subject: str, html: str,
            from_hdr: str = "WG-Gesucht.de <webmaster@wg-gesucht.de>") -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = from_hdr
    m.set_content(html, subtype="html")
    return m


class TestUrlRegex:
    def test_slugless_url(self) -> None:
        m = AD_URL_RE.search("https://www.wg-gesucht.de/14138656.html")
        assert m is not None
        assert m.group("ad_id") == "14138656"
        assert m.group("slug") is None

    def test_url_with_slug(self) -> None:
        m = AD_URL_RE.search(
            "https://www.wg-gesucht.de/wg-zimmer-in-Muenchen-Moosach.14138656.html"
        )
        assert m is not None
        assert m.group("ad_id") == "14138656"
        assert m.group("slug") == "wg-zimmer-in-Muenchen-Moosach"

    def test_url_with_query_params(self) -> None:
        m = AD_URL_RE.search(
            "https://www.wg-gesucht.de/14138656.html?campaign=suchauftrag_detail"
        )
        assert m is not None
        assert m.group("ad_id") == "14138656"

    def test_url_without_ad_id_does_not_match(self) -> None:
        assert AD_URL_RE.search("https://www.wg-gesucht.de/mein-wg-gesucht.html") is None
        assert AD_URL_RE.search("https://www.wg-gesucht.de/") is None
        assert AD_URL_RE.search("https://www.wg-gesucht.de/wgg-plus-shop.html") is None


class TestTrackingUnwrap:
    def test_plain_url_untouched(self) -> None:
        url = "https://www.wg-gesucht.de/14138656.html"
        assert _unwrap_tracking(url) == url

    def test_unwraps_redirect_param(self) -> None:
        wrapped = "https://tracker.example/click?url=https%3A%2F%2Fwww.wg-gesucht.de%2F14138656.html"
        assert "wg-gesucht.de/14138656.html" in _unwrap_tracking(wrapped)


class TestSenderFilter:
    def test_matches_wg_gesucht(self) -> None:
        assert is_relevant_sender("WG-Gesucht.de <webmaster@wg-gesucht.de>", "wg-gesucht.de")

    def test_rejects_other(self) -> None:
        assert not is_relevant_sender("random@example.com", "wg-gesucht.de")

    def test_empty_header(self) -> None:
        assert not is_relevant_sender(None, "wg-gesucht.de")
        assert not is_relevant_sender("", "wg-gesucht.de")


class TestRealFixtures:
    def test_registration_email_yields_zero(self) -> None:
        html = (FIXTURES / "registration.html").read_text(encoding="utf-8")
        msg = _mk_msg("Ihre Registrierung auf WG-Gesucht.de", html)
        assert parse_email(msg) == []

    def test_muenchen_two_ads_extracted(self) -> None:
        html = (FIXTURES / "muenchen_two_ads.html").read_text(encoding="utf-8")
        subject = '"München": 2 neue Angebote zu Ihrem Suchauftrag gefunden'
        listings = parse_email(_mk_msg(subject, html))

        assert len(listings) == 2
        ad_ids = {l.ad_id for l in listings}
        assert ad_ids == {"14138656", "14138646"}

        first = next(l for l in listings if l.ad_id == "14138656")
        assert first.city == "München"
        assert first.title is not None
        assert "Neugründung" in first.title
        assert "Olympiaeinkaufszentrum" in first.title

        second = next(l for l in listings if l.ad_id == "14138646")
        assert second.city == "München"
        assert second.title == "Gemütliches Zimmer mit privatem Bad"

    def test_rosenheim_one_ad_extracted(self) -> None:
        html = (FIXTURES / "rosenheim_one_ad.html").read_text(encoding="utf-8")
        subject = '"Rosenheim": 1 neues Angebot zu Ihrem Suchauftrag gefunden'
        listings = parse_email(_mk_msg(subject, html))

        assert len(listings) == 1
        l = listings[0]
        assert l.ad_id == "14138758"
        assert l.city == "Rosenheim"
        assert l.title is not None
        assert "Helles" in l.title
        assert "möbliertes" in l.title


class TestPromoBlockRegression:
    """Regression test for the edge case where WG-Gesucht inserts a
    promotional block (WG-Gesucht+) between listings in the same email —
    this must not shift the title-to-ad pairing."""

    def test_promo_block_does_not_shift_titles(self) -> None:
        html = """
        <html><body>
          <p>Hallo, es gibt 2 neue Angebote zu Ihrem Suchauftrag "München".</p>
          <p>"Neugründung - WG-Zimmer - nahe Olympiaeinkaufszentrum"</p>
          <a href="https://www.wg-gesucht.de/1111111.html?x=1">Angebot ansehen</a>
          <a href="https://www.wg-gesucht.de/1111111.html?y=2">Chancen Check</a>
          <div class="promo">
            <p>Unser Tipp: Schneller ins neue Zuhause mit WG-Gesucht+.</p>
            <p>Dank der exklusiven Zusatzfunktionen sind Sie voraus.</p>
            <a href="https://www.wg-gesucht.de/wgg-plus-shop.html">Alle Vorteile</a>
          </div>
          <p>"4-er WG (1 Zimmer frei, Balkon) München-Hadern Erstbezug top"</p>
          <a href="https://www.wg-gesucht.de/2222222.html?x=1">Angebot ansehen</a>
        </body></html>
        """
        msg = _mk_msg('"München": 2 neue Angebote', html)
        listings = parse_email(msg)

        assert len(listings) == 2
        by_id = {l.ad_id: l for l in listings}
        assert "1111111" in by_id and "2222222" in by_id

        assert by_id["1111111"].title is not None
        assert "Olympiaeinkaufszentrum" in by_id["1111111"].title

        assert by_id["2222222"].title is not None
        assert "Hadern" in by_id["2222222"].title


class TestMimeSubjectDecode:
    def test_mime_encoded_subject_decoded(self) -> None:
        html = (FIXTURES / "muenchen_two_ads.html").read_text(encoding="utf-8")
        subject = (
            "=?UTF-8?Q?=22M=C3=BCnchen=22=3A=20=32=20neue=20Angebote?="
        )
        listings = parse_email(_mk_msg(subject, html))
        assert len(listings) == 2
        assert all(l.city == "München" for l in listings)


class TestNonWgLinksIgnored:
    def test_non_wg_gesucht_links_do_not_produce_listings(self) -> None:
        html = """
        <p>"Some very long title that would look like a room ad"</p>
        <a href="https://example.com/1234567.html">See listing</a>
        """
        msg = _mk_msg("Test", html)
        assert parse_email(msg) == []
