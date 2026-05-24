"""IndexNow integration — push new + updated URLs to Bing, Yandex, and
their syndication partners with no GCP credentials, no Webmaster Tools
sign-up, no rate-limit headaches.

WHY: Google indexing is slow (often 1-4 weeks for new programmatic pages
in a low-authority site). IndexNow is the Microsoft/Yandex equivalent
that ships in ~hours. Bing+Yandex+DuckDuckGo+Seznam combined are ~10-15%
of US search share — meaningful long-tail traffic even if Google still
dominates. Free, no auth, no quotas in practice; you POST a JSON list
of URLs and the search engines pick them up.

PROTOCOL: https://www.indexnow.org/documentation
  1. Pick a key (any 8-128 char string of [a-z0-9-]).
  2. Host the key as plaintext at https://<host>/<key>.txt — proves
     domain ownership.
  3. POST { host, key, keyLocation, urlList } to https://api.indexnow.org/indexnow
     OR to a participating engine's endpoint (bing.com, yandex.com).
     The engine fans out to all participants automatically.
  4. Receive 200 OK = accepted into the crawl queue. 202 = batch
     accepted but not yet validated. 400/422 = malformed; 403 = key
     mismatch; 429 = rate-limited (rare).

KEY: 7b3f8c5d2a9e4f1b6c8d0a3e5f7b9c2d
  Hosted at frontend/public/7b3f8c5d2a9e4f1b6c8d0a3e5f7b9c2d.txt and
  served by Vercel static-asset handler. Stable — DO NOT change unless
  re-verifying via fresh upload.

USAGE: worker calls submit_urls([...]) once a day with the URLs that
changed since the last run. Empty list = no-op. Failures log and
swallow — IndexNow is fire-and-forget, not a critical path.

ENV: indexnow_api_key (defaults to the hex above so this works in dev
without any config). Override via env var if rotating.
"""
from __future__ import annotations

import logging
from typing import Iterable

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
DEFAULT_HOST = "tapeline.io"

# Per-engine endpoint as a fallback if the primary aggregator is down.
# The aggregator fans out anyway, so this is rarely needed — kept here
# for resilience.
BING_ENDPOINT = "https://www.bing.com/indexnow"

# IndexNow caps batches at 10,000 URLs per POST. We chunk for safety,
# but realistically Tapeline will never submit more than a few hundred
# URLs in a single day.
MAX_URLS_PER_BATCH = 10_000


def _api_key() -> str:
    """Return the configured IndexNow key, falling back to the static one."""
    return (
        getattr(settings, "indexnow_api_key", None)
        or "7b3f8c5d2a9e4f1b6c8d0a3e5f7b9c2d"
    )


def _key_location(host: str) -> str:
    return f"https://{host}/{_api_key()}.txt"


async def submit_urls(
    urls: Iterable[str],
    host: str = DEFAULT_HOST,
) -> dict:
    """Submit a batch of URLs to IndexNow.

    Returns a dict with `submitted`, `accepted` (HTTP 200), `queued`
    (HTTP 202), and `failed` counts. Logs on failure, never raises —
    this is a fire-and-forget channel.

    All URLs must be on `host` per IndexNow's same-domain rule.
    Cross-domain URLs in a single batch cause 422 rejection.
    """
    url_list = sorted({u for u in urls if u and isinstance(u, str)})
    if not url_list:
        return {"submitted": 0, "accepted": 0, "queued": 0, "failed": 0}

    # Filter to URLs on this host — IndexNow rejects mixed-domain batches.
    same_host = [u for u in url_list if f"//{host}/" in u or u.startswith(f"https://{host}")]
    if len(same_host) != len(url_list):
        logger.warning(
            "indexnow.cross_domain_dropped kept=%d dropped=%d",
            len(same_host), len(url_list) - len(same_host),
        )
    if not same_host:
        return {"submitted": 0, "accepted": 0, "queued": 0, "failed": 0}

    accepted = 0
    queued = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for batch_start in range(0, len(same_host), MAX_URLS_PER_BATCH):
            batch = same_host[batch_start : batch_start + MAX_URLS_PER_BATCH]
            payload = {
                "host": host,
                "key": _api_key(),
                "keyLocation": _key_location(host),
                "urlList": batch,
            }
            try:
                r = await client.post(INDEXNOW_ENDPOINT, json=payload)
                if r.status_code == 200:
                    accepted += len(batch)
                    logger.info(
                        "indexnow.accepted host=%s count=%d", host, len(batch),
                    )
                elif r.status_code == 202:
                    queued += len(batch)
                    logger.info(
                        "indexnow.queued host=%s count=%d", host, len(batch),
                    )
                else:
                    failed += len(batch)
                    logger.warning(
                        "indexnow.rejected host=%s status=%d body=%s",
                        host, r.status_code, r.text[:300],
                    )
            except Exception:
                failed += len(batch)
                logger.exception("indexnow.exception host=%s batch_size=%d", host, len(batch))

    return {
        "submitted": len(same_host),
        "accepted": accepted,
        "queued": queued,
        "failed": failed,
    }


async def submit_url(url: str, host: str = DEFAULT_HOST) -> bool:
    """Single-URL convenience for tight loops (e.g. blog publish hook).

    Returns True if IndexNow accepted or queued the URL.
    """
    result = await submit_urls([url], host=host)
    return (result["accepted"] + result["queued"]) > 0
