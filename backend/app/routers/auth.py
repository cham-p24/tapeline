"""Native auth: signup, signin, signout, session me."""
from __future__ import annotations

import asyncio
import logging
import secrets
import string
import time
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.bot_protection import (
    is_disposable_email,
    is_honeypot_tripped,
    verify_turnstile,
)
from app.services.rate_limit import client_ip as resolve_client_ip
from app.services.rate_limit import limit_auth, limiter
from app.services.session import (
    SESSION_COOKIE,
    decode_session_token,
    hash_password,
    issue_session_token,
    session_cookie_kwargs,
    session_epoch_matches,
    verify_password,
)
from app.services.tier import must_add_card
from app.services.trial_abuse import normalise_email

logger = logging.getLogger(__name__)
router = APIRouter()

# ---- Referral-credit anti-abuse ---------------------------------------------
#
# A referral credit is a free month that gets minted into a REAL 100%-off
# Stripe coupon at the holder's next checkout (services/billing.
# create_checkout_session, duration_in_months=N). Every credit is therefore
# real money, so the grant is guarded twice:
#
#   1. **Not granted on signup.** A raw signup is free to manufacture, so
#      crediting the referrer per signup let anyone farm unlimited free months
#      by mass-registering referees. The referrer is credited only once the
#      referee VERIFIES their email (see _consume_verification below), which
#      forces the abuser to control a distinct, deliverable, non-disposable
#      inbox per referral instead of typing throwaway addresses into the form.
#   2. **Capped outstanding balance.** A referrer stops accruing once they
#      hold MAX_REFERRAL_CREDIT_MONTHS unspent months, so a single minted
#      coupon can never exceed that many free months. Redeeming credits frees
#      the balance up again, so a genuine power-referrer isn't permanently
#      capped — they just can't bank an unbounded pile.
#
# Conservative on purpose. Tune the constant here; nothing else reads it.
MAX_REFERRAL_CREDIT_MONTHS = 5


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    name: str | None = Field(None, max_length=120)
    ref: str | None = Field(None, max_length=20)  # referral code from URL
    # Honeypot — must stay empty. Bots fill all visible-looking fields.
    # The frontend renders this offscreen so humans never see it.
    company: str | None = Field(None, max_length=200)
    # Cloudflare Turnstile token. Verified server-side if Turnstile is configured;
    # ignored otherwise (dev mode pass-through).
    turnstile_token: str | None = Field(None, max_length=2048)
    # Lightweight device fingerprint from frontend (lib/fingerprint.ts). Used
    # for the same-device retrial check; empty/missing falls back to the
    # other defences (honeypot, Turnstile, IP cap, email normalisation).
    device_fingerprint: str | None = Field(None, max_length=64)
    # Marketing-attribution UTMs captured by lib/utm.ts on the landing
    # visit (localStorage, 30-day TTL) and forwarded here. Written once
    # to the User row; never updated. Distinct from `referral_source`
    # (self-reported during onboarding) — this is ground-truth channel
    # attribution.
    utm_source: str | None = Field(None, max_length=80)
    utm_medium: str | None = Field(None, max_length=80)
    utm_campaign: str | None = Field(None, max_length=120)
    utm_term: str | None = Field(None, max_length=120)
    utm_content: str | None = Field(None, max_length=120)
    # Google Ads click IDs captured by lib/utm.ts on the landing visit and
    # forwarded here (same mechanism as utm_*). Written once at signup to the
    # signup_gclid/gbraid/wbraid columns, never updated. Stored so the
    # founder-gated offline-conversion upload to Google has the click ID
    # available. Only paid Google traffic carries these.
    gclid: str | None = Field(None, max_length=200)
    gbraid: str | None = Field(None, max_length=200)
    wbraid: str | None = Field(None, max_length=200)
    # Meta click ID — same capture/forward mechanism as gclid above, for the
    # other paid-click platform. Written once to users.signup_fbclid. The RAW
    # param, not the `fb.1.<ts>.<fbclid>` wire format; meta_capi.fbc_value()
    # builds that. Without it Meta's match quality is capped and there is no
    # honest way to count Meta payers (the 14-day trial puts every first
    # charge outside Meta's 7-day click window) — see migration 0053.
    fbclid: str | None = Field(None, max_length=200)
    # The `_fbp` first-party cookie the Meta pixel writes on the landing
    # visit, read from document.cookie at submit. NOT persisted — there is no
    # column and no second use for it: it is forwarded straight onto the
    # CompleteRegistration event as the other unhashed identifier Meta
    # matches on. Absent whenever the pixel was blocked or never ran.
    fbp: str | None = Field(None, max_length=200)
    # Self-reported attribution — the OPTIONAL free-text "How did you hear
    # about us?" answer (gap G2). Written to users.referral_source, the same
    # column the onboarding survey used to own.
    #
    # Why free text and not a dropdown: a fixed option list can only ever
    # count channels we already thought of, and this field exists precisely
    # to surface the ones we cannot see — AI assistants and dark social
    # arrive with no referrer and no UTM, so a self-report is the ONLY
    # instrument that will ever credit them (§2.3).
    #
    # NOT a suitability input. It records where someone heard of us; it never
    # touches capital, holdings, risk tolerance, goals or experience, and it
    # must never change which securities or factor weightings a user is
    # shown. Keep it that way — see docs/COMPLIANCE_COPY_RULES.md Rule 8.
    # max_length is deliberately WIDER than the 40-char column so a chatty
    # answer truncates instead of 422-ing the signup; attribution must never
    # be able to block an account being created.
    referral_source: str | None = Field(None, max_length=400)
    # First-touch EXTERNAL referrer HOSTNAME captured by lib/utm.ts on the
    # landing visit (same localStorage mechanism as utm_*) and forwarded
    # here. AI-assistant referrals (Copilot/ChatGPT/Perplexity) carry no
    # utm_* params, so document.referrer's host is the only channel trace.
    # Hostname only — never path/query. Written once at signup, never
    # updated.
    signup_referrer_host: str | None = Field(None, max_length=100)
    # First-touch LANDING PATH on our own site, captured by lib/utm.ts at
    # landing and forwarded here — e.g. "/glossary/rsi". Answers which of our
    # ~4,750 SEO pages earned the signup, which the channel fields above
    # can't. Path only; any query/hash is stripped by _normalise_landing_path
    # below (defence in depth — the client strips it too). max_length is
    # deliberately WIDER than the 200-char column so an unexpectedly long
    # path truncates instead of 422-ing the whole signup — attribution must
    # never be able to block an account being created.
    signup_landing_path: str | None = Field(None, max_length=500)
    # Signup-form email consent — BOTH default False and the form renders
    # both boxes unchecked (explicit opt-in only; never pre-ticked).
    #   marketing_opt_in    → users.marketing_opt_in: consent for the weekly
    #                         market digest. Previously capturable only via
    #                         the onboarding checkbox, which a day-1 bouncer
    #                         never saw — this is the placement fix.
    #   daily_top10_opt_in  → enrols the email in the Daily Top 10 digest via
    #                         the same newsletter subscribe() service the
    #                         public footer box uses (dedupe, welcome email,
    #                         one-click unsubscribe token all reused).
    marketing_opt_in: bool = False
    daily_top10_opt_in: bool = False


class SigninBody(BaseModel):
    email: EmailStr
    password: str


_LANDING_PATH_MAX = 200  # matches users.signup_landing_path
_REFERRAL_SOURCE_MAX = 40  # matches users.referral_source


def _normalise_referral_source(raw: str | None) -> str | None:
    """Clean the free-text "How did you hear about us?" answer, or None.

    The column (users.referral_source, String(40)) predates this field: it
    used to hold slugs from the onboarding survey's dropdown ("reddit",
    "ai_copilot"). Free text now lands in the same column so one GROUP BY
    reads both eras, which means cleaning it before it gets there:
      - collapse all whitespace, so "  reddit \n r/stocks " and
        "reddit r/stocks" aggregate as one row rather than two
      - drop control characters (a hostile client can post anything)
      - truncate to the column width rather than rejecting — a long answer is
        still a usable answer, and attribution must never fail a signup

    Never raises, for the same reason.
    """
    if not raw:
        return None
    try:
        cleaned = " ".join(
            raw.replace("\x7f", " ").split()
        )
        cleaned = "".join(c for c in cleaned if ord(c) >= 0x20)
        cleaned = cleaned.strip()[:_REFERRAL_SOURCE_MAX].strip()
        return cleaned or None
    except Exception:
        return None


def _normalise_landing_path(raw: str | None) -> str | None:
    """Normalise the client-supplied first-touch landing path, or None.

    Contract (mirrors lib/utm.ts:normaliseLandingPath so client and server
    agree on the bucket a page falls into):
      - strip anything from the first `?` or `#` — the query string and hash
        can carry search terms or identifiers, and they explode the
        cardinality of the aggregation this column exists to feed
      - lowercase, so /Glossary/RSI and /glossary/rsi are one row
      - drop a trailing slash (root "/" kept as-is)
      - reject anything that isn't a rooted, site-relative path. "//host" is
        protocol-relative (an external URL) — a spoofed payload must not get
        someone else's domain into our column
      - truncate to the column width

    Never raises: attribution must not be able to fail a signup.
    """
    if not raw:
        return None
    try:
        path = raw.strip()
        for sep in ("?", "#"):
            idx = path.find(sep)
            if idx >= 0:
                path = path[:idx]
        path = path.lower()
        if not path.startswith("/") or path.startswith("//"):
            return None
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        path = path[:_LANDING_PATH_MAX]
        return path or None
    except Exception:
        return None


def _user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "tier": u.tier,
        "is_admin": u.is_admin,
        "is_lifetime": u.is_lifetime,
        "trial_ends_at": u.trial_ends_at.isoformat() if u.trial_ends_at else None,
        "referral_code": u.referral_code,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        # Drives the post-signup redirect — frontend sends users with a NULL
        # onboarding_completed_at through /app/onboarding before /app/scanner.
        "onboarding_completed_at": (
            u.onboarding_completed_at.isoformat() if u.onboarding_completed_at else None
        ),
        # Null until the user clicks the link in their verification email
        # (or OAuth provider verified at signup). Frontend uses this to
        # render the "Verify your email" banner in /app/*.
        "email_verified_at": (
            u.email_verified_at.isoformat() if u.email_verified_at else None
        ),
        # Drives the card wall at /app/start. This MUST ship on the session
        # payload, not only on /api/me: UserContext boots from
        # GET /api/auth/session, and without the field here the doorman in
        # app/layout.tsx reads undefined and the wall never fires at all.
        # Computed server-side from the single dated CARD_GATE_START constant so
        # the browser never re-derives who is grandfathered — see tier.py.
        "must_add_card": must_add_card(u),
    }


def _generate_referral_code() -> str:
    """Short, human-readable code. Collision chance <1 per 10k users."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude 0/O, 1/I/L to reduce confusion
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "").replace("L", "")
    return "".join(secrets.choice(alphabet) for _ in range(8))


@router.post("/signup", dependencies=[Depends(limit_auth)])
async def signup(
    body: SignupBody,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    # ---- Bot/abuse checks (run before any expensive work) -------------------
    if is_honeypot_tripped(body.company):
        # Bot tripped the honeypot field. Return a fake-success response so the
        # bot can't probe whether the honeypot exists, but don't actually create
        # the account or set a session cookie.
        logger.warning("auth.honeypot_tripped email=%s", body.email)
        return {"user": {
            "id": "u_blocked", "email": body.email, "name": None, "tier": "free",
            "is_admin": False, "is_lifetime": False, "trial_ends_at": None,
            "referral_code": None, "created_at": None,
        }}

    # Normalise the email so dot/+tag permutations of the same Gmail / Outlook
    # inbox can't mint multiple trials. See services/trial_abuse.normalise_email.
    from app.services.trial_abuse import (
        fingerprint_allowed,
        normalise_email,
        record_fingerprint_signup,
        record_signup,
        signup_allowed,
    )
    email = normalise_email(body.email)
    if is_disposable_email(email):
        logger.warning("auth.disposable_email_blocked email=%s", email)
        raise HTTPException(400, "This email provider isn't supported. Please use a regular email address.")

    # Real client IP behind Fly's edge proxy. request.client.host is the proxy's
    # internal peer address — IDENTICAL for every external visitor — so using it
    # would collapse the per-IP signup cap below into a GLOBAL 3-per-24h limit
    # (after any 3 site-wide signups in a window, every visitor 429s). Use the
    # shared resolver, which prefers Cloudflare's un-forgeable cf-connecting-ip
    # header and falls back to the leftmost X-Forwarded-For entry exactly as
    # services/rate_limit already does for limit_auth.
    client_ip = resolve_client_ip(request)
    if not await verify_turnstile(body.turnstile_token, client_ip):
        raise HTTPException(400, "Bot challenge failed. Please refresh and try again.")

    # IP-based 24h signup cap. Stops drive-by trial farming where one host
    # creates dozens of accounts via Gmail tag permutations or scripts.
    if not signup_allowed(client_ip):
        logger.warning("auth.ip_rate_limited ip=%s email=%s", client_ip, email)
        raise HTTPException(
            429,
            "Too many signups from this network in the last 24 hours. "
            "Please try again tomorrow or contact support@tapeline.io if you "
            "share an IP with several legitimate users.",
        )

    # Device-fingerprint check — same browser can't mint MANY trials in a
    # 30-day window. Tolerant cap (5, not the default 1): the homemade 8-byte
    # fingerprint (lib/fingerprint.ts) collides across same-model phones,
    # corporate Chrome fleets, and canvas-blocking privacy browsers, so a hard
    # max=1 returned a false-positive 409 to legitimate paid-traffic cohorts
    # (and blocked the founder from testing the funnel twice). Email-uniqueness
    # + the per-IP cap + Turnstile remain the primary abuse defences. Generic
    # 409 message so we don't reveal which signal tripped.
    if not fingerprint_allowed(body.device_fingerprint, max_in_window=5):
        logger.warning("auth.fingerprint_rate_limited fp=%s email=%s",
                       (body.device_fingerprint or "")[:8], email)
        raise HTTPException(
            409,
            "An account with these details already exists. "
            "If you're trying to recover access, use Sign in or Reset password.",
        )

    # ---- Normal signup path -------------------------------------------------
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "An account already exists for that email")

    try:
        pw = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Resolve referral code -> referring user. A valid ref earns BOTH parties
    # one month of free Premium, applied at the next paid checkout via a
    # one-shot Stripe coupon. See services/billing.create_checkout_session.
    # The REFEREE's month lands here at signup (it's capped at one per account
    # and only pays out if they actually subscribe); the REFERRER's is deferred
    # until this account verifies its email — see MAX_REFERRAL_CREDIT_MONTHS.
    referrer: User | None = None
    if body.ref:
        ref_q = await session.execute(select(User).where(User.referral_code == body.ref.upper()))
        referrer = ref_q.scalar_one_or_none()
    referred_by_id = referrer.id if referrer else None

    # NO trial is granted here. Creating an account is email + password only,
    # and it lands on FREE. From tier.CARD_GATE_START a NEW free account still
    # hits the card wall at first sign-in (services/tier.must_add_card); only
    # accounts created before that date are card-free forever. The
    # /free-stock-scanner-no-credit-card page was rewritten for exactly this —
    # it now tells a true story about the PUBLIC record (scorecard, daily
    # picks, exports, ticker pages), which needs no account and no card.
    #
    # The 14-day Premium trial is now card-required: the user starts it
    # deliberately from POST /api/billing/checkout {"start_trial": true}, which
    # opens a Stripe Checkout that charges $0 today and states the exact
    # first-charge date. tier/trial_ends_at/trial_started_at are then written by
    # the `trialing` subscription webhook (routers/webhooks.py) from the
    # SUBSCRIPTION's own trial_end, so the date we show is the date Stripe will
    # actually bill. Declining leaves the account exactly as created here.
    #
    # Why the old auto-grant went: every account got Premium for 14 days with
    # no card, so no account has ever produced a payment signal.

    # Generate a unique referral code for the new user
    ref_code = _generate_referral_code()
    for _ in range(5):  # retry on unlikely collision
        conflict = await session.execute(select(User).where(User.referral_code == ref_code))
        if conflict.scalar_one_or_none() is None:
            break
        ref_code = _generate_referral_code()

    user = User(
        id=f"u_{uuid.uuid4().hex}",
        email=email,
        name=(body.name or "").strip() or None,
        # FREE, no card on file, and no trial. See the block above: from
        # tier.CARD_GATE_START this row still meets the card wall at first
        # sign-in, and the Premium trial is opt-in and card-required, stamped
        # by the subscription webhook — never here.
        tier="free",
        password_hash=pw,
        trial_ends_at=None,
        referral_code=ref_code,
        referred_by=referred_by_id,
        referral_credit_months=1 if referrer else 0,
        # Marketing attribution — forwarded by the frontend from the user's
        # original landing query string. Written once at signup, never
        # updated. Stay nullable so direct/un-tagged traffic doesn't blow up.
        signup_utm_source=(body.utm_source or None),
        signup_utm_medium=(body.utm_medium or None),
        signup_utm_campaign=(body.utm_campaign or None),
        signup_utm_term=(body.utm_term or None),
        signup_utm_content=(body.utm_content or None),
        # Google Ads click IDs — same write-once-at-signup contract as the
        # UTMs above. Available for the founder-gated offline-conversion
        # upload to Google (value-based bidding). See models/user.py.
        signup_gclid=(body.gclid or None),
        signup_gbraid=(body.gbraid or None),
        signup_wbraid=(body.wbraid or None),
        # Meta click ID — same write-once contract. Raw fbclid; the
        # `fb.1.<ts>.<fbclid>` wire value is derived at send time.
        signup_fbclid=(body.fbclid or None),
        # Self-reported "How did you hear about us?" (optional, free text).
        # The only instrument that can credit AI-assistant and dark-social
        # referrals, both of which arrive with no referrer and no UTM.
        referral_source=_normalise_referral_source(body.referral_source),
        # First-touch external referrer host — the only attribution trace
        # AI-assistant referrals leave (no utm_* params). Hostname only.
        signup_referrer_host=(body.signup_referrer_host or None),
        # First-touch landing path on our own site — which PAGE earned the
        # signup, complementing the channel columns above. Normalised +
        # validated here (path only, no query/hash, must be rooted); a
        # rejected value stores NULL rather than failing the signup.
        signup_landing_path=_normalise_landing_path(body.signup_landing_path),
        # Weekly-digest consent from the signup form's unchecked-by-default
        # checkbox. False (no tick) writes the column default — nothing is
        # inferred from silence.
        marketing_opt_in=bool(body.marketing_opt_in),
    )
    session.add(user)
    # NOTE: the referrer is deliberately NOT credited here. Granting a free
    # month per signup made the balance farmable by anyone willing to submit
    # the form repeatedly. The credit is applied in _consume_verification once
    # this account proves control of its inbox.
    await session.commit()
    await session.refresh(user)

    # Consent→bit sync, mirroring the onboarding submit (routers/me.py):
    # weekly-digest consent also sets the WEEKLY_NEWSLETTER email_prefs bit so
    # /app/settings/email shows the toggle in the state the user just chose.
    # (Delivery double-gates on marketing_opt_in AND the bit — see
    # services/email.run_weekly_newsletter.) Done after the refresh above so
    # the column default has materialised and the OR can't clobber other bits.
    if user.marketing_opt_in:
        from app.services.email_prefs import EmailPref
        user.email_prefs = int(user.email_prefs or 0) | int(EmailPref.WEEKLY_NEWSLETTER)
        await session.commit()

    # Record the IP for the 24h sliding-window cap. Done AFTER the DB commit so
    # a failed signup (DB unavailable, transaction conflict) doesn't burn the
    # legitimate user's budget.
    record_signup(client_ip)
    record_fingerprint_signup(body.device_fingerprint)

    # Daily Top 10 enrolment — the signup form's second consent box. Reuses
    # the SAME subscribe() service the public footer capture box posts to, so
    # dedupe (already-subscribed no-op), the resubscribe flip, the welcome
    # email and the one-click unsubscribe token all come along for free.
    # Best-effort: a newsletter hiccup must never fail account creation.
    if body.daily_top10_opt_in:
        try:
            from app.services.newsletter import subscribe as newsletter_subscribe
            await newsletter_subscribe(
                session,
                email=user.email,
                source="signup",
                utm_source=body.utm_source,
                utm_medium=body.utm_medium,
                utm_campaign=body.utm_campaign,
                utm_term=body.utm_term,
                utm_content=body.utm_content,
            )
        except Exception:
            logger.exception(
                "auth.signup_daily_top10_subscribe_failed user=%s", user.id
            )

    # Real-time founder ping so a new signup / live trial never goes unnoticed.
    # Self-guarding + never raises (no-op if the Telegram channel isn't set).
    from app.services.telegram import notify_founder_new_signup

    await notify_founder_new_signup(
        email=user.email, tier=user.tier,
        trial_ends_at=user.trial_ends_at, source="email",
    )

    token = issue_session_token(user.id, user.session_epoch)
    response.set_cookie(value=token, **session_cookie_kwargs())
    logger.info("auth.signup user=%s referred_by=%s", user.id, referred_by_id or "none")

    # Server-side `CompleteRegistration` for Meta. Same reasoning as the GA4
    # sign_up beacon in routers/oauth.py: the client-side pixel is the only
    # other record, and this audience runs ad-blockers well above web average,
    # so a browser-only signup event under-counts real conversions — which is
    # precisely the signal an ad account would be optimising against.
    #
    # Why this event and not just StartTrial: since #536 the 14-day trial is a
    # SEPARATE, card-required step, so StartTrial is now genuinely scarce.
    # Meta's smart bidding wants ~50 events per ad set per week; at Tapeline's
    # volume only the free-account signup has any chance of approaching that.
    # Both are sent — which one a campaign OPTIMISES toward is a campaign
    # setting, not a code decision. See docs/META_GO_LIVE.md.
    #
    # Fire-and-forget, env-gated, never raises — a Meta hiccup must not cost
    # someone their account.
    try:
        from app.services import meta_capi

        # fbc/fbp ride along UNHASHED (meta_capi enforces that) — they are the
        # EMQ upgrade that costs no new PII. With only a hashed email +
        # hashed user id, match quality caps around 5-6, and this is the event
        # the campaign optimises toward, so it is the one whose match quality
        # the delivery model actually learns from.
        await meta_capi.track_complete_registration(
            user_id=user.id, email=user.email, method="email",
            fbc=meta_capi.fbc_value(user.signup_fbclid, user.created_at),
            fbp=(body.fbp or None),
        )
    except Exception:
        logger.exception("auth.meta_complete_registration_failed user=%s", user.id)

    # Day-0 email. Fire-and-forget — failures don't block signup.
    # send_email is a no-op if RESEND_API_KEY isn't set, so this is safe in dev.
    # Referred users get a credit-acknowledgement email instead of the standard
    # welcome — both carry the same "account is ready" framing, but the referral
    # version surfaces the earned bonus front-and-centre. (The credit is real
    # and unchanged by the card-required-trial move: it is minted as a Stripe
    # coupon at the user's next checkout, trial or paid.)
    # The referrer's "+1 month credited" note is NOT sent here: their credit
    # doesn't exist yet. It goes out from _consume_verification at the moment
    # the balance actually moves, so the email can't claim a credit that was
    # never granted.
    if referrer:
        try:
            from app.services.email import render_referral_referee_email, send_email
            await send_email(
                user.email,
                "Welcome to Tapeline — you've earned 1 free month of Premium",
                render_referral_referee_email(user.name or "trader", referrer.name),
            )
        except Exception:
            logger.exception("auth.referral_emails_failed user=%s referrer=%s",
                             user.id, referrer.id)
    else:
        try:
            from sqlalchemy import desc as _desc

            from app.models import Ticker
            from app.services.email import render_welcome_email, send_email
            from app.services.ticker_freshness import live_clauses

            # Freshness + data-quality floor — a new signup's first email should
            # show live, clean top picks, not stale ghost rows or corrupt
            # (score>100 / emoji-symbol / <2-factor) artifacts. (score IS NOT
            # NULL is part of the floor.) See app.services.ticker_freshness.
            _top_stmt = select(
                Ticker.symbol, Ticker.score, Ticker.signal, Ticker.reason
            )
            for _clause in await live_clauses(session):
                _top_stmt = _top_stmt.where(_clause)
            top_result = await session.execute(
                _top_stmt.order_by(_desc(Ticker.score)).limit(3)
            )
            picks = [
                {"symbol": r[0], "score": r[1], "signal": r[2], "reason": r[3]}
                for r in top_result.all()
            ]
            # Subject states what actually happened. Signup no longer starts a
            # trial, so the old "your trial is live" line would be false for
            # every native signup from here on. Kept in step with the body
            # (services/email.render_welcome_email, "Your Tapeline account is
            # live") — subject and body must not tell different stories.
            await send_email(
                user.email,
                "Welcome to Tapeline — your account is live",
                render_welcome_email(user.name or "trader", picks=picks),
            )
        except Exception:
            logger.exception("auth.welcome_email_failed user=%s", user.id)

    # Verification email — fire-and-forget, alongside the welcome. Native
    # signup ONLY: OAuth users get auto-verified in routers/oauth.py because
    # the provider already proved ownership.
    try:
        from app.services.email import mint_and_send_verification
        await mint_and_send_verification(session, user)
    except Exception:
        logger.exception("auth.verification_send_failed user=%s", user.id)

    return {"user": _user_out(user)}


# ── Email verification ────────────────────────────────────────────────────


async def _apply_referrer_credit(session: AsyncSession, referee: User) -> User | None:
    """Grant the user who referred `referee` one free month, if they're eligible.

    Called exactly once per referee, at their FIRST successful email
    verification — that's the conversion signal that makes the credit cost
    something to farm. Mutates the referrer in the caller's session but does
    NOT commit; the caller commits alongside the verification stamp so the
    credit and the "this referee has been counted" marker land atomically.

    Returns the credited referrer (so the caller can email them after the
    commit), or None when nothing was granted.
    """
    if not referee.referred_by:
        return None
    r = await session.execute(select(User).where(User.id == referee.referred_by))
    referrer = r.scalar_one_or_none()
    if referrer is None or referrer.id == referee.id:
        return None
    balance = referrer.referral_credit_months or 0
    if balance >= MAX_REFERRAL_CREDIT_MONTHS:
        # Not an error — they've simply banked the maximum. Accrual resumes
        # once they redeem some at checkout.
        logger.info(
            "auth.referral_credit_capped referrer=%s balance=%s cap=%s",
            referrer.id, balance, MAX_REFERRAL_CREDIT_MONTHS,
        )
        return None
    referrer.referral_credit_months = balance + 1
    logger.info(
        "auth.referral_credit_granted referrer=%s referee=%s balance=%s",
        referrer.id, referee.id, referrer.referral_credit_months,
    )
    return referrer


class VerifyEmailBody(BaseModel):
    """POST body for the verify-email endpoint. We accept POST + GET so the
    frontend can call this from a click handler without juggling redirects;
    GET keeps the simple-link case working for email clients that don't
    handle anchor → fetch chains."""

    token: str = Field(..., min_length=8, max_length=200)
    action: str = Field("verify", pattern=r"^(verify|cancel)$")
    # Second gesture required for action="cancel" ONLY — see the cancel branch
    # in _consume_verification. Ignored for action="verify".
    confirm: bool = False


async def _consume_verification(
    session: AsyncSession, token: str, action: str, *, confirmed: bool = False,
) -> dict:
    """Shared implementation for GET and POST verification endpoints.

    Returns a dict the caller can shape into JSON. Never raises 5xx —
    every branch is a user-readable outcome:
      - {"status": "verified"}             token good, email stamped
      - {"status": "confirm_required"}     cancel asked for without confirm=true
      - {"status": "cancelled"}            user said "this wasn't me" — account deleted
      - {"status": "already_verified"}     token already consumed earlier
      - {"status": "expired"}              token past 24h
      - {"status": "invalid"}              token doesn't exist / bad shape
    """
    from app.models import EmailVerificationToken

    r = await session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token == token,
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        return {"status": "invalid"}

    now = datetime.now(UTC)
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if row.used_at is not None:
        # Idempotent: a second click on the same link reports the prior
        # outcome rather than scaring the user with "invalid token".
        return {"status": "already_verified"}

    if expires_at < now:
        return {"status": "expired"}

    # Load user
    u = await session.execute(select(User).where(User.id == row.user_id))
    user = u.scalar_one_or_none()
    if user is None:
        # Shouldn't happen (FK cascade), but defensively treat as invalid.
        return {"status": "invalid"}

    if action == "cancel":
        # "This wasn't me" — hard, cascading, irreversible account deletion.
        #
        # It used to fire on nothing more than the URL being fetched, which
        # meant NO HUMAN had to act for an account to be destroyed: the
        # cancel_url is an <a href> in every verification email, and mail
        # security stacks detonate emailed links in an instrumented headless
        # browser (Defender for Office 365 Safe Links, Proofpoint URL Defense)
        # — as do link prefetchers, antivirus crawlers and browser prerender.
        # The token stays valid for 24h, so every one of those loads re-fired
        # the delete on a brand-new signup.
        #
        # Two gates now stand in front of it: GET can never confirm (it passes
        # confirmed=False unconditionally — a safe method must not destroy
        # state), and POST must carry an explicit confirm=true that only a
        # deliberate button press sets. A crawler following the link lands on
        # confirm_required, which is a screen, not a deletion.
        if not confirmed:
            return {"status": "confirm_required"}
        # Delete the child rows FIRST, then the user.
        #
        # This was a bare `session.delete(user)`. Of the 14 FKs into `users`,
        # only email_verification_tokens, password_reset_tokens and
        # mfa_recovery_codes carry ON DELETE CASCADE — watchlists,
        # watchlist_items, alert_rules, alert_events, api_keys, roadmap_votes,
        # scanner_presets, subscriptions, web_push_subscriptions and
        # watchlist_track_record do not, and there is no ORM relationship()
        # anywhere in app/models/, so SQLAlchemy emits a plain DELETE FROM users
        # and Postgres enforces RESTRICT.
        #
        # The child rows are GUARANTEED to be there: me.submit_onboarding fires
        # on both Submit and Skip and seeds a watchlist plus 2-4 items in the
        # first minute of every account — before the user has even opened the
        # verification email. So "this wasn't me" raised a ForeignKeyViolation,
        # the commit rolled back, and the account the user had just reported as
        # fraudulent stayed alive.
        #
        # Shared with the GDPR erasure path so a newly-added child table cannot
        # be handled by one and missed by the other.
        from app.services.account_purge import purge_user

        await purge_user(session, user.id, user.email)
        await session.commit()
        logger.info(
            "auth.verification_cancelled user=%s email=%s", user.id, user.email,
        )
        return {"status": "cancelled"}

    # action == "verify"
    # Gate the referral payout on email_verified_at being unset rather than on
    # the token alone. A single-use token is enough TODAY only because
    # mint_and_send_verification deletes prior unused tokens, so an
    # already-verified user can still be handed a fresh valid one (via
    # /resend-verification) and walk this branch a second time. Keying off the
    # user's verified stamp makes "one credit per referee" hold regardless.
    first_verification = user.email_verified_at is None
    user.email_verified_at = now
    row.used_at = now
    credited_referrer = (
        await _apply_referrer_credit(session, user) if first_verification else None
    )
    await session.commit()
    logger.info("auth.verification_verified user=%s", user.id)

    # Fire-and-forget, after the commit — the credit is already durable, and a
    # Resend hiccup must never turn a successful verification into an error.
    if credited_referrer is not None and credited_referrer.email:
        try:
            from app.services.email import (
                render_referral_referrer_email,
                send_email,
            )
            masked_referee = (
                user.email[:3] + "***" + user.email[user.email.index("@"):]
            )
            await send_email(
                credited_referrer.email,
                "Someone joined Tapeline via your link — 1 free month credited",
                render_referral_referrer_email(
                    credited_referrer.name or "trader", masked_referee,
                ),
            )
        except Exception:
            logger.exception(
                "auth.referral_referrer_email_failed referrer=%s referee=%s",
                credited_referrer.id, user.id,
            )

    return {"status": "verified"}


@router.get("/verify-email")
async def verify_email_get(
    token: str,
    action: str = "verify",
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GET variant — what the email link points at. Mirror of POST below.

    Validation is identical to the Pydantic body in POST; we re-do the
    pattern check here so a malformed query string returns 400 rather
    than passing junk into _consume_verification.

    Deliberately takes no `confirm` parameter: action="cancel" over GET always
    resolves to {"status": "confirm_required"}, never a deletion. A GET is a
    safe method that prefetchers, mail scanners and crawlers issue without a
    human — it may report what the link WOULD do, not do it.
    """
    if action not in ("verify", "cancel"):
        raise HTTPException(400, "action must be 'verify' or 'cancel'")
    if not (8 <= len(token) <= 200):
        raise HTTPException(400, "token has an invalid length")
    return await _consume_verification(session, token, action, confirmed=False)


@router.post("/verify-email")
async def verify_email_post(
    body: VerifyEmailBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _consume_verification(
        session, body.token, body.action, confirmed=body.confirm,
    )


@router.post("/resend-verification", dependencies=[Depends(limit_auth)])
async def resend_verification(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mint a fresh 24h verification token + send the email.

    Requires an authenticated session (you can only ask to resend YOUR
    OWN verification email — there's no email-to-userid path here so
    we don't accidentally enable account-enumeration via this endpoint).
    No-op + 200 if the user is already verified.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    decoded = decode_session_token(token)
    if not decoded:
        raise HTTPException(401, "Invalid session")
    user_id, epoch = decoded
    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if user is None or not session_epoch_matches(user.session_epoch, epoch):
        raise HTTPException(401, "Invalid session")
    if user.email_verified_at is not None:
        return {"status": "already_verified"}
    from app.services.email import mint_and_send_verification
    ok = await mint_and_send_verification(session, user)
    return {"status": "sent" if ok else "send_skipped"}


# ── Password reset ────────────────────────────────────────────────────────

class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(..., min_length=8, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)


# Constant-time floor for /forgot-password, in seconds.
#
# The endpoint returns an identical body for known and unknown addresses, but
# that only hides enumeration if the two branches also COST the same. They
# didn't: a hit awaited mint_and_send_password_reset (DELETE + INSERT + commit,
# then an httpx POST to Resend with a 10s timeout) while a miss returned after
# one SELECT — a sub-millisecond baseline against a several-hundred-millisecond
# hit, which is a clean oracle at 10 probes/min/IP. The Resend round-trip is now
# deferred to a background task (below) so it lands AFTER the response is
# flushed, and this floor pads whatever is left so both branches sit on the same
# wall-clock shelf. Cheap insurance: nobody is latency-sensitive on a
# password-reset request.
_FORGOT_PASSWORD_FLOOR_SECONDS = 0.5


async def _send_password_reset_bg(user_id: str) -> None:
    """Mint + send the reset email OUTSIDE the request path.

    Runs as a Starlette background task, i.e. after the response bytes are
    flushed, which is the point — see _FORGOT_PASSWORD_FLOOR_SECONDS. It must
    open its OWN session: FastAPI tears down `yield` dependencies (and hence
    the request-scoped AsyncSession) before background tasks run.
    """
    from app.db import session_scope
    from app.services.email import mint_and_send_password_reset

    try:
        async with session_scope() as s:
            r = await s.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if user is None:
                return
            await mint_and_send_password_reset(s, user)
    except Exception:
        logger.exception("auth.password_reset_send_failed user=%s", user_id)


async def _send_signin_code_bg(user_id: str) -> None:
    """Mint + email a sign-in code OUTSIDE the request path.

    Same shape (and same reason) as _send_password_reset_bg: FastAPI tears the
    request-scoped session down before background tasks run, so this opens its
    own. Keeping Resend off the signin request matters more here than for a
    reset — the user is sitting on a spinner waiting to log in.

    A delivery failure is logged, not surfaced: /signin has already returned
    the challenge, and telling the client "the email failed" would leak that
    the password was correct.
    """
    from app.db import session_scope
    from app.services.email import mint_and_send_signin_code

    try:
        async with session_scope() as s:
            r = await s.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if user is None:
                return
            await mint_and_send_signin_code(s, user)
    except Exception:
        logger.exception("auth.signin_code_send_failed user=%s", user_id)


@router.post("/forgot-password", dependencies=[Depends(limit_auth)])
async def forgot_password(
    body: ForgotPasswordBody,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Initiate a password reset.

    Returns 200 with {"status": "sent"} regardless of whether the email
    matches a real account. This is deliberate: a different response for
    unknown emails would let attackers enumerate which addresses have
    accounts. Slightly worse UX for typos, much better security posture.
    Rate-limited by limit_auth, and padded to a constant time floor so the
    uniform body isn't undone by a non-uniform latency.
    """
    started = time.monotonic()
    email = body.email.lower().strip()

    # Look the address up BOTH as typed and in the canonical form signup
    # stores. signup writes normalise_email(body.email) (see the signup
    # handler), which strips dots and +tags for Gmail/Outlook-family domains —
    # so a user who registered "bob.smith@gmail.com" is on file as
    # "bobsmith@gmail.com" and an exact-match lookup here silently missed them.
    # The endpoint still answered {"status": "sent"}, so the account was
    # unrecoverable through the UI with no error to report. Both candidates go
    # into ONE query: two sequential SELECTs would reintroduce the timing
    # difference this endpoint is trying to erase. Storage is unchanged; only
    # the lookup widened, and an exact hit still wins over a canonical one.
    candidates = {email, normalise_email(body.email)}
    rows = (
        await session.execute(select(User).where(User.email.in_(candidates)))
    ).scalars().all()
    user = next((u for u in rows if u.email == email), None) or (
        rows[0] if rows else None
    )

    if user is not None and user.password_hash:
        # OAuth-only users (password_hash IS NULL) can't reset what they
        # never had — silently no-op for them too, same response as
        # unknown-email case, so we don't leak "this email signed up with
        # Google" either.
        background.add_task(_send_password_reset_bg, user.id)
    else:
        logger.info("auth.forgot_password_noop email=%s", email)

    remaining = _FORGOT_PASSWORD_FLOOR_SECONDS - (time.monotonic() - started)
    if remaining > 0:
        await asyncio.sleep(remaining)
    return {"status": "sent"}


@router.post("/reset-password", dependencies=[Depends(limit_auth)])
async def reset_password(
    body: ResetPasswordBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Consume a password-reset token and update the user's password.

    Returns one of:
      {"status": "reset"}             token good, password updated
      {"status": "expired"}           token past 60min
      {"status": "already_used"}      token already consumed
      {"status": "invalid"}           token doesn't exist / bad shape
      {"status": "weak_password"}     new password failed hash_password validation
    """
    from app.models import PasswordResetToken

    r = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == body.token,
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        return {"status": "invalid"}

    if row.used_at is not None:
        return {"status": "already_used"}

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        return {"status": "expired"}

    u = await session.execute(select(User).where(User.id == row.user_id))
    user = u.scalar_one_or_none()
    if user is None:
        return {"status": "invalid"}

    try:
        pw = hash_password(body.password)
    except ValueError:
        return {"status": "weak_password"}

    user.password_hash = pw
    # Evict every outstanding session for this account.
    #
    # This is the whole point of a reset done under compromise: the receipt
    # email below offers an "if this wasn't you" path, and before the epoch
    # existed that path did nothing — session JWTs are stateless, so an
    # attacker's captured cookie kept working for the remainder of its 30-day
    # exp no matter how many times the victim changed their password. Bumping
    # the counter makes every token minted before this line fail on the next
    # request. No cookie is re-issued: the user is anonymous here (they hold a
    # reset token, not a session) and signs in again straight after.
    user.session_epoch = int(user.session_epoch or 0) + 1
    row.used_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "auth.password_reset_completed user=%s session_epoch=%s",
        user.id, user.session_epoch,
    )

    # Security-confirmation receipt — fire-and-forget so a Resend hiccup
    # never fails the reset. Account-state notification (the user can't opt
    # out of it): persona "default", no List-Unsubscribe. Gives an
    # "if this wasn't you" recovery path if someone reset a password the
    # real owner didn't request.
    if user.email:
        try:
            from app.services.email import (
                render_security_confirmation_email,
                send_email,
            )

            html = render_security_confirmation_email(
                user.name or "trader",
                change="Your password was changed",
            )
            await send_email(
                user.email,
                "Your Tapeline password was changed",
                html,
                persona="default",
            )
        except Exception:  # email must never block the reset
            logger.exception(
                "auth.password_reset_confirmation_email_failed user=%s", user.id
            )

    return {"status": "reset"}


@router.post("/signin", dependencies=[Depends(limit_auth)])
async def signin(
    body: SigninBody,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    email = body.email.lower().strip()
    # Same two-candidate lookup as /forgot-password. Signup normalises the
    # address before storing it (Gmail dots and +tags collapse), so a user who
    # signed up as "first.last@gmail.com" is stored as "firstlast@gmail.com"
    # and an exact-match signin never found them — they could complete a
    # password reset and STILL be unable to log in, which is the worst kind of
    # broken: the recovery path appears to work. One IN query rather than two
    # SELECTs so both branches stay the same shape; an exact hit still wins.
    candidates = {email, normalise_email(body.email)}
    rows = (
        await session.execute(select(User).where(User.email.in_(candidates)))
    ).scalars().all()
    user = next((u for u in rows if u.email == email), None) or (
        rows[0] if rows else None
    )
    if user is None or not verify_password(body.password, user.password_hash):
        # Identical error message for both branches = no account enumeration
        raise HTTPException(401, "Invalid email or password")

    # 2FA gate — if TOTP is enabled, don't mint a session yet. Return a
    # short-lived challenge token the client exchanges at POST /api/auth/2fa
    # together with a live authenticator code (or a recovery code).
    if user.mfa_enabled and user.totp_secret:
        from app.services.mfa import issue_mfa_token
        logger.info("auth.signin_mfa_challenge user=%s", user.id)
        return {"mfa_required": True, "mfa_token": issue_mfa_token(user.id)}

    # New-device gate. A browser that has already cleared an emailed code
    # carries a signed trust cookie (30 days); anything else has to prove it
    # can read the account's inbox before we mint a session.
    #
    # Deliberately NOT applied to every sign-in: that would make Resend a hard
    # dependency of logging in at all, so a mail outage would lock every user
    # (including the founder) out of a live product. Unrecognised-device-only
    # is the same trade every major SaaS makes.
    from app.services.signin_codes import (
        CODE_ISSUE_MAX,
        CODE_ISSUE_WINDOW_SECONDS,
        TRUSTED_DEVICE_COOKIE,
        is_trusted_device,
        mask_email,
    )

    if not is_trusted_device(
        request.cookies.get(TRUSTED_DEVICE_COOKIE), user.id, user.session_epoch
    ):
        # Cap codes ISSUED per account. limit_auth buckets on IP, which does
        # nothing to stop someone who knows a victim's password from using
        # /signin as a mail bomb; this bucket is keyed on the account being
        # mailed. Verification attempts are capped separately at /2fa.
        if not await limiter.consume(
            f"signin_code:{user.id}", CODE_ISSUE_MAX, CODE_ISSUE_WINDOW_SECONDS
        ):
            logger.warning("auth.signin_code_issue_cap_hit user=%s", user.id)
            raise HTTPException(
                429,
                "Too many sign-in codes requested for this account. "
                "Wait a few minutes, then try again.",
            )
        from app.services.mfa import issue_mfa_token
        background.add_task(_send_signin_code_bg, user.id)
        logger.info("auth.signin_code_challenge user=%s", user.id)
        return {
            "mfa_required": True,
            "mfa_token": issue_mfa_token(user.id),
            "method": "email",
            # Masked so the code screen can say WHICH inbox to check without
            # handing the full address to someone who only has the password.
            "email_hint": mask_email(user.email),
        }

    token = issue_session_token(user.id, user.session_epoch)
    response.set_cookie(value=token, **session_cookie_kwargs())
    logger.info("auth.signin user=%s", user.id)
    return {"user": _user_out(user)}


class TwoFASigninBody(BaseModel):
    mfa_token: str = Field(..., min_length=8, max_length=2048)
    # 6 digits for a TOTP, or a recovery code. Recovery codes grew from
    # "a1b2c-d3e4f" (11 chars) to 80 bits dash-grouped in fives —
    # "a1b2c-d3e4f-5a6b7-c8d9e", 23 chars — so the old max_length=20 would
    # have 422'd every newly minted code before it reached the handler.
    code: str = Field(..., min_length=6, max_length=64)


# ---- Per-account 2FA guess budget -------------------------------------------
#
# limit_auth buckets on client IP alone (services/rate_limit.limit_auth), which
# a distributed guesser sidesteps for free: every proxy gets its own auth:{ip}
# bucket while NOTHING on the account side moves. A TOTP is 1e6 codes and
# verify_totp accepts a ±1 step window, so ~333k guesses is the expected hit —
# roughly half an hour across a thousand IPs, and a failed code neither burns
# the mfa_token nor leaves a trace. This second bucket is keyed on the ACCOUNT,
# so the budget being spent belongs to the victim rather than the attacker, and
# a distributed guesser exhausts it just as fast as a single host would.
#
# Reuses the existing in-process TokenBucket rather than adding a
# users.failed_2fa_attempts column: no migration needed, and the bucket refills
# on its own so there is no lockout for support to clear by hand. It inherits
# limit_auth's known limitation — the counter is per Fly machine, so the true
# ceiling is TWOFA_MAX_ATTEMPTS × (running machines). One machine today; move
# both to a shared store together when we scale out.
TWOFA_MAX_ATTEMPTS = 5
TWOFA_WINDOW_SECONDS = 900


async def _consume_signin_code(
    session: AsyncSession, user: User, code: str
) -> bool:
    """Verify + burn an emailed sign-in code. True only if it was live.

    Single-use is enforced with a CONDITIONAL update rather than a
    read-then-assign, for the same reason the TOTP step-burn below is: two
    submissions of the same code racing each other would otherwise both pass
    their read and both mint a session. The database arbitrates instead.

    Codes are compared in constant time (services/signin_codes.verify_code)
    and the newest few unused rows are scanned — mint_and_send_signin_code
    invalidates prior codes, so in practice there is at most one.
    """
    from app.models import SigninCode
    from app.services.signin_codes import verify_code

    now = datetime.now(UTC)
    rows = (await session.execute(
        select(SigninCode)
        .where(SigninCode.user_id == user.id, SigninCode.used_at.is_(None))
        .order_by(SigninCode.created_at.desc())
        .limit(5)
    )).scalars().all()

    for row in rows:
        expires_at = row.expires_at
        # SQLite hands back naive datetimes; Postgres tz-aware. Same
        # normalisation the verification/reset paths use above.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            continue
        if not verify_code(code, user.id, row.code_hash):
            continue
        res = await session.execute(
            update(SigninCode)
            .where(SigninCode.id == row.id, SigninCode.used_at.is_(None))
            .values(used_at=now)
        )
        # rowcount 0 => another request spent this code between our read and
        # our write, so that one wins and this submission fails.
        return res.rowcount != 0  # type: ignore[attr-defined]
    return False


@router.post("/2fa", dependencies=[Depends(limit_auth)])
async def signin_2fa(
    body: TwoFASigninBody,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Second step of a 2FA signin: verify the code, then mint the session.

    Accepts either a current 6-digit TOTP code OR one of the user's
    single-use recovery codes. The challenge token (from /signin) proves the
    password step already passed and expires after 5 minutes.
    """
    from app.services.mfa import (
        normalise_recovery_code,
        verify_mfa_token,
        verify_recovery_code,
        verify_totp_step,
    )

    user_id = verify_mfa_token(body.mfa_token)
    if not user_id:
        raise HTTPException(401, "Your verification window expired. Please sign in again.")

    # Per-account guess budget — see TWOFA_MAX_ATTEMPTS above. Consumed before
    # the code is checked (and before the user row is loaded) so a locked-out
    # account costs the attacker a 429 and nothing else.
    if not await limiter.consume(
        f"2fa:{user_id}", TWOFA_MAX_ATTEMPTS, TWOFA_WINDOW_SECONDS
    ):
        logger.warning("auth.2fa_attempt_cap_hit user=%s", user_id)
        raise HTTPException(
            429,
            "Too many verification attempts on this account. "
            "Wait a few minutes, then sign in again.",
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Two-factor auth is not active on this account.")

    code = body.code.strip()

    # ── Emailed sign-in code (accounts without an authenticator app) ────────
    # /signin only issues one when the browser isn't already trusted, so
    # clearing it is also what EARNS that trust: we set the 30-day device
    # cookie here, which is why the next sign-in from this browser is a plain
    # password login. TOTP accounts never reach this branch.
    if not (user.mfa_enabled and user.totp_secret):
        if not await _consume_signin_code(session, user, code):
            raise HTTPException(
                401,
                "That code is wrong or has expired. Sign in again to get a new one.",
            )
        from app.services.signin_codes import (
            issue_trusted_device_token,
            trusted_device_cookie_kwargs,
        )
        response.set_cookie(
            value=issue_trusted_device_token(user.id, user.session_epoch),
            **trusted_device_cookie_kwargs(),
        )
        response.set_cookie(
            value=issue_session_token(user.id, user.session_epoch),
            **session_cookie_kwargs(),
        )
        await session.commit()
        logger.info("auth.signin_code_verified user=%s", user.id)
        return {"user": _user_out(user)}
    # Burn the time-step this code belongs to. verify_totp_step refuses any
    # step at or below user.totp_last_step, so the same 6 digits can't be
    # replayed inside their ~90s ±1 window — which is what let an attacker who
    # observed the victim's own successful login sign in with the same code.
    step = verify_totp_step(user.totp_secret, code, user.totp_last_step)
    if step is not None:
        # Burn the step with a CONDITIONAL update, not a read-then-assign.
        # The threat this guard exists for is a real-time phishing proxy —
        # an adversary who controls request timing and will submit the relayed
        # code ALONGSIDE the victim rather than politely afterwards. Two
        # overlapping requests both read the pre-burn value, so an in-memory
        # assignment lets both through and mints two sessions from one code.
        # Pushing the comparison into the WHERE clause makes the database the
        # arbiter: the second writer re-evaluates it after the first commits
        # and matches zero rows.
        #
        # A conditional UPDATE rather than SELECT ... FOR UPDATE because
        # SQLite ignores row locks, which would leave this untestable on the
        # dev/CI path.
        res = await session.execute(
            update(User)
            .where(
                User.id == user.id,
                or_(User.totp_last_step.is_(None), User.totp_last_step < step),
            )
            .values(totp_last_step=step)
        )
        if res.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult.rowcount (DML)
            # Someone else spent this step between our read and our write.
            raise HTTPException(401, "Invalid code.")
        user.totp_last_step = step
    else:
        # Not a valid TOTP — try a single-use recovery code.
        #
        # bcrypt salts per row, so there is no indexed hash lookup any more:
        # we scan the user's unused rows. Two guards on the cost of that —
        # a length floor (both code formats normalise to >= 10 chars, a TOTP
        # to 6), so a mistyped 6-digit code doesn't buy ~10 bcrypt rounds;
        # and no early break, so the wall-clock cost doesn't reveal WHICH row
        # matched.
        from app.models import MfaRecoveryCode
        rc = None
        if len(normalise_recovery_code(code)) >= 10:
            rows = (await session.execute(
                select(MfaRecoveryCode).where(
                    MfaRecoveryCode.user_id == user.id,
                    MfaRecoveryCode.used_at.is_(None),
                )
            )).scalars().all()
            # Off the event loop: each bcrypt check is ~190ms, so scanning ten
            # rows inline would block the single uvicorn worker for ~1.9s per
            # attempt. Every row is still checked (no early exit) so wall-clock
            # doesn't reveal WHICH row matched — the comprehension runs to
            # completion inside the thread before we pick a winner.
            stored = [row.code_hash for row in rows]
            matches = await asyncio.to_thread(
                lambda: [verify_recovery_code(code, h) for h in stored]
            )
            idx = next((i for i, ok in enumerate(matches) if ok), None)
            if idx is not None:
                rc = rows[idx]
        if rc is None:
            raise HTTPException(401, "Invalid code.")

        # Burn the code with a CONDITIONAL UPDATE, for exactly the reason the
        # TOTP branch above spells out — and which this branch used to ignore.
        #
        # It read the unused rows, spent ~1.9s in bcrypt off the event loop,
        # then did an in-memory `rc.used_at = ...` before the commit. That is
        # the pattern the comment above calls out by name: "an in-memory
        # assignment lets both through and mints two sessions from one code".
        # The bcrypt scan makes the window enormous — two overlapping requests
        # both SELECT the row while `used_at IS NULL`, both spend their ~1.9s,
        # both stamp it, and both fall through to issue_session_token +
        # set_cookie. A real-time phishing proxy controls request timing and
        # submits the relayed code ALONGSIDE the victim rather than after them.
        #
        # `WHERE used_at IS NULL` makes the database the arbiter: the second
        # writer re-evaluates it after the first commits and matches zero rows.
        # Conditional UPDATE rather than SELECT ... FOR UPDATE because SQLite
        # ignores row locks, which would leave this untestable on dev/CI.
        from app.models import MfaRecoveryCode as _MfaRecoveryCode

        burned = await session.execute(
            update(_MfaRecoveryCode)
            .where(
                _MfaRecoveryCode.id == rc.id,
                _MfaRecoveryCode.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        if burned.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult.rowcount (DML)
            # Someone else spent this code between our read and our write.
            raise HTTPException(401, "Invalid code.")

    token = issue_session_token(user.id, user.session_epoch)
    response.set_cookie(value=token, **session_cookie_kwargs())
    await session.commit()
    logger.info("auth.signin_2fa user=%s", user.id)
    return {"user": _user_out(user)}


@router.post("/signout")
async def signout(response: Response) -> dict:
    # KNOWN LIMITATION — signout still only clears the BROWSER's copy of the
    # cookie. It does not revoke the token, so a copy captured before signout
    # keeps working until its 30-day exp.
    #
    # The session_epoch counter added for password reset could evict it, but
    # the epoch is per-USER, not per-device: bumping it here would sign the
    # user out of their phone and their other laptop every time they signed
    # out of one tab. Per-device revocation needs a sessions table keyed on a
    # per-token id, which is deliberately out of scope. Until then, the
    # recovery path for a stolen cookie is a password reset, which now
    # genuinely works (see reset_password).
    #
    # delete_cookie only takes effect when its (path, domain) tuple matches
    # the original Set-Cookie's scope. In prod the session cookie is set on
    # domain=".tapeline.io" so it's shared between api.* and the apex —
    # without passing the same domain here, the browser keeps the original
    # cookie and the session stays alive after signout returns {ok: true}.
    kw = session_cookie_kwargs()
    response.delete_cookie(kw["key"], path=kw.get("path", "/"), domain=kw.get("domain"))
    return {"ok": True}


@router.get("/session")
async def get_session_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Frontend hits this on boot to restore auth state. Returns null user if not logged in."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return {"user": None}
    decoded = decode_session_token(token)
    if not decoded:
        return {"user": None}
    user_id, epoch = decoded
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not session_epoch_matches(user.session_epoch, epoch):
        return {"user": None}
    return {"user": _user_out(user)}
