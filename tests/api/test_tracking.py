"""Focused tracker transport compatibility tests."""

from pathlib import Path


TRACKER_PATH = Path("app/static/js/tracker.js")


def test_tracker_uses_same_origin_cookie_transport_without_requiring_a_token() -> None:
    source = TRACKER_PATH.read_text(encoding="utf-8")

    assert 'credentials: "same-origin"' in source
    assert "useCookieAuth" in source
    assert 'if (token) {' in source
    assert 'headers.Authorization = "Bearer " + token' in source


def test_tracker_preserves_batched_non_blocking_delivery_contract() -> None:
    source = TRACKER_PATH.read_text(encoding="utf-8")

    assert "batchSize: 20" in source
    assert "flushIntervalMs: 10000" in source
    assert "keepalive: keepalive" in source
    assert "maxRetries: 3" in source
    assert 'window.addEventListener("pagehide"' in source
    assert "stopTimeTracking();" in source
