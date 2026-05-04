from __future__ import annotations

import urllib.parse

from src.launch_smoke import _next_script_paths, build_telegram_init_data


def test_next_script_paths_extracts_next_scripts_only() -> None:
    html = """
    <script src="/_next/static/chunks/a.js"></script>
    <script src="/plain.js"></script>
    <script src="/_next/static/chunks/b.js"></script>
    """

    assert _next_script_paths(html) == ["/_next/static/chunks/a.js", "/_next/static/chunks/b.js"]


def test_build_telegram_init_data_contains_signed_fields() -> None:
    init_data = build_telegram_init_data(bot_token="123456:test-token", user_id=42, auth_date=1_700_000_000)
    parsed = dict(urllib.parse.parse_qsl(init_data))

    assert parsed["auth_date"] == "1700000000"
    assert parsed["query_id"] == "smoke-42-1700000000"
    assert '"id":42' in parsed["user"]
    assert len(parsed["hash"]) == 64
