"""The citable export must enumerate its own restatements.

`/api/scorecard.csv` and `/api/scorecard.json` are designed to be read
DETACHED from the site and cited. Their metadata promised:

    "Entries are written once and never edited, re-ranked, back-filled or
     deleted."

On 2026-08-25 every scored row was rewritten: `price_at_flag` had been
recorded from the vendor's last trade INCLUDING extended hours rather than
the official close (the freeze runs at 21:15 UTC = 17:15 ET), while
`spy_change_pct_1d` always came from SPY's official daily-bar closes — so the
two legs of `alpha_vs_spy` were on different bases, and ~34% of rows sat
2-18% off.

A consumer holding an older copy of this file has no other channel through
which to learn the numbers moved. A note on a web page they may never load
does not reach them. So the exceptions belong in the artefact.
"""
from datetime import date

import pytest

from app.services import scorecard_export as ex


def _meta() -> dict:
    return ex.dataset_meta(
        row_count=688, session_count=72, delay_days=7,
        first_date=date(2026, 5, 11), last_date=date(2026, 8, 21),
        cutoff=date(2026, 8, 18),
    )


def test_the_export_enumerates_its_restatements():
    meta = _meta()
    assert "restatements" in meta, (
        "the citable export does not disclose that published rows were "
        "rewritten — a consumer with an older copy cannot learn it"
    )
    assert meta["restatements"], "the 2026-08-25 restatement is not recorded"


def test_the_append_only_promise_no_longer_overclaims():
    """The old wording said entries are 'never edited'. That is false as of
    2026-08-25 and cannot be left standing in a machine-readable dataset."""
    text = _meta()["append_only"]
    assert "never edited" not in text, (
        "the export still claims entries are never edited, which the "
        "2026-08-25 restatement makes false"
    )
    # The narrower promise that IS still true must survive — otherwise the
    # fix has thrown away the guarantee instead of qualifying it.
    assert "never re-ranked, back-filled or deleted" in text
    assert "restatements" in text, (
        "the promise does not point the reader at the enumerated exceptions"
    )


def test_each_restatement_is_self_describing():
    """A bare date is not a disclosure. Someone reading this file years later,
    with no access to the repo or the site, must be able to tell what changed,
    what did not, why, and which way it moved."""
    for r in ex.RESTATEMENTS:
        for key in ("date", "scope", "fields_changed", "fields_unchanged",
                    "reason", "remedy", "effect_on_summary"):
            assert r.get(key), f"restatement {r.get('date')!r} is missing {key}"
        date.fromisoformat(r["date"])  # raises if not a real ISO date


def test_the_2026_08_25_entry_names_the_actual_cause():
    r = next(x for x in ex.RESTATEMENTS if x["date"] == "2026-08-25")
    assert "extended-hours" in r["reason"]
    assert "21:15 UTC" in r["reason"]
    # The identity columns must be stated as UNCHANGED — that distinction is
    # the whole reason the record is still worth anything.
    for col in ("as_of", "symbol", "rank", "score_at_flag"):
        assert col in r["fields_unchanged"]
    # Direction disclosed even though it is unfavourable.
    assert "against Tapeline" in r["effect_on_summary"]


@pytest.mark.asyncio
async def test_restatements_survive_into_the_json_export():
    """Metadata that exists in the dict but never reaches the file is not a
    disclosure. The JSON renderer must carry it through verbatim."""
    import json

    async def _no_rows():
        return
        yield  # pragma: no cover - makes this an async generator

    meta = _meta()
    body = "".join([chunk async for chunk in ex.iter_json(meta, _no_rows())])
    parsed = json.loads(body)
    assert parsed["meta"]["restatements"][0]["date"] == "2026-08-25", (
        "the restatement list is dropped between dataset_meta and the "
        "rendered JSON file"
    )
