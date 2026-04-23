from __future__ import annotations

from src.core import legacy_runtime


def test_legacy_runtime_is_thin_compatibility_shell() -> None:
    assert not hasattr(legacy_runtime, "LegacySharedRuntime")
    assert legacy_runtime.chunk_text("one two") == ["one two"]
    assert legacy_runtime.strip_internal_thoughts(" visible ") == "visible"
