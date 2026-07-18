"""Lifecycle stage model, the global frequency governor, and the activation nudge.

Three contracts are pinned here, in increasing order of "would be expensive to
get wrong in production":

  1. GOVERNOR — a single user cannot receive colliding messages from two flows
     that don't know about each other. The cap holds ACROSS flows (drip +
     nudge + digest), not just within one, because the worker threads ONE
     governor through all of them.

  2. ACTIVATION NUDGE — fires only on genuine zero-activity, at most twice
     (~6h and ~48h after signup), and never a third time. Opted-out and
     unsubscribed users are excluded.

  3. RULE 7 (the compliance hard constraint) — no template in the activation
     series may report how a user's watched tickers MOVED or performed. This
     is asserted against the RENDERED HTML, not the source, because the whole
     point is what lands in the reader's inbox.

Assertion strategy mirrors test_lifecycle_emails.py: we assert on the SPECIFIC
seeded user's drip_state, never the aggregate counts dict. The test DB is
shared for the whole session (conftest creates tables once, never truncates),
so residue from other tests can inflate an orchestrator's return counts.

send_email returns {"skipped": True} without RESEND_API_KEY (always the case in
CI, which conftest enforces by popping the env var), so tests that need a send
to COUNT monkeypatch it to a delivered result. Tests asserting the no-key
no-op deliberately omit the patch.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.models import AlertRule, User, WatchlistItem
from app.services.email import (
    render_activation_alert_email,
    render_activation_ask_email,
    render_activation_first_scan_email,
    render_activation_watchlist_email,
    run_activation_nudge_drip,
    run_re_engagement_drip,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref
from app.services.lifecycle import (
    MAX_LIFECYCLE_SENDS_PER_WEEK,
    ActivitySnapshot,
    FrequencyGovernor,
    LifecycleStage,
    SendClass,
    SendLedger,
    has_recorded_activity,
    resolve_stage,
)


async def _fake_send_ok(*_a, **_k):
    """A delivered send — no 'skipped' key, so the flow stamps state."""
    return {"id": "test-msg"}


# ── Seed helpers ─────────────────────────────────────────────────────────────

async def _seed_inactive_user(
    *,
    age: timedelta,
    trial_drip: bool = True,
    drip_state: str = "",
    tier: str = "free",
    trial_ends_at: datetime | None = None,
    email_prefs: int | None = None,
    with_watchlist: bool = False,
    with_alert: bool = False,
    lookups_reset_on=None,
    activated_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> tuple[str, str]:
    """Insert a user aged `age` ago with NO recorded activity by default.

    `created_at` is set explicitly (the server_default only fills when the
    value is omitted) so the user lands inside or outside a nudge window.
    Every activity signal has its own flag so a test can switch exactly one
    on and prove it suppresses the nudge.
    """
    uid = f"gov_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS if email_prefs is None else email_prefs
    if not trial_drip:
        prefs &= ~int(EmailPref.TRIAL_DRIP)
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="GovTest",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            drip_state=drip_state,
            created_at=datetime.now(UTC) - age,
            trial_ends_at=trial_ends_at,
            lookups_reset_on=lookups_reset_on,
            activated_at=activated_at,
            last_seen_at=last_seen_at,
        ))
        if with_watchlist:
            s.add(WatchlistItem(user_id=uid, symbol="AAPL"))
        if with_alert:
            s.add(AlertRule(user_id=uid, name="t", rule_type="score"))
        await s.commit()
    return uid, email


async def _drip_state(uid: str) -> set[str]:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return set((u.drip_state or "").split(",")) - {""}


def _user(**kw) -> User:
    """A detached in-memory User for pure-function tests (no DB round-trip)."""
    base = dict(
        id=f"mem_{_uuid.uuid4().hex}",
        email="mem@example.com",
        tier="free",
        drip_state="",
        email_prefs=DEFAULT_PREFS,
        lookups_today=0,
    )
    base.update(kw)
    return User(**base)


# ═══════════════════════════════════════════════════════════════════════════
# 1. The frequency governor
# ═══════════════════════════════════════════════════════════════════════════

def test_governor_enforces_min_gap_across_different_flows():
    """The core cross-flow guarantee.

    Flow A sends, then flow B — a DIFFERENT orchestrator with a different
    token — asks to send to the same user moments later. Before the governor
    existed, both went out because each flow only knew its own dedupe token.
    """
    gov = FrequencyGovernor(ledger=SendLedger())
    u = _user()

    assert gov.allows(u, SendClass.LIFECYCLE, token="re14") is True
    gov.record(u, SendClass.LIFECYCLE)

    # A different flow, a different token, the same user, same tick.
    assert gov.allows(u, SendClass.LIFECYCLE, token="wb30") is False
    assert gov.allows(u, SendClass.LIFECYCLE, token="act_scan6h") is False
    assert gov.blocked == 2


def test_governor_caps_lifecycle_sends_per_week():
    """The rolling weekly ceiling, tested by back-dating ledger entries past
    the min-gap window so only the weekly cap can be doing the blocking."""
    ledger = SendLedger()
    gov = FrequencyGovernor(ledger=ledger)
    u = _user()

    import time
    now = time.time()
    # Three sends, each 2 days apart — all clear of MIN_LIFECYCLE_GAP_HOURS.
    for days_ago in (5, 3, 1):
        ledger.record(u.id, now - days_ago * 86400)

    assert MAX_LIFECYCLE_SENDS_PER_WEEK == 3
    assert gov.allows(u, SendClass.LIFECYCLE, token="annual_p") is False


def test_governor_never_blocks_transactional():
    """A receipt must always arrive — and must not consume the budget."""
    gov = FrequencyGovernor(ledger=SendLedger())
    u = _user()
    gov.record(u, SendClass.LIFECYCLE)

    assert gov.allows(u, SendClass.LIFECYCLE) is False
    assert gov.allows(u, SendClass.TRANSACTIONAL) is True

    # Transactional sends are not recorded, so they can't starve a lifecycle
    # send later.
    fresh = FrequencyGovernor(ledger=SendLedger())
    v = _user()
    for _ in range(5):
        fresh.record(v, SendClass.TRANSACTIONAL)
    assert fresh.allows(v, SendClass.LIFECYCLE) is True


def test_governor_never_blocks_scheduled_but_does_record_it():
    """A digest the user asked for always goes out — but it counts, so a
    lifecycle nudge won't pile on top of it the same day."""
    gov = FrequencyGovernor(ledger=SendLedger())
    u = _user()
    gov.record(u, SendClass.LIFECYCLE)

    # Blocked for lifecycle, still permitted for the opted-in digest.
    assert gov.allows(u, SendClass.LIFECYCLE) is False
    assert gov.allows(u, SendClass.SCHEDULED) is True

    # And the reverse direction: a digest suppresses a following nudge.
    gov2 = FrequencyGovernor(ledger=SendLedger())
    v = _user()
    assert gov2.allows(v, SendClass.SCHEDULED) is True
    gov2.record(v, SendClass.SCHEDULED)
    assert gov2.allows(v, SendClass.LIFECYCLE, token="act_scan6h") is False


def test_governor_blocks_globally_unsubscribed_user():
    """email_prefs == 0 is the 'unsubscribe from everything' state written by
    services/unsubscribe. Nothing but transactional may pass."""
    gov = FrequencyGovernor(ledger=SendLedger())
    u = _user(email_prefs=0)

    assert gov.allows(u, SendClass.LIFECYCLE, token="act_scan6h") is False
    assert gov.allows(u, SendClass.SCHEDULED) is False
    assert gov.allows(u, SendClass.TRANSACTIONAL) is True


def test_governor_treats_unset_prefs_as_opted_in():
    """None is an unset column on an in-memory row, NOT an opt-out — matching
    email_prefs.wants(), which deliberately defaults to sending."""
    gov = FrequencyGovernor(ledger=SendLedger())
    assert gov.allows(_user(email_prefs=None), SendClass.LIFECYCLE) is True


def test_governor_blocks_undeliverable_address():
    gov = FrequencyGovernor(ledger=SendLedger())
    u = _user(email_undeliverable_at=datetime.now(UTC))
    assert gov.allows(u, SendClass.LIFECYCLE, token="act_scan6h") is False


def test_governor_caps_the_activation_series_at_four_messages():
    """MAX_ACTIVATION_SERIES_MESSAGES = 4 counting the day-0 welcome, so three
    tokenised sends is the ceiling — the fourth is refused even on a user with
    an otherwise-empty send ledger."""
    gov = FrequencyGovernor(ledger=SendLedger())
    # Three activation tokens already stamped = welcome + 3 = the full series.
    u = _user(drip_state="act_scan6h,act_ask48h,act_wl")
    assert gov.allows(u, SendClass.LIFECYCLE, token="act_alert") is False

    # Two stamped still leaves room for one more.
    v = _user(drip_state="act_scan6h,act_ask48h")
    assert v.id != u.id
    assert gov.allows(v, SendClass.LIFECYCLE, token="act_wl") is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. Lifecycle stage resolution
# ═══════════════════════════════════════════════════════════════════════════

def test_stage_new_for_signup_with_no_activity():
    u = _user(created_at=datetime.now(UTC) - timedelta(hours=8))
    assert resolve_stage(u) is LifecycleStage.NEW


def test_stage_new_outranks_trialing_for_a_bounced_signup():
    """A bounced trial signup needs 'here's the first thing to do', not
    'your trial is ticking' — so NEW wins while activity is zero."""
    u = _user(
        tier="premium",
        created_at=datetime.now(UTC) - timedelta(hours=8),
        trial_ends_at=datetime.now(UTC) + timedelta(days=13),
    )
    assert resolve_stage(u) is LifecycleStage.NEW


def test_stage_trialing_once_the_user_has_actually_done_something():
    now = datetime.now(UTC)
    u = _user(
        tier="premium",
        created_at=now - timedelta(hours=8),
        trial_ends_at=now + timedelta(days=13),
        activated_at=now - timedelta(hours=1),
    )
    assert resolve_stage(u) is LifecycleStage.TRIALING


def test_stage_paid_beats_everything():
    now = datetime.now(UTC)
    u = _user(
        tier="premium",
        stripe_customer_id="cus_123",
        created_at=now - timedelta(days=200),
        trial_ends_at=now - timedelta(days=180),
    )
    assert resolve_stage(u) is LifecycleStage.PAID


def test_stage_dormant_after_two_weeks_quiet():
    now = datetime.now(UTC)
    u = _user(
        created_at=now - timedelta(days=90),
        activated_at=now - timedelta(days=80),
        last_seen_at=now - timedelta(days=30),
    )
    assert resolve_stage(u) is LifecycleStage.DORMANT


def test_has_recorded_activity_fails_safe_on_any_signal():
    """Every one of these alone is enough to call the user active, because
    telling someone who HAS used the product that they haven't is the worse
    error."""
    now = datetime.now(UTC)
    created = now - timedelta(hours=8)

    assert has_recorded_activity(_user(created_at=created)) is False
    assert has_recorded_activity(_user(created_at=created, activated_at=now)) is True
    assert has_recorded_activity(_user(created_at=created, lookups_today=1)) is True
    assert has_recorded_activity(
        _user(created_at=created, lookups_reset_on=now.date())
    ) is True
    assert has_recorded_activity(
        _user(created_at=created), ActivitySnapshot(has_watchlist_item=True),
    ) is True
    # Came back to the site hours after signing up.
    assert has_recorded_activity(
        _user(created_at=created, last_seen_at=created + timedelta(hours=4)),
    ) is True
    # Same session as signup (the last_seen bump is throttled hourly) —
    # that is what a single bounce looks like, so still inactive.
    assert has_recorded_activity(
        _user(created_at=created, last_seen_at=created + timedelta(minutes=5)),
    ) is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. The activation nudge
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_nudge_fires_at_6h_on_genuine_zero_activity(monkeypatch):
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8))

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert "act_scan6h" in await _drip_state(uid)


@pytest.mark.asyncio
async def test_nudge_does_not_fire_before_six_hours(monkeypatch):
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=2))

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"with_watchlist": True},
        {"with_alert": True},
        {"activated_at": datetime.now(UTC)},
        {"lookups_reset_on": datetime.now(UTC).date()},
    ],
    ids=["watchlist", "alert_rule", "activated_stamp", "consumed_lookup"],
)
async def test_nudge_suppressed_by_any_real_activity(monkeypatch, kwargs):
    """The nudge says 'you haven't started yet'. Sending that to someone who
    HAS started is the failure mode this guards."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8), **kwargs)

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_nudge_suppressed_when_user_came_back_to_the_site(monkeypatch):
    """last_seen_at meaningfully after created_at means they returned — no
    artefact required. This one is Python-side, so it also proves the
    fail-safe re-check runs after the SQL pre-filter."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    created_ago = timedelta(hours=8)
    uid, _ = await _seed_inactive_user(
        age=created_ago,
        last_seen_at=datetime.now(UTC) - timedelta(hours=2),
    )

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_nudge_excludes_opted_out_users(monkeypatch):
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8), trial_drip=False)

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_nudge_excludes_globally_unsubscribed_users(monkeypatch):
    """email_prefs == 0 — the governor is the thing that catches this one."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8), email_prefs=0)

    async with session_scope() as s:
        await run_activation_nudge_drip(
            s, governor=FrequencyGovernor(ledger=SendLedger()),
        )

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_nudge_second_stage_fires_at_48h(monkeypatch):
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(
        age=timedelta(hours=60), drip_state="act_scan6h",
    )

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert "act_ask48h" in await _drip_state(uid)


@pytest.mark.asyncio
async def test_nudge_never_sends_a_third_time(monkeypatch):
    """Both stages already sent and the user is STILL inactive and still
    inside both windows. Nothing further may be added — 'then STOP'."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(
        age=timedelta(hours=60), drip_state="act_ask48h,act_scan6h",
    )

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == {"act_scan6h", "act_ask48h"}


@pytest.mark.asyncio
async def test_nudge_is_idempotent_across_repeated_hourly_runs(monkeypatch):
    """The worker calls this every hour; a user sits in the 6-24h window for
    eighteen of them. Exactly one send."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8))

    for _ in range(5):
        async with session_scope() as s:
            await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == {"act_scan6h"}


@pytest.mark.asyncio
async def test_nudge_skips_stale_signups_outside_the_window(monkeypatch):
    """A worker that was down for a week must not wake up and email a month
    of old signups."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_inactive_user(age=timedelta(days=30))

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_nudge_is_a_noop_without_an_api_key():
    """No monkeypatch — real send_email, no RESEND_API_KEY (conftest pops it).
    The token must stay unstamped so the user is retried once a key is live."""
    uid, _ = await _seed_inactive_user(age=timedelta(hours=8))

    async with session_scope() as s:
        await run_activation_nudge_drip(s)

    assert await _drip_state(uid) == set()


@pytest.mark.asyncio
async def test_governor_blocks_nudge_when_another_flow_already_emailed(
    monkeypatch,
):
    """END-TO-END cross-flow cap — the reason the governor exists.

    One user is eligible for BOTH the 14-day re-engagement drip and (by
    construction) an activation nudge. With one shared governor threaded
    through both, exactly one email goes out.
    """
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    now = datetime.now(UTC)
    # Dormant long enough for the re14 window (last_seen_at 15 days ago),
    # signed up well before that so the timeline is coherent.
    uid, _ = await _seed_inactive_user(
        age=timedelta(days=40),
        last_seen_at=now - timedelta(days=15),
    )
    governor = FrequencyGovernor(ledger=SendLedger())
    async with session_scope() as s:
        await run_re_engagement_drip(s, governor=governor)

    assert "re14" in await _drip_state(uid)

    # The re-engagement send consumed this user's budget; a nudge now is
    # refused by the governor even though its own token is unstamped.
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert governor.allows(u, SendClass.LIFECYCLE, token="act_ask48h") is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. RULE 7 + RULE 6 — asserted on the RENDERED output
# ═══════════════════════════════════════════════════════════════════════════

# Phrasings that report how a user's securities MOVED or performed, plus the
# FOMO framings that are performance claims in disguise. A "missed setup" is
# only worth regretting because of the return it implies, which is exactly why
# "what you missed" belongs on this list and not in a template.
_PERFORMANCE_LANGUAGE = [
    "your watchlist is up",
    "your watchlist is down",
    "your tickers are up",
    "your tickers are down",
    "your best performer",
    "your top performer",
    "your worst performer",
    "would have caught",
    "you'd have caught",
    "what you missed",
    "missed setups",
    "missed out on",
    "since you added",
    "gained",
    "outperform",
    "beat the market",
    "returned",
    "% return",
    "p&l",
    "profit",
]

# Rule 6 — manufactured urgency. The ONLY permitted time statement is a
# factual note about the user's own real trial expiry.
_URGENCY_LANGUAGE = [
    "countdown",
    "act now",
    "hurry",
    "last chance",
    "don't miss out",
    "expires in",
    "only a few",
    "spots left",
    "limited time",
    "price goes up",
]

# Every template in the activation series, including the two milestone nudges
# that pre-date this work — the cap counts all four against one budget, so all
# four are held to the same content rules.
_ACTIVATION_TEMPLATES = [
    ("first_scan", lambda: render_activation_first_scan_email("Sam")),
    ("ask", lambda: render_activation_ask_email("Sam")),
    ("watchlist", lambda: render_activation_watchlist_email("Sam")),
    ("alert", lambda: render_activation_alert_email("Sam")),
]


@pytest.mark.parametrize(
    "name,render", _ACTIVATION_TEMPLATES, ids=[t[0] for t in _ACTIVATION_TEMPLATES],
)
def test_activation_templates_emit_no_ticker_performance_language(name, render):
    """RULE 7. A 1:1 message to a named person about how their self-selected
    securities performed is the worst-case fact pattern for the personal-advice
    test. Asserted on rendered HTML — that is what reaches the inbox."""
    html = render().lower()
    for phrase in _PERFORMANCE_LANGUAGE:
        assert phrase not in html, f"{name}: Rule 7 violation — {phrase!r}"


@pytest.mark.parametrize(
    "name,render", _ACTIVATION_TEMPLATES, ids=[t[0] for t in _ACTIVATION_TEMPLATES],
)
def test_activation_templates_carry_no_manufactured_urgency(name, render):
    """RULE 6."""
    html = render().lower()
    for phrase in _URGENCY_LANGUAGE:
        assert phrase not in html, f"{name}: Rule 6 violation — {phrase!r}"


@pytest.mark.parametrize(
    "name,render", _ACTIVATION_TEMPLATES, ids=[t[0] for t in _ACTIVATION_TEMPLATES],
)
def test_activation_templates_name_no_specific_securities(name, render):
    """Rule 2's structural companion: a template that never names a ticker
    cannot templatise an evaluative adjective onto one."""
    html = render()
    for ticker in ("AAPL", "TSLA", "NVDA", "SPY"):
        assert ticker not in html, f"{name}: names a security — {ticker}"


def test_trial_note_is_factual_and_not_a_billing_event():
    """Rule 6's one permitted exception. The trial takes no card, so the note
    must not read as a charge, a renewal, or a lapse into billing."""
    ends = datetime(2026, 8, 1, tzinfo=UTC)
    html = render_activation_first_scan_email("Sam", trial_ends_at=ends)

    assert "1 Aug 2026" in html
    assert "no card on file" in html.lower()

    lowered = html.lower()
    for phrase in ("you'll be charged", "will be billed", "auto-renew",
                   "payment due", "card will be charged"):
        assert phrase not in lowered, f"trial note reads as billing — {phrase!r}"


def test_trial_note_is_omitted_for_users_without_a_trial():
    html = render_activation_first_scan_email("Sam", trial_ends_at=None)
    assert "trial runs to" not in html.lower()


def test_ask_email_collects_no_suitability_data():
    """Rule 8. The 48h message invites a reply — which makes it a collection
    surface. It must ask about the PRODUCT, never about the reader's capital,
    holdings, risk tolerance, goals or experience."""
    html = render_activation_ask_email("Sam").lower()
    for phrase in ("portfolio size", "how much capital", "net worth",
                   "risk tolerance", "investment goals", "experience level",
                   "how much do you", "what do you trade", "account size"):
        assert phrase not in html, f"Rule 8 violation — {phrase!r}"


def test_ask_email_actually_asks_a_question_and_invites_a_reply():
    """The founder wants conversations — pin the intent so a later 'tighten
    the CTA' edit can't quietly turn this back into a pitch."""
    html = render_activation_ask_email("Sam")
    assert "?" in html
    assert "reply" in html.lower()
