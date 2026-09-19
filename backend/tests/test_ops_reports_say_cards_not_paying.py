"""The founder's own reports must not call a card on file "paying".

`prod_pulse` counts accounts with a `stripe_customer_id`, which is set when
Stripe Checkout completes, i.e. when a card is entered and a trial starts. It
is not a charge. The weekly email still put that count in its subject and
headline as "N paying", and its signal box said "Someone is paying", while
every account in that count could be an uncharged trial or a card whose first
charge failed. The founder reads this email to decide what to do next, so a
wrong word here steers real decisions.

`diagnostics` had the same fault under a `[PAID]` heading over a count of
subscriptions by Stripe status. A status string is not proof of a charge.

The counts themselves are unchanged. Only the words are.
"""
from datetime import UTC, datetime, timedelta

import app.db as _db
from app.models import Subscription, User
from app.scripts import diagnostics, prod_pulse


async def _seed() -> None:
    now = datetime.now(UTC)
    async with _db.SessionLocal() as s:
        # A card trial: card on file, never charged.
        s.add(User(
            id="card", email="card@example.com", tier="premium",
            password_hash="x", stripe_customer_id="cus_TESTcardtrial01",
        ))
        # An engaged free user with no card: a hot lead.
        s.add(User(
            id="lead", email="lead@example.com", tier="free",
            password_hash="x", activated_at=now,
        ))
        await s.flush()
        s.add(Subscription(
            id="sub_TESTcardtrial01", user_id="card", status="active",
            tier="premium", current_period_end=now + timedelta(days=30),
        ))
        await s.commit()


async def test_pulse_counts_cards_and_does_not_call_them_paying(monkeypatch):
    await _seed()
    d = await prod_pulse.gather()
    assert d["cards"] == 1, "the count itself must not change"
    assert len(d["leads"]) == 1

    html = prod_pulse.render(d)
    assert "paying" not in html.lower(), "a card on file is not a payment"
    assert "card(s) on file" in html
    # The channel table's third column counts cards, not payments.
    assert ">paid<" not in html

    sent: list[tuple[str, str]] = []

    async def _fake_send(to, subject, body, **_kw):
        sent.append((subject, body))
        return {"ok": True}

    monkeypatch.setattr(prod_pulse, "send_email", _fake_send)
    await prod_pulse.main()
    (subject, _body), = sent
    assert "paying" not in subject.lower()
    assert "1 card(s) on file" in subject


async def test_diagnostics_does_not_label_subscriptions_paid(capsys):
    await _seed()
    await diagnostics.main()
    out = capsys.readouterr().out
    assert "[PAID]" not in out, "a subscription status is not proof of a charge"
    # Same numbers as before, under an honest heading.
    assert "active=1  total=1" in out
