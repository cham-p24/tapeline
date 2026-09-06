"""Five fields come out of one cache lookup; all five must survive a miss.

THE BUG
-------
`polygon_feed.fetch_snapshots` reads five values from a single
`get_cached_bar_stats(sym)` dict (polygon_feed.py:346-358):

    week52_high, week52_low, avg_volume_30d, change_pct_5d, change_pct_1m

On a cache miss it honestly writes None for all five — that part is correct and
deliberate; an honest NULL is what makes the COALESCE guard work at all.

But only THREE of them were listed in `CACHE_DERIVED_COLUMNS`, and that tuple is
what decides whether the tick's UPDATE wraps a column in COALESCE. So every 60
seconds the two unlisted ones had their last good value overwritten with NULL,
while their three siblings from the same dict were preserved.

Measured live on 2026-09-06: 14 of 40 rows on /api/public/signals had null 5D
and 1M while change_pct_1d was populated on all 40. Both are offered as scanner
sort keys, and two public SEO landing pages sort on them — so "sort by 5D"
ranked whatever handful of rows happened to be warm that minute.

WHY THESE ARE SAFE TO COALESCE AND THE FACTORS ARE NOT
------------------------------------------------------
`_merged_factor_set`'s docstring records that the six factor columns were
briefly COALESCE'd individually and it was "subtly wrong": 158 rows carried a
score that disagreed with their own published factors, because `sub_macro`
never NULLs and overwrote while `score` was held back.

That cannot happen here. These two are display/export only — main.py,
api_v1.py, export.py — and feed nothing in the composite, so a stale value
cannot desynchronise a score from the factors published beside it.
"""

from app.services import polygon_feed
from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS, FACTOR_COLUMNS

#: Every field fetch_snapshots reads out of one get_cached_bar_stats() call.
BAR_STATS_FIELDS = (
    "week52_high",
    "week52_low",
    "avg_volume_30d",
    "change_pct_5d",
    "change_pct_1m",
)


def test_every_bar_stats_field_is_protected():
    """The regression. Three of five were listed; two were not."""
    missing = [f for f in BAR_STATS_FIELDS if f not in CACHE_DERIVED_COLUMNS]
    assert not missing, (
        f"{missing} come from the same cache lookup as the rest but are not "
        f"COALESCE-protected, so a cache miss erases them every tick"
    )


def test_the_two_that_were_missing_are_named_explicitly():
    """Pins the specific regression, so a tuple rewrite that drops exactly
    these two fails loudly rather than silently."""
    assert "change_pct_5d" in CACHE_DERIVED_COLUMNS
    assert "change_pct_1m" in CACHE_DERIVED_COLUMNS


def test_no_factor_column_is_protected():
    """The other direction, and the reason this is not just "add everything".

    COALESCE'ing a factor column desynchronises the score from the factors
    published next to it — 158 rows, off by ~3.75, within the hour. If someone
    reads this file as "protect the lot", this stops them.
    """
    overlap = [c for c in FACTOR_COLUMNS if c in CACHE_DERIVED_COLUMNS]
    assert not overlap, (
        f"{overlap} are composite inputs; COALESCE'ing them lets a row publish "
        f"a score that disagrees with its own factors"
    )
    assert "score" not in CACHE_DERIVED_COLUMNS


def test_a_cache_miss_still_writes_an_honest_null():
    """The guard only works because the miss is honest.

    If a miss ever returns a stale or invented number instead of None, COALESCE
    can never distinguish "nothing new" from "genuinely this value" — and the
    same file records what that cost: a mock's random.gauss draw once overwrote
    the whole non-sheet universe's score after every deploy.
    """
    polygon_feed._BAR_STATS_CACHE.pop("ZZNOTREAL", None)
    assert polygon_feed.get_cached_bar_stats("ZZNOTREAL") is None


def test_the_five_fields_really_do_share_one_lookup():
    """If fetch_snapshots stops reading them from one dict, the premise of this
    file is void and the grouping above is arbitrary. Checked on executable
    source so the explanation above cannot satisfy it."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(polygon_feed)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)

    assert "get_cached_bar_stats" in code
    for field in BAR_STATS_FIELDS:
        assert field in code, f"{field} is no longer read in polygon_feed"
