from __future__ import annotations

from wg_sniper.i18n import DEFAULT_LANG, SUPPORTED, normalize, t


class TestTranslation:
    def test_all_keys_have_both_languages(self) -> None:
        from wg_sniper.i18n import STRINGS
        for key, entry in STRINGS.items():
            for lang in SUPPORTED:
                assert lang in entry, f"missing {lang} for key {key!r}"

    def test_ukrainian_lookup(self) -> None:
        assert "pong" in t("pong", "uk", uptime="1m 5s")

    def test_english_lookup(self) -> None:
        assert "pong" in t("pong", "en", uptime="1m 5s")

    def test_unknown_key_returns_key(self) -> None:
        assert t("nonexistent_key_foo", "uk") == "nonexistent_key_foo"

    def test_missing_placeholder_does_not_crash(self) -> None:
        result = t("pong", "uk")
        assert isinstance(result, str)

    def test_format_placeholders(self) -> None:
        result = t("mem_body", "en", total="4 GB", used="2 GB", free="1 GB", pct="50")
        assert "4 GB" in result
        assert "50" in result


class TestNormalize:
    def test_supported_lang_passthrough(self) -> None:
        assert normalize("uk") == "uk"
        assert normalize("en") == "en"

    def test_unknown_falls_back_to_default(self) -> None:
        assert normalize("de") == DEFAULT_LANG
        assert normalize(None) == DEFAULT_LANG
        assert normalize("") == DEFAULT_LANG
