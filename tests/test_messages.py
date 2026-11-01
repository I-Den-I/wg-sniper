from __future__ import annotations

from wg_sniper.messages import STRINGS, t


class TestMessages:
    def test_lookup_with_placeholder(self) -> None:
        assert t("pong", uptime="1m 5s") == "🏓 pong · uptime 1m 5s"

    def test_unknown_key_returns_key(self) -> None:
        assert t("nonexistent_key_foo") == "nonexistent_key_foo"

    def test_missing_placeholder_does_not_crash(self) -> None:
        assert isinstance(t("pong"), str)

    def test_format_placeholders(self) -> None:
        result = t("mem_body", total="4 GB", used="2 GB", free="1 GB", pct="50")
        assert "4 GB" in result and "50" in result

    def test_help_lists_no_language_command(self) -> None:
        assert "/lang" not in t("help_body")
        assert "/status" in t("help_body")

    def test_texts_contain_no_cyrillic(self) -> None:
        for key, text in STRINGS.items():
            assert not any(0x400 <= ord(ch) <= 0x4FF for ch in text), key
