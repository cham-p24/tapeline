"""Report converted (trial -> paid) subscribers' click conversions to Google Ads.

THE GAP THIS CLOSES
-------------------
Tapeline's paid conversion happens ~14+ days after the ad click (the free
trial), OFF-SESSION — so a browser pixel can never see it. Without this, Google
Ads Smart Bidding optimises toward trial SIGNUPS (people who love free things)
instead of PAYERS. This job reports each paid subscriber's stored Google click
id back to Google Ads with the first-charge value, so value-based bidding
chases real revenue. The capture side is already built: frontend/lib/utm.ts
stores the click id on landing, routers/auth.py writes it to
users.signup_gclid / signup_gbraid / signup_wbraid at signup.

WHAT COUNTS AS A CONVERSION
---------------------------
A user who (1) carries a Google click id, and (2) has at least one Subscription
in status 'active' — a 30-day trial flips 'trialing' -> 'active' on the first
real charge — and (3) has not been uploaded before
(users.ads_conversion_uploaded_at IS NULL). One conversion per user; that
timestamp is the idempotency key, so a daily run never double-counts.

SAFE BY DEFAULT
---------------
- If the Google Ads credentials are not fully configured, the job runs in
  DRY-RUN: it logs exactly what it WOULD upload, calls nothing, marks nothing,
  and exits 0. So it is harmless to schedule before the founder finishes the
  Google-side setup, and it is unit-testable without the google-ads dependency.
- Pass --dry-run to force a preview even when creds are present.
- Uploads use partial_failure=True and per-row success detection: one bad row
  never sinks the batch, and only rows Google accepts get marked uploaded.

CREDENTIALS (env — see docs/launch/google-ads/OFFLINE-CONVERSION-IMPORT.md)
--------------------------------------------------------------------------
  GOOGLE_ADS_DEVELOPER_TOKEN
  GOOGLE_ADS_CLIENT_ID
  GOOGLE_ADS_CLIENT_SECRET
  GOOGLE_ADS_REFRESH_TOKEN
  GOOGLE_ADS_LOGIN_CUSTOMER_ID      # manager (MCC) id, digits only, no dashes
  GOOGLE_ADS_CUSTOMER_ID            # the 271-638-2397 account, digits only
  GOOGLE_ADS_CONVERSION_ACTION_ID   # the 'Subscribe' conversion action id

USAGE
-----
    python -m app.scripts.upload_google_ads_conversions --dry-run
    python -m app.scripts.upload_google_ads_conversions            # live if creds set
    fly ssh console -a tapeline-backend -C "python -m app.scripts.upload_google_ads_conversions"

Exits 0 on success (including dry-run / nothing-to-do), 1 on a hard failure.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import UTC, datetime

from sqlalchemy import or_, select

from app.db import session_scope
from app.models.user import Subscription, User

logger = logging.getLogger("app.scripts.upload_google_ads_conversions")

# First-charge value (USD) for value-based bidding, keyed (tier, billing_period).
# Mirrors frontend/lib/pricing.ts — the single source of truth for display +
# checkout. Kept as a small local map because this value feeds Smart Bidding
# (approximate is fine), not billing. Update alongside any reprice.
_PRICE_USD: dict[tuple[str, str], float] = {
    ("pro", "monthly"): 9.99,
    ("pro", "annual"): 99.0,
    ("premium", "monthly"): 19.99,
    ("premium", "annual"): 199.0,
}
_VALUE_FLOOR = 9.99  # cheapest real plan — used for any unmapped tier/period

_CRED_ENV = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_CONVERSION_ACTION_ID",
)


# ── pure helpers (unit-tested; no DB, no network) ──────────────────────────
def creds_present() -> bool:
    """True only when every Google Ads credential env var is set."""
    return all(os.getenv(k) for k in _CRED_ENV)


def conversion_value(tier: str | None, billing_period: str | None) -> float:
    """First-charge USD value for value-based bidding. An unknown tier/period
    combination falls back to the cheapest real plan, so a mis-tagged sub never
    uploads a zero or an inflated value."""
    return _PRICE_USD.get(
        (str(tier or "").lower(), str(billing_period or "").lower()),
        _VALUE_FLOOR,
    )


def click_identifier(user: User) -> tuple[str, str] | None:
    """(field_name, value) for the strongest available Google click id,
    preferring gclid > gbraid > wbraid. None when the user carries none (not a
    paid-Google signup — skip)."""
    if user.signup_gclid:
        return ("gclid", user.signup_gclid)
    if user.signup_gbraid:
        return ("gbraid", user.signup_gbraid)
    if user.signup_wbraid:
        return ("wbraid", user.signup_wbraid)
    return None


def format_conversion_time(dt: datetime) -> str:
    """Google Ads wants 'yyyy-mm-dd hh:mm:ss+hh:mm' with an explicit offset;
    a naive string is rejected. We always emit UTC."""
    dt = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + "+00:00"


# ── DB gather ──────────────────────────────────────────────────────────────
async def gather_pending(session, limit: int) -> list[dict]:
    """Converted-but-not-yet-uploaded subscribers who carry a Google click id.

    Returns lightweight dicts (all DB work done before any network I/O), one per
    user (deduped — a duplicate-conversion user can hold two active subs)."""
    stmt = (
        select(User, Subscription)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            Subscription.status == "active",
            User.ads_conversion_uploaded_at.is_(None),
            or_(
                User.signup_gclid.isnot(None),
                User.signup_gbraid.isnot(None),
                User.signup_wbraid.isnot(None),
            ),
        )
        # Deterministic pick for a user with >1 active subscription: always the
        # earliest sub, so the same order_id (Google's cross-run dedup key) and
        # value are chosen every run — never an arbitrary row that could carry a
        # different order_id, escape Google's dedup, and double-count.
        .order_by(Subscription.created_at.asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return rows_to_pending(rows)


def rows_to_pending(rows) -> list[dict]:
    """Dedup (User, Subscription) rows to ONE conversion dict per user — a
    duplicate-conversion user can hold more than one active sub — and build the
    upload payload. Pure (no DB / no network) so the dedup + value + click-id
    logic is unit-tested directly. `rows` is ordered by the caller so the chosen
    sub (hence order_id / value) is stable across runs."""
    pending: list[dict] = []
    seen: set[str] = set()
    for user, sub in rows:
        if user.id in seen:
            continue
        ident = click_identifier(user)
        if ident is None:
            continue
        seen.add(user.id)
        pending.append(
            {
                "user_id": user.id,
                "click_field": ident[0],
                "click_value": ident[1],
                "value": conversion_value(sub.tier, sub.billing_period),
                "currency": "USD",
                "order_id": str(sub.id),  # Stripe sub id — Ads also dedups on this
            }
        )
    return pending


# ── live upload (google-ads imported lazily so the module loads without it) ─
def upload_conversions(pending: list[dict]) -> tuple[set[str], list[str]]:
    """Upload the click conversions. Returns (user_ids Google accepted,
    error_messages). Only accepted rows are returned, so the caller marks only
    those uploaded and the rest retry on the next run."""
    from google.ads.googleads.client import GoogleAdsClient  # lazy import

    customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"]
    action_id = os.environ["GOOGLE_ADS_CONVERSION_ACTION_ID"]
    client = GoogleAdsClient.load_from_dict(
        {
            "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            "login_customer_id": os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"],
            "use_proto_plus": True,
        }
    )
    upload_service = client.get_service("ConversionUploadService")
    action_service = client.get_service("ConversionActionService")
    action_rn = action_service.conversion_action_path(customer_id, action_id)
    now_str = format_conversion_time(datetime.now(UTC))

    conversions = []
    for p in pending:
        cc = client.get_type("ClickConversion")
        cc.conversion_action = action_rn
        setattr(cc, p["click_field"], p["click_value"])  # gclid | gbraid | wbraid
        cc.conversion_date_time = now_str
        cc.conversion_value = float(p["value"])
        cc.currency_code = p["currency"]
        cc.order_id = p["order_id"]
        conversions.append(cc)

    request = client.get_type("UploadClickConversionsRequest")
    request.customer_id = customer_id
    request.conversions.extend(conversions)
    request.partial_failure = True  # one bad row never sinks the batch

    response = upload_service.upload_click_conversions(request=request)

    # results is index-aligned with the input; a SUCCESSFUL row echoes its
    # fields, a FAILED row comes back empty (reason in partial_failure_error).
    ok_user_ids: set[str] = set()
    for i, r in enumerate(response.results):
        populated = bool(
            getattr(r, "conversion_action", "")
            or getattr(r, "gclid", "")
            or getattr(r, "gbraid", "")
            or getattr(r, "wbraid", "")
        )
        if populated:
            ok_user_ids.add(pending[i]["user_id"])

    errors: list[str] = []
    pfe = getattr(response, "partial_failure_error", None)
    if pfe and getattr(pfe, "message", ""):
        errors.append(pfe.message)
    return ok_user_ids, errors


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report paid subscribers' Google Ads click conversions (offline import)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only — never call the API, never mark uploaded.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max conversions per run (default 500).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.dry_run:
        dry = True
        logger.info("dry-run forced via --dry-run")
    elif not creds_present():
        dry = True
        missing = [k for k in _CRED_ENV if not os.getenv(k)]
        logger.warning(
            "Google Ads creds not configured (missing: %s) — running DRY-RUN. "
            "See docs/launch/google-ads/OFFLINE-CONVERSION-IMPORT.md",
            ", ".join(missing),
        )
    else:
        dry = False

    async with session_scope() as session:
        pending = await gather_pending(session, args.limit)
        if not pending:
            logger.info(
                "no converted-not-uploaded subscribers with a Google click id — nothing to do"
            )
            return 0

        logger.info("%d paid conversion(s) pending upload:", len(pending))
        for p in pending:
            logger.info(
                "  user=%s  %s=%s…  value=$%.2f  order=%s",
                p["user_id"], p["click_field"], str(p["click_value"])[:12],
                p["value"], p["order_id"],
            )

        if dry:
            logger.info(
                "DRY-RUN — nothing uploaded, nothing marked. Set the creds and "
                "drop --dry-run to go live."
            )
            return 0

        try:
            ok_user_ids, errors = upload_conversions(pending)
        except Exception:
            # Surface any API / auth / network failure as a hard exit 1 so a
            # scheduler alerts; nothing was marked, so everything retries.
            logger.exception("Google Ads upload failed")
            return 1

        for msg in errors:
            logger.error("partial failure: %s", msg)

        if ok_user_ids:
            now = datetime.now(UTC)
            result = await session.execute(select(User).where(User.id.in_(ok_user_ids)))
            for user in result.scalars().all():
                user.ads_conversion_uploaded_at = now
            await session.commit()

        logger.info(
            "uploaded %d/%d conversion(s); marked %d as reported",
            len(ok_user_ids), len(pending), len(ok_user_ids),
        )
        # Hard-fail (exit 1) only if a live attempt uploaded NOTHING — that's
        # the signal worth waking a scheduler for. Any success is success.
        return 0 if ok_user_ids else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
