"""Outbound email must report the record the same way the website does.

Two places in email.py computed `sum(alpha) / len(scored)` — an arithmetic
mean, with no outlier filter — and rendered it as "Average alpha vs SPY" in the
weekly digest and "avg next-day alpha" in win-back emails.

On the live record that mean reads **+3.58%** while the **median** pick is
**-0.272%**. A handful of large winners drag the average positive while the
typical pick trails SPY. So subscribers were being told the picks beat the
market, by email, by the one company whose entire pitch is that it does not
misstate things.

/api/scorecard has always done this properly: partition out entries beyond
±50% (vendor-data artefacts), then report the MEDIAN. Having a second
methodology in the email path meant the website and the email disagreed about
the same picks — the identical defect as the two composite definitions in
score.py/polygon_feed.py, and fixed the same way: one helper, callers adapt.

A short rolling window makes a mean MORE outlier-sensitive, not less, so the
weekly digest was the worst place for it.
"""
from __future__ import annotations

import inspect
import re

from app.routers.scorecard import _summary_stats
from app.services import email as email_mod


def test_no_arithmetic_mean_of_alpha_survives_in_email():
    """The exact shape that shipped, banned by pattern.

    Source-level by necessity — the alternative is standing up a full digest
    render against seeded scorecard rows for a property that is really about
    which formula is written down. Narrow on purpose: it pins the specific
    computation, not "anything containing the word average".
    """
    src = inspect.getsource(email_mod)
    means = re.findall(
        r"sum\(\s*p\.alpha_vs_spy[^)]*\)\s*/\s*len\(", src
    )
    assert not means, (
        f"{len(means)} arithmetic mean(s) of alpha_vs_spy are back in email.py. "
        f"The mean is +3.58% on a record whose median is -0.272%; emailing it "
        f"claims the picks beat SPY when they do not. Use "
        f"scorecard._summary_stats(...)['median_alpha_vs_spy']."
    )


def test_the_email_reads_the_shared_summary_helper():
    """Not merely 'not a mean' — the SAME source the public API uses."""
    src = inspect.getsource(email_mod)
    assert "_summary_stats" in src, (
        "email.py no longer routes through the scorecard summary helper, so the "
        "website and the email can drift apart on the same record again"
    )
    assert src.count('median_alpha_vs_spy') >= 2, (
        "both the weekly digest and the win-back payload should read the median"
    )


def test_no_label_says_average_alpha():
    """A correct number under the wrong word is still a false statement.

    The win-back builder printed "avg next-day alpha" while its fallback key
    list already preferred `median_alpha_vs_spy` — so on the router shape it
    was printing the median labelled as the mean.
    """
    src = inspect.getsource(email_mod)
    for banned in ("Average alpha vs SPY", "avg next-day alpha"):
        assert banned not in src, (
            f"email copy still says {banned!r}; the value it renders is the median"
        )


def test_the_helper_excludes_outliers_and_returns_a_median():
    """Guards the thing email.py now depends on.

    If _summary_stats ever stopped filtering or started returning a mean under
    the same key, this fix would silently undo itself.
    """
    from app.routers.scorecard import _OUTLIER_PCT_THRESHOLD

    class _E:
        def __init__(self, alpha, chg=None):
            self.alpha_vs_spy = alpha
            self.change_pct_1d_after = chg if chg is not None else alpha

    # Four ordinary entries plus one absurd vendor artefact.
    entries = [_E(-1.0), _E(-0.5), _E(0.5), _E(1.0), _E(900.0)]
    out = _summary_stats(entries)

    assert out["entries_excluded_outliers"] >= 1, (
        f"the ±{_OUTLIER_PCT_THRESHOLD}% outlier filter is not excluding a 900% entry"
    )
    median = out["median_alpha_vs_spy"]
    assert median is not None and -1.0 <= median <= 1.0, (
        f"median {median} is outside the clean entries' range — the 900% "
        f"artefact is still reaching the aggregate"
    )
