"""Signup-attribution normalisers shared by the email and OAuth signup paths.

Both `routers/auth.py` (email signup) and `routers/oauth.py` (Google /
Microsoft / Apple callback) write the same first-touch attribution columns
onto a brand-new User row: signup_utm_*, signup_gclid/gbraid/wbraid,
signup_referrer_host and signup_landing_path. The landing path needs real
normalisation (not just a length cap) and the two routers must agree on it
exactly, or the same page would aggregate into different buckets depending
on which button the visitor happened to click.

This module exists so that contract has ONE home. `routers/oauth.py`
deliberately avoids importing from `routers/auth.py` (see its
`_generate_referral_code` note) — a services-level module sidesteps that.
"""
from __future__ import annotations

# Matches users.signup_landing_path (String(200)) in models/user.py.
LANDING_PATH_MAX = 200


def normalise_landing_path(raw: str | None) -> str | None:
    """Normalise the client-supplied first-touch landing path, or None.

    Contract (mirrors frontend lib/utm.ts:normaliseLandingPath so client and
    server agree on the bucket a page falls into):
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
        path = path[:LANDING_PATH_MAX]
        return path or None
    except Exception:
        return None
