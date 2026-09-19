"""What we say about CRYPTO freshness is what the rows actually hold.

MEASURED IN PRODUCTION, 2026-09-17 22:45 UTC (read-only)
-------------------------------------------------------
118 crypto rows, every one priced. Of them:

* 51 carried a price written more than 25 hours earlier,
* 39 more than two days earlier,
* 23 more than four days earlier,
* the oldest was written 2026-09-13 13:53 UTC - four days and nine hours.

The price itself is a completed UTC-day close, so a day is added on top of the
write age. The refresh is one detached job per worker process, latched at 24h
and stamped before dispatch, so a failed run waits another day; a pair that
drops out of the 120 the job fetches keeps its last close until it returns.

So "crypto updates once a day" was true of the JOB and false of the DATA on
43% of pairs, on six surfaces: the in-app scanner, the press page twice, the
MCP tool description, the MCP per-ticker note and the product-update email.
`services/freshness.py` and `frontend/lib/freshness.ts` now carry the sentence,
and this file pins that the two sides agree, that the sentence discloses the
tail, and that no surface goes back to a bare daily claim.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.services.freshness import (
    CRYPTO_CADENCE_PHRASE,
    CRYPTO_CADENCE_SENTENCE,
)

_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _ROOT / "frontend"
_BACKEND = _ROOT / "backend"


def _frontend_string(name: str) -> str:
    """A `export const NAME = "..." + "...";` value from lib/freshness.ts."""
    src = (_FRONTEND / "lib" / "freshness.ts").read_text(encoding="utf-8")
    # Only string literals joined by `+`, so a semicolon inside the copy
    # ("...once a day; a pair...") cannot truncate the value.
    body = re.search(
        rf'export const {name}\s*=\s*((?:\s*"[^"]*"\s*\+?)+)\s*;',
        src,
    )
    assert body, f"{name} is not exported from frontend/lib/freshness.ts"
    return "".join(re.findall(r'"([^"]*)"', body.group(1)))


def test_both_sides_say_the_same_thing_about_crypto() -> None:
    """One fact, two codebases. Mutation: change either side alone."""
    assert _frontend_string("CRYPTO_CADENCE_SENTENCE") == CRYPTO_CADENCE_SENTENCE
    assert _frontend_string("CRYPTO_CADENCE_PHRASE") == CRYPTO_CADENCE_PHRASE


def test_the_sentence_discloses_the_tail_not_just_the_job() -> None:
    """A daily job does not mean day-old data: 23 of 118 pairs were four days
    old. Mutation: the old "Crypto prices and scores update once a day."."""
    assert "several days" in CRYPTO_CADENCE_SENTENCE.lower()
    assert "several days" in CRYPTO_CADENCE_PHRASE.lower()


def test_the_mcp_server_serves_the_sentence_for_a_crypto_row() -> None:
    """The keyless MCP server answers agents, which quote it verbatim.
    Mutation: its own "Daily price (crypto updates once a day)." string."""
    src = (_BACKEND / "app" / "routers" / "mcp.py").read_text(encoding="utf-8")
    assert "CRYPTO_CADENCE_SENTENCE" in src
    assert "CRYPTO_CADENCE_PHRASE" in src
    assert "crypto updates once a day" not in src


#: Every surface that states a crypto cadence, and the source of truth it must
#: use. A bare "once a day" here is the claim production contradicts.
_SURFACES = (
    "frontend/app/app/scanner/page.tsx",
    "frontend/app/press/page.tsx",
    "backend/app/routers/mcp.py",
    # The file AI assistants read about us. It still said "updated once a day"
    # twice after #872, because it was not in this list (found 2026-09-19).
    "frontend/public/llms.txt",
)

#: NOT fixed here, and deliberately so. The product-update email carrying
#: "Crypto is in: more than 100 pairs, updated once a day." was SENT on
#: 2026-09-15; there is no copy to correct in front of a reader, and any change
#: to a customer email or a send path needs the founder's explicit yes each
#: time. Whether those recipients get a correction is the founder's call, not a
#: copy fix. Pinned so the exception stays one known line instead of growing.
_SENT_EMAIL = ("backend/app/services/email.py", "updated once a day")


def test_the_sent_email_is_the_only_place_left_saying_it() -> None:
    """Mutation: a second surface quietly joins the exception."""
    path, phrase = _SENT_EMAIL
    hits = [
        line.strip()
        for line in (_ROOT / path).read_text(encoding="utf-8").splitlines()
        if phrase in line and ("crypto" in line.lower() or "coin" in line.lower())
    ]
    assert len(hits) == 1, f"expected exactly one sent-email line, found {hits}"


def test_no_surface_claims_crypto_is_only_a_day_old() -> None:
    """Any line that puts crypto and a daily cadence together must also say
    the tail is longer, or take the wording from the constant.

    Mutation: any of the four surfaces reverted to its pre-fix wording."""
    offenders: list[str] = []
    for rel in _SURFACES:
        # Comments are dropped BEFORE the scan, on both sides of the rule: a
        # comment must neither be reported as copy nor excuse the copy beside
        # it. Mutation-tested - with comments left in, reverting the MCP note
        # was excused by the comment above it that explains the fix.
        numbered = [
            (n, line)
            for n, line in enumerate((_ROOT / rel).read_text(encoding="utf-8").splitlines(), 1)
            if not re.match(r"\s*(#|//|/\*|\*)", line)
        ]
        for index, (number, line) in enumerate(numbered):
            low = line.lower()
            if "crypto" not in low and "coin" not in low:
                continue
            if not re.search(r"once a day|updated daily|a daily price", low):
                continue
            window = "\n".join(
                text for _, text in numbered[max(0, index - 3):index + 4]
            )
            if "several days" in window.lower() or "CRYPTO_CADENCE" in window:
                continue
            offenders.append(f"{rel}:{number}: {line.strip()[:90]}")
    assert not offenders, "crypto cadence stated without its tail:\n" + "\n".join(offenders)
