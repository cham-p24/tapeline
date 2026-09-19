"""The pre-charge notice check prints no usable Stripe id into its public log.

`check_precharge_notices` runs daily from GitHub Actions
(precharge-notice-check.yml) over `flyctl ssh console`, and everything it
prints lands in the Actions log of a PUBLIC repository. Its MISSED, DROPPED,
PENDING and OK rows printed each subscription's raw `sub_` id and customer's
raw `cus_` id there.

Now the printed rows carry a short one-way hash of each id instead (the same
`prefix#sha256[:10]` form `billing_audit` uses, so one account reads the same
in both jobs). The founder alert is private (Telegram, or email to the
founder), so it keeps the raw ids: that is where someone has to act on a
finding. stripe-python's own request logger is held at WARNING so no request
URL can put a customer id into the log either.
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import re

import pytest

from app.scripts import check_precharge_notices as cpn

SUB_ID = "sub_1TestPrechargeLogAa"
CUS_ID = "cus_TestPrechargeLogBb"
RAW_ID = re.compile(r"\b(?:sub|cus)_[A-Za-z0-9]+")


def _hash(obj_id: str) -> str:
    """The one-way form, computed here rather than imported, so the test pins
    the algorithm that billing_audit's log uses as well."""
    prefix = obj_id.split("_", 1)[0]
    return f"{prefix}#{hashlib.sha256(obj_id.encode()).hexdigest()[:10]}"


def _row(sub_id: str, cust: str, **extra) -> dict:
    return {
        "sub": sub_id, "customer": cust, "status": "active",
        "renews": "2026-09-20", "days_out": -1.0,
        "notices": ["invoice.upcoming"], **extra,
    }


def _every_section() -> dict:
    """One row in each of the four sections, each with its own ids."""
    return {
        "totals": {"invoice.upcoming": 1, "customer.subscription.trial_will_end": 0},
        "recorded_count": 3,
        "missed": [_row("sub_1MissedAaaaaaa", "cus_MissedBbbbbbb", notices=[])],
        "dropped": [_row("sub_1DroppedAaaaaa", "cus_DroppedBbbbbb", unrecorded=["evt_1Dropped"])],
        "pending": [_row("sub_1PendingAaaaaa", "cus_PendingBbbbbb", notices=[], days_out=3.0)],
        "healthy": [_row(SUB_ID, CUS_ID)],
    }


def test_the_one_way_hash_is_stable_and_keeps_only_the_prefix():
    assert cpn._mask_stripe_id(CUS_ID) == _hash(CUS_ID)
    assert cpn._mask_stripe_id(CUS_ID) == cpn._mask_stripe_id(CUS_ID)
    assert cpn._mask_stripe_id(SUB_ID).startswith("sub#")
    assert CUS_ID not in cpn._mask_stripe_id(CUS_ID)
    assert cpn._mask_stripe_id(None) == "(none)"
    assert cpn._mask_stripe_id("") == "(none)"


def test_no_section_prints_a_raw_subscription_or_customer_id():
    d = _every_section()
    _subject, text, alert = cpn.render(d)

    assert alert is True
    for section in ("MISSED", "DROPPED", "PENDING", "OK"):
        assert section in text
    assert RAW_ID.findall(text) == [], text
    for key in ("missed", "dropped", "pending", "healthy"):
        row = d[key][0]
        assert _hash(row["sub"]) in text, key
        assert _hash(row["customer"]) in text, key
    # The event id is not a customer identifier and is what a dropped delivery
    # is resent by, so it stays as it is.
    assert "evt_1Dropped" in text


def test_the_private_rendering_keeps_the_raw_ids_for_the_founder():
    _subject, text, _alert = cpn.render(_every_section(), public=False)
    assert "sub_1MissedAaaaaaa" in text and "cus_MissedBbbbbbb" in text
    assert SUB_ID in text and CUS_ID in text


@pytest.mark.asyncio
async def test_main_prints_hashes_and_alerts_the_founder_with_raw_ids(monkeypatch, capsys):
    d = _every_section()

    async def _gather():
        return d

    alerts: list[dict] = []

    async def _deliver(*, subject, text):
        alerts.append({"subject": subject, "text": text})

    from app.services import telegram

    monkeypatch.setattr(cpn.settings, "stripe_secret_key", "sk_test_not_a_real_key", raising=False)
    monkeypatch.setattr(cpn, "gather", _gather)
    monkeypatch.setattr(telegram, "deliver_founder_alert", _deliver)

    code = await cpn.main()

    printed = capsys.readouterr()
    assert code == 1
    assert RAW_ID.findall(printed.out + printed.err) == [], printed.out
    assert _hash(SUB_ID) in printed.out and _hash(CUS_ID) in printed.out
    assert len(alerts) == 1
    assert SUB_ID in alerts[0]["text"] and CUS_ID in alerts[0]["text"]
    assert RAW_ID.findall(alerts[0]["subject"]) == []


def test_stripe_request_logging_is_held_at_warning(caplog):
    """stripe-python logs each request at INFO on the "stripe" logger, with the
    customer id in the URL. Re-importing the module must set the level itself,
    not rely on another script having done it earlier in the process."""
    stripe_logger = logging.getLogger("stripe")
    before = stripe_logger.level
    try:
        stripe_logger.setLevel(logging.NOTSET)
        importlib.reload(cpn)
        assert stripe_logger.level == logging.WARNING

        with caplog.at_level(logging.INFO):
            stripe_logger.info("message='Request to Stripe api' path=/v1/customers/%s", CUS_ID)
        assert CUS_ID not in caplog.text
    finally:
        stripe_logger.setLevel(before)
