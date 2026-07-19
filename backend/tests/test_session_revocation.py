"""Regression guards for three verified auth findings.

All three fail against the pre-fix code:

  1. Session JWTs were unrevocable. verify_session_token checked only the
     signature, exp and purpose — no DB access — so a cookie captured before a
     password reset kept working for the rest of its 30-day life. The
     "if this wasn't you" receipt email pointed at a recovery path that
     recovered nothing.
  2. TOTP codes were replayable. verify_totp used valid_window=1 and recorded
     nothing, so one 6-digit code stayed acceptable for ~90s and could be
     submitted repeatedly — including by someone who watched the real owner
     sign in with it.
  3. Recovery codes were 40 bits behind an unsalted single-round sha256, so
     one GPU pass over the shared keyspace cracked every row in the table at
     once.

Two of the fixes carry a compatibility promise that is asserted here as
hard as the fix itself:

  - a token with NO epoch claim must still verify (nobody is signed out by
    the deploy), and
  - a recovery code already stored as sha256 must still verify (nobody is
    locked out of their account).
"""
from __future__ import annotations

import asyncio
import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import MfaRecoveryCode, PasswordResetToken, User
from app.services.session import (
    SESSION_COOKIE,
    _session_secret,
    decode_session_token,
    hash_password,
    issue_session_token,
    session_epoch_matches,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mfa_mod(monkeypatch):
    """Import app.services.mfa even when pyotp/segno aren't installed.

    The module imports both at module scope and neither is in the local venv
    (they are in CI). The recovery-code helpers under test here don't touch
    either library — only the import line does — so stubbing lets the
    no-lockout guarantee be verified locally instead of only on CI. Same
    monkeypatch.setitem trick test_auth_hardening.py already uses.

    Tests that exercise real TOTP maths use pytest.importorskip instead.
    """
    import sys
    import types

    missing = [m for m in ("pyotp", "segno") if m not in sys.modules]
    for name in missing:
        try:
            __import__(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    # Drop any cached copy so the import below binds to whatever is in
    # sys.modules now, and drop it again afterwards so a module built against
    # a stub can never leak into a later test.
    monkeypatch.delitem(sys.modules, "app.services.mfa", raising=False)
    import app.services.mfa as mfa
    yield mfa
    sys.modules.pop("app.services.mfa", None)


async def _seed_user(**kw) -> User:
    kw.setdefault("password_hash", hash_password("OriginalPassword!2026"))
    user = User(
        id=f"u_{_uuid.uuid4().hex}",
        email=f"rev-{_uuid.uuid4().hex[:8]}@example.com",
        name="Rev", tier="free",
        **kw,
    )
    async with session_scope() as s:
        s.add(user)
        await s.commit()
        await s.refresh(user)
        s.expunge(user)
    return user


async def _reload(user_id: str) -> User:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        s.expunge(u)
        return u


# ── Finding 1: session revocation ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_minted_before_password_reset_stops_working(client):
    """THE fix. A reset must actually evict the attacker's captured cookie.

    Pre-fix this returned the user forever: reset_password wrote password_hash
    and nothing else, and verify_session_token never consulted the row.
    """
    user = await _seed_user()
    stolen = issue_session_token(user.id, user.session_epoch)

    # Sanity: the cookie works before the reset.
    async with client:
        before = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: stolen},
        )
        assert before.json()["user"] is not None, "fixture must start authenticated"

        token = f"reset_{_uuid.uuid4().hex}"
        async with session_scope() as s:
            s.add(PasswordResetToken(
                token=token, user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ))
            await s.commit()

        r = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "BrandNewPassword!2026"},
        )
        assert r.json() == {"status": "reset"}

        after = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: stolen},
        )
        me = await client.get("/api/me", cookies={SESSION_COOKIE: stolen})

    assert after.json()["user"] is None, "the pre-reset cookie must be dead"
    assert me.json().get("authenticated") is not True, (
        "the revoked cookie must not resolve on the main dependency either"
    )
    assert (await _reload(user.id)).session_epoch == 1


@pytest.mark.asyncio
async def test_token_with_no_epoch_claim_still_works(client):
    """The no-forced-logout guarantee.

    Every cookie in the wild at deploy time was minted without an "epoch"
    claim. Those must read as 0 and match the column's default of 0, or the
    deploy signs every logged-in customer out at once.
    """
    user = await _seed_user()

    # A token in exactly the pre-fix shape: no epoch claim at all.
    now = datetime.now(UTC)
    legacy = jwt.encode(
        {
            "sub": user.id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=30)).timestamp()),
            "nonce": "deadbeefdeadbeef",
        },
        _session_secret(),
        algorithm="HS256",
    )
    assert "epoch" not in jwt.decode(
        legacy, _session_secret(), algorithms=["HS256"]
    ), "fixture must exercise the legacy shape"

    assert decode_session_token(legacy) == (user.id, 0)
    assert session_epoch_matches(user.session_epoch, 0)

    async with client:
        r = await client.get("/api/auth/session", cookies={SESSION_COOKIE: legacy})
        me = await client.get("/api/me", cookies={SESSION_COOKIE: legacy})

    assert r.json()["user"]["id"] == user.id
    assert me.json().get("authenticated") is True


@pytest.mark.asyncio
async def test_session_issued_after_the_reset_works(client):
    """Revocation must not be a one-way door — signing in again has to work."""
    user = await _seed_user(session_epoch=4)
    fresh = issue_session_token(user.id, user.session_epoch)
    async with client:
        r = await client.get("/api/auth/session", cookies={SESSION_COOKIE: fresh})
    assert r.json()["user"]["id"] == user.id


@pytest.mark.asyncio
async def test_signin_mints_a_token_carrying_the_current_epoch(client):
    """A user whose epoch was already bumped must get a token on the NEW value,
    not a stale 0 that its own verify would reject."""
    password = "SigninPassword!2026"
    user = await _seed_user(password_hash=hash_password(password), session_epoch=7)
    async with client:
        r = await client.post(
            "/api/auth/signin", json={"email": user.email, "password": password},
        )
        assert r.status_code == 200, r.text
        cookie = r.cookies.get(SESSION_COOKIE)
        assert cookie, "signin must set a session cookie"
        assert decode_session_token(cookie) == (user.id, 7)

        follow = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: cookie},
        )
    assert follow.json()["user"]["id"] == user.id


@pytest.mark.asyncio
async def test_a_forged_higher_epoch_is_not_a_bypass():
    """The epoch lives inside the signed payload, so it can't be edited — but
    assert the comparison is equality rather than a >= that a tampered claim
    could satisfy."""
    assert session_epoch_matches(1, 1)
    assert not session_epoch_matches(1, 0)
    assert not session_epoch_matches(1, 2)
    assert session_epoch_matches(None, 0), "NULL column reads as 0"


# ── Finding 2: TOTP replay ────────────────────────────────────────────────────
#
# These need the real pyotp (not installed in the local venv, present in CI),
# so they skip locally and run in CI.


@pytest.mark.asyncio
async def test_the_same_totp_code_cannot_be_used_twice(client):
    """Pre-fix, a code observed via a phishing proxy or a shoulder-surf could be
    replayed for the rest of its ~90s window even after the owner had used it."""
    pyotp = pytest.importorskip("pyotp")
    from app.services.mfa import issue_mfa_token

    secret = pyotp.random_base32()
    user = await _seed_user(mfa_enabled=True, totp_secret=secret)
    code = pyotp.TOTP(secret).now()

    async with client:
        first = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": code},
        )
        assert first.status_code == 200, first.text

        replay = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": code},
        )

    assert replay.status_code == 401, "a spent code must never be accepted again"
    assert (await _reload(user.id)).totp_last_step is not None


@pytest.mark.asyncio
async def test_a_stale_read_cannot_respend_a_burned_totp_step(client, monkeypatch):
    """The losing side of a race must be refused by the DATABASE, not by the
    in-memory value the request happened to read.

    The threat model for the replay guard is a real-time phishing proxy — an
    adversary who controls timing and relays the victim's code at the same
    moment rather than politely afterwards. Both requests then read the
    pre-burn value, so a read-then-assign guard waves both through and one code
    yields two sessions.

    Racing two real HTTP calls does NOT reproduce this reliably (I tried: the
    naive implementation passes such a test, because the requests don't
    actually interleave across the critical section). So this reconstructs the
    losing racer's exact state deterministically: the row has already been
    advanced to step N by the winner, while THIS request's verifier still
    reports N — precisely what a stale read looks like. Only the conditional
    UPDATE catches it; against a plain assignment this test returns 200.
    """
    pytest.importorskip("pyotp")
    import app.services.mfa as mfa_module
    from app.services.mfa import issue_mfa_token

    burned = 1000
    user = await _seed_user(mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == user.id))).scalar_one()
        row.totp_last_step = burned  # the winning racer, already committed
        await s.commit()

    # The verifier is imported inside the handler, so patch it at its source.
    monkeypatch.setattr(
        mfa_module, "verify_totp_step", lambda secret, code, last_step=None: burned,
    )

    async with client:
        r = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": "123456"},
        )

    assert r.status_code == 401, "a step already spent by another request must lose"
    assert SESSION_COOKIE not in r.cookies, "the loser must not receive a session"
    assert (await _reload(user.id)).totp_last_step == burned


@pytest.mark.asyncio
async def test_a_legitimate_first_totp_login_succeeds(client):
    """The no-lockout half of the replay fix.

    totp_last_step is NULL for every existing 2FA user. NULL means "never
    completed a challenge" and must NOT be read as step 0, which would be a
    live comparison that rejects a genuine first login.
    """
    pyotp = pytest.importorskip("pyotp")
    from app.services.mfa import issue_mfa_token

    secret = pyotp.random_base32()
    user = await _seed_user(mfa_enabled=True, totp_secret=secret)
    assert user.totp_last_step is None, "fixture must start with the NULL case"

    async with client:
        r = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": pyotp.TOTP(secret).now()},
        )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == user.id


@pytest.fixture
def fake_totp_mfa(monkeypatch):
    """app.services.mfa bound to a deterministic fake pyotp.

    Installed unconditionally (unlike mfa_mod) so the replay guard's step
    arithmetic is exercised identically on CI and on a laptop without pyotp.
    The fake pins "now" to step 1000 and gives every step a distinct code, so
    the assertions are about the guard, not about clocks.
    """
    import sys
    import types

    class _FakeTOTP:
        NOW_STEP = 1000

        def __init__(self, secret: str) -> None:
            self.secret = secret

        def timecode(self, _when) -> int:
            return self.NOW_STEP

        def at(self, _when, counter_offset: int = 0) -> str:
            return f"{self.NOW_STEP + counter_offset:06d}"

    stub = types.ModuleType("pyotp")
    stub.TOTP = _FakeTOTP
    stub.random_base32 = lambda: "JBSWY3DPEHPK3PXP"
    monkeypatch.setitem(sys.modules, "pyotp", stub)
    if "segno" not in sys.modules:
        try:
            __import__("segno")
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, "segno", types.ModuleType("segno"))

    monkeypatch.delitem(sys.modules, "app.services.mfa", raising=False)
    import app.services.mfa as mfa
    yield mfa, _FakeTOTP
    sys.modules.pop("app.services.mfa", None)


def test_verify_totp_step_refuses_a_step_that_was_already_spent(fake_totp_mfa):
    """The guard itself: a code is only accepted while its step is unspent.

    Pre-fix there was no last_step parameter at all — pyotp.verify(...) said
    yes to every submission of the same code inside its ~90s window.
    """
    mfa, fake = fake_totp_mfa
    now_code = f"{fake.NOW_STEP:06d}"
    prev_code = f"{fake.NOW_STEP - 1:06d}"

    # Never-used account: NULL, not 0. Both the current step and the skew
    # step behind it are live.
    assert mfa.verify_totp_step("S", now_code, None) == fake.NOW_STEP
    assert mfa.verify_totp_step("S", prev_code, None) == fake.NOW_STEP - 1

    # Once the current step is spent, that code is dead — and so is every
    # earlier one still inside the window.
    assert mfa.verify_totp_step("S", now_code, fake.NOW_STEP) is None
    assert mfa.verify_totp_step("S", prev_code, fake.NOW_STEP) is None
    assert mfa.verify_totp_step("S", now_code, fake.NOW_STEP + 1) is None

    # Spending the SKEW step must not burn the current one — a user whose
    # phone runs slow has to be able to log in again on the next code.
    assert mfa.verify_totp_step("S", now_code, fake.NOW_STEP - 1) == fake.NOW_STEP

    # The +1 step is still reachable for a fast clock.
    assert mfa.verify_totp_step(
        "S", f"{fake.NOW_STEP + 1:06d}", fake.NOW_STEP,
    ) == fake.NOW_STEP + 1

    # Non-codes stay rejected, and nothing raises.
    assert mfa.verify_totp_step("S", "abcdef", None) is None
    assert mfa.verify_totp_step("", now_code, None) is None
    assert mfa.verify_totp_step("S", "", None) is None


@pytest.mark.asyncio
async def test_enabling_2fa_revokes_old_sessions_but_not_the_caller(
    client, fake_totp_mfa,
):
    """Hardening the account evicts sessions that predate the hardening — and
    must NOT log out the person doing the hardening.

    Without the re-issued cookie the user would be signed out of the settings
    page mid-flow, which is why the handler sets a fresh one on the new epoch.
    """
    _mfa, fake = fake_totp_mfa
    user = await _seed_user(totp_secret="JBSWY3DPEHPK3PXP", mfa_enabled=False)
    old_cookie = issue_session_token(user.id, user.session_epoch)

    async with client:
        r = await client.post(
            "/api/me/2fa/enable",
            json={"code": f"{fake.NOW_STEP:06d}"},
            cookies={SESSION_COOKIE: old_cookie},
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["recovery_codes"]) == 10

        new_cookie = r.cookies.get(SESSION_COOKIE)
        assert new_cookie, "the caller must be re-cookied, not logged out"
        assert new_cookie != old_cookie

        stale = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: old_cookie},
        )
        fresh = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: new_cookie},
        )

    assert stale.json()["user"] is None, "pre-2FA cookies must stop working"
    assert fresh.json()["user"]["id"] == user.id
    reloaded = await _reload(user.id)
    assert reloaded.session_epoch == 1
    assert reloaded.mfa_enabled is True
    # Enrolment must not burn the step — the code is still on screen and the
    # user may be about to sign in with it on another device.
    assert reloaded.totp_last_step is None


def test_verify_totp_step_returns_the_step_and_refuses_spent_ones():
    """Unit-level: the window still absorbs clock skew, but only forward."""
    pyotp = pytest.importorskip("pyotp")
    from app.services.mfa import verify_totp_step

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    now = datetime.now(UTC)
    step = totp.timecode(now)

    assert verify_totp_step(secret, totp.now(), None) == step
    # Already spent → refused, even though it's still inside the ±1 window.
    assert verify_totp_step(secret, totp.now(), step) is None
    assert verify_totp_step(secret, totp.now(), step + 5) is None
    # A code from the previous step is accepted for skew when nothing is spent,
    # and refused once the current step has been.
    prev = totp.at(now, counter_offset=-1)
    assert verify_totp_step(secret, prev, None) == step - 1
    assert verify_totp_step(secret, prev, step) is None
    assert verify_totp_step(secret, "000000", None) in (None, step)


# ── Finding 3: recovery-code hashing ──────────────────────────────────────────


def test_new_recovery_codes_are_80_bits_and_bcrypt_hashed(mfa_mod):
    RECOVERY_CODE_BYTES = mfa_mod.RECOVERY_CODE_BYTES
    generate_recovery_codes = mfa_mod.generate_recovery_codes
    hash_recovery_code = mfa_mod.hash_recovery_code
    normalise_recovery_code = mfa_mod.normalise_recovery_code
    verify_recovery_code = mfa_mod.verify_recovery_code

    assert RECOVERY_CODE_BYTES * 8 >= 80, "entropy floor"
    codes = generate_recovery_codes(5)
    assert len(set(codes)) == 5
    for c in codes:
        assert len(normalise_recovery_code(c)) == RECOVERY_CODE_BYTES * 2

    stored = hash_recovery_code(codes[0])
    assert stored.startswith("$2"), "must be bcrypt, not a hex digest"
    assert len(stored) <= 64, "must fit mfa_recovery_codes.code_hash (String(64))"
    # Salted: the same code hashed twice must not collide, which is exactly
    # what defeats the single-pass table-wide GPU crack.
    assert hash_recovery_code(codes[0]) != stored
    assert verify_recovery_code(codes[0], stored)
    assert not verify_recovery_code(codes[1], stored)
    # Dashes and case are still optional for the user.
    assert verify_recovery_code(codes[0].replace("-", "").upper(), stored)


def test_an_existing_sha256_recovery_code_still_verifies(mfa_mod):
    """The no-lockout guarantee. Rows minted before this change are unsalted
    sha256 and MUST keep working, or every 2FA user's printed backup codes
    become waste paper."""
    legacy_sha256_recovery_hash = mfa_mod.legacy_sha256_recovery_hash
    verify_recovery_code = mfa_mod.verify_recovery_code

    legacy_plaintext = "a1b2c-d3e4f"  # the old 40-bit format
    legacy_hash = legacy_sha256_recovery_hash(legacy_plaintext)
    assert len(legacy_hash) == 64

    assert verify_recovery_code(legacy_plaintext, legacy_hash)
    assert verify_recovery_code("A1B2CD3E4F", legacy_hash), "normalisation holds"
    assert not verify_recovery_code("00000-00000", legacy_hash)


@pytest.mark.asyncio
async def test_a_new_recovery_code_is_single_use_end_to_end(client, fake_totp_mfa):
    """The bcrypt row has to be findable without an indexed hash lookup, and
    consumed on first use.

    Runs on the fake TOTP so it exercises the handler everywhere: the submitted
    code is never a valid TOTP, so control falls through to the recovery scan —
    which is the branch that used to be an indexed `code_hash == sha256(code)`
    equality match and cannot be one any more.
    """
    mfa, _fake = fake_totp_mfa
    generate_recovery_codes = mfa.generate_recovery_codes
    hash_recovery_code = mfa.hash_recovery_code
    issue_mfa_token = mfa.issue_mfa_token

    user = await _seed_user(mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    codes = generate_recovery_codes()
    async with session_scope() as s:
        for c in codes:
            s.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(c)))
        await s.commit()

    # Deliberately NOT the first row — proves the loop scans past non-matches.
    chosen = codes[6]
    async with client:
        first = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": chosen},
        )
        assert first.status_code == 200, first.text

        reuse = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": chosen},
        )
    assert reuse.status_code == 401, "recovery codes are single-use"

    async with session_scope() as s:
        rows = (await s.execute(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
        )).scalars().all()
    assert sum(1 for r in rows if r.used_at is not None) == 1


@pytest.mark.asyncio
async def test_a_legacy_sha256_recovery_row_still_signs_the_user_in(
    client, fake_totp_mfa,
):
    """End-to-end version of the no-lockout guarantee, through the handler that
    used to do an indexed `code_hash == sha256(code)` match.

    This is the one that decides whether shipping the bcrypt change locks
    existing 2FA users out of their own accounts.
    """
    mfa, _fake = fake_totp_mfa
    issue_mfa_token = mfa.issue_mfa_token
    legacy_sha256_recovery_hash = mfa.legacy_sha256_recovery_hash

    user = await _seed_user(mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    legacy_plaintext = "9f8e7-6d5c4"
    async with session_scope() as s:
        s.add(MfaRecoveryCode(
            user_id=user.id, code_hash=legacy_sha256_recovery_hash(legacy_plaintext),
        ))
        await s.commit()

    async with client:
        r = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": issue_mfa_token(user.id), "code": legacy_plaintext},
        )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == user.id
