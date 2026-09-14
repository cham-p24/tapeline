"""Send the week's SEO digest to the founder's Telegram, if no run has yet.

Run on the Fly machine by .github/workflows/seo-weekly-digest.yml:

    python -m app.scripts.seo_weekly_digest

Safe to run any number of times: seo_health.run_weekly_digest claims the ISO
week in job_period_claims before it crawls, and sends at most once per week.
Exits 1 when a run failed to send, or sent without recording it, so the
workflow run shows red; every other outcome exits 0.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.services.seo_health import DigestOutcome, run_weekly_digest

_RED = {DigestOutcome.FAILED, DigestOutcome.SENT_UNRECORDED}


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # The Telegram send URL carries the bot token, and httpx logs every request
    # URL at INFO. This output lands in Actions logs on a PUBLIC repository, where
    # the vendor key leaked 1,086 times on 2026-08-27 by the same route.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main() -> int:
    outcome = await run_weekly_digest()
    print(f"seo_digest.outcome={outcome.value}", flush=True)
    return 1 if outcome in _RED else 0


if __name__ == "__main__":
    configure_logging()
    sys.exit(asyncio.run(main()))
