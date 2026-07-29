"""Tests for the Google Ads offline-conversion upload job's pure logic.

These lock in the parts that decide correctness of value-based bidding — the
first-charge value map, click-id precedence, the Ads timestamp format, and the
dry-run credential gate. No DB or google-ads dependency needed (that's the
point of keeping this logic pure). See
app/scripts/upload_google_ads_conversions.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.scripts.upload_google_ads_conversions import (
    _CRED_ENV,
    click_identifier,
    conversion_value,
    creds_present,
    format_conversion_time,
    rows_to_pending,
)


def _user(**kw):
    base = {
        "id": "u1",
        "signup_gclid": None,
        "signup_gbraid": None,
        "signup_wbraid": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _sub(**kw):
    base = {"id": "sub_1", "tier": "pro", "billing_period": "monthly"}
    base.update(kw)
    return SimpleNamespace(**base)


def test_conversion_value_known_tiers():
    assert conversion_value("pro", "monthly") == 9.99
    assert conversion_value("pro", "annual") == 99.0
    assert conversion_value("premium", "monthly") == 19.99
    assert conversion_value("premium", "annual") == 199.0


def test_conversion_value_case_insensitive():
    assert conversion_value("PRO", "Annual") == 99.0


def test_conversion_value_unknown_falls_to_floor_not_zero():
    # A mis-tagged / missing combo must never upload $0 or an inflated value.
    assert conversion_value("lifetime", "once") == 9.99
    assert conversion_value(None, None) == 9.99
    assert conversion_value("premium", None) == 9.99


def test_click_identifier_prefers_gclid_then_gbraid_then_wbraid():
    both = SimpleNamespace(signup_gclid="G1", signup_gbraid="B1", signup_wbraid="W1")
    assert click_identifier(both) == ("gclid", "G1")

    gbraid = SimpleNamespace(signup_gclid=None, signup_gbraid="B1", signup_wbraid="W1")
    assert click_identifier(gbraid) == ("gbraid", "B1")

    wbraid = SimpleNamespace(signup_gclid=None, signup_gbraid=None, signup_wbraid="W1")
    assert click_identifier(wbraid) == ("wbraid", "W1")


def test_click_identifier_none_when_no_click_id():
    none = SimpleNamespace(signup_gclid=None, signup_gbraid=None, signup_wbraid="")
    assert click_identifier(none) is None


def test_format_conversion_time_naive_gets_utc_offset():
    s = format_conversion_time(datetime(2026, 7, 29, 12, 0, 0))
    assert s == "2026-07-29 12:00:00+00:00"


def test_format_conversion_time_converts_to_utc():
    # A +10:00 (Melbourne-ish) time must be normalised to UTC, offset explicit.
    aware = datetime(2026, 7, 29, 22, 0, 0, tzinfo=timezone(_ten_hours()))
    s = format_conversion_time(aware)
    assert s == "2026-07-29 12:00:00+00:00"


def _ten_hours():
    from datetime import timedelta

    return timedelta(hours=10)


def test_creds_present_gate(monkeypatch):
    # Missing any one → False (job runs dry). All set → True.
    for k in _CRED_ENV:
        monkeypatch.delenv(k, raising=False)
    assert creds_present() is False

    for k in _CRED_ENV:
        monkeypatch.setenv(k, "x")
    assert creds_present() is True

    monkeypatch.delenv(_CRED_ENV[0], raising=False)
    assert creds_present() is False


def test_rows_to_pending_dedups_multi_active_sub_user():
    # A duplicate-conversion user holds two active subs. Exactly one conversion
    # is emitted, and it's the caller-ordered FIRST sub — so order_id (Google's
    # cross-run dedup key) and value are deterministic, never double-counted.
    u = _user(id="u1", signup_gclid="G1")
    rows = [
        (u, _sub(id="sub_early", tier="pro", billing_period="monthly")),
        (u, _sub(id="sub_late", tier="premium", billing_period="annual")),
    ]
    pending = rows_to_pending(rows)
    assert len(pending) == 1
    assert pending[0]["order_id"] == "sub_early"
    assert pending[0]["value"] == 9.99


def test_rows_to_pending_skips_user_without_click_id():
    u = _user(id="u2")  # no gclid / gbraid / wbraid — not a paid-Google signup
    assert rows_to_pending([(u, _sub())]) == []


def test_rows_to_pending_builds_full_payload():
    u = _user(id="u3", signup_gbraid="B9")
    pending = rows_to_pending([(u, _sub(id="s3", tier="premium", billing_period="annual"))])
    assert pending == [
        {
            "user_id": "u3",
            "click_field": "gbraid",
            "click_value": "B9",
            "value": 199.0,
            "currency": "USD",
            "order_id": "s3",
        }
    ]
