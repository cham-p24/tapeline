"""Send the week's SEO digest to the founder's Telegram, if no run has yet.

Run on the Fly machine by .github/workflows/seo-weekly-digest.yml:

    python -m app.scripts.seo_weekly_digest

Safe to run any number of times: seo_health.run_weekly_digest claims the ISO
week in job_period_claims before it crawls, and sends at most once per week.
Exits 1, with a GitHub Actions ::error annotation saying what to do, when a run
needs a person: it failed to send, sent without recording it, could not read
the sitemap, or may have delivered without knowing which. Every other outcome
exits 0. IN_FLIGHT also prints a ::notice, so a green re-dispatch that sent
nothing is not mistaken for a send.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.services.seo_health import DIGEST_JOB, DigestOutcome, run_weekly_digest

_RED = {
    DigestOutcome.FAILED,
    DigestOutcome.SENT_UNRECORDED,
    DigestOutcome.SEND_UNKNOWN,
    DigestOutcome.SITEMAP_UNAVAILABLE,
}

#: What the workflow log says for an outcome that needs a look. No chat id, no
#: token: this output is public.
ANNOTATIONS: dict[DigestOutcome, str] = {
    DigestOutcome.FAILED: (
        "::error title=SEO digest not sent::Nothing was sent and the week was "
        "released. The next scheduled run retries; the cause is in the log above."
    ),
    DigestOutcome.SENT_UNRECORDED: (
        "::error title=SEO digest sent but not recorded::The digest went out but "
        f"its {DIGEST_JOB} claim could not be completed. Do not re-dispatch."
    ),
    DigestOutcome.SEND_UNKNOWN: (
        "::error title=SEO digest may have been delivered::The send failed after "
        "Telegram may have received it, so the week is kept as sent and no run "
        "will send it again. Check the founder's Telegram BEFORE re-dispatching. "
        f"Only if it did not arrive, delete the job_period_claims row for "
        f"job={DIGEST_JOB} and this week (period in the log above), then re-dispatch."
    ),
    DigestOutcome.SITEMAP_UNAVAILABLE: (
        "::error title=Sitemap unavailable::The sitemap could not be read, so no "
        "URL was checked and no digest was sent: a '0 broken' report would have "
        "been false. The week was released; the next run retries."
    ),
    DigestOutcome.IN_FLIGHT: (
        "::notice title=SEO digest in flight elsewhere::Another run holds this "
        "week's claim, so this run sent nothing. The claim's owner, age and "
        "retryable_after are in the log above; a re-dispatch before "
        "retryable_after also sends nothing."
    ),
}


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
    if outcome in ANNOTATIONS:
        print(ANNOTATIONS[outcome], flush=True)
    return 1 if outcome in _RED else 0


if __name__ == "__main__":
    configure_logging()
    sys.exit(asyncio.run(main()))
