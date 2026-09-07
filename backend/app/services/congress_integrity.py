"""One filter, applied everywhere a congressional disclosure is published.

WHY THIS EXISTS — measured against production on 2026-09-06
-----------------------------------------------------------
`congress_trades` holds 338,015 rows. Every one of them is fabricated.

    politician                  rows   first written  last written
    Dan Crenshaw               42,951   2026-05-03     2026-07-18
    Ro Khanna                  42,872   2026-05-03     2026-07-18
    Debbie Wasserman Schultz   42,670   2026-05-03     2026-07-18
    Tommy Tuberville           42,456   2026-05-03     2026-07-18
    Rick Scott                 42,401   2026-05-03     2026-07-18
    Josh Gottheimer            42,280   2026-05-03     2026-07-18
    Mark Kelly                 41,546   2026-05-03     2026-07-18
    Nancy Pelosi               40,839   2026-05-03     2026-07-18

Eight politicians, ~42,000 disclosures each. No member of Congress files
43,000 trades. These are `mock_feed.fetch_congress_trades` rows — randomly
generated trades attributed to real, named, living people — and they were
persisted to production until `_mock_writes_enabled()` began gating the write
path on `app_env != "production"`. Nothing has been written since 2026-07-18,
and no real source has ever written a row.

They were still being SERVED. `routers/congress.py` returned them to Premium
subscribers as disclosures, its free preview returned three of them to every
signed-in account — under a comment saying the preview exists "to prove the
feed is real and populated" — and `services/alerts.py` could email a user to
say a named politician had traded a named stock. All of that is a false
statement of fact about identifiable real people, which is the most serious
class of defect this product can produce. The same reasoning retired the
crypto-collision rows in migration 0063: worse than serving nothing.

WHY A DATE AND NOT A NAME LIST
------------------------------
Filtering on the eight names would be wrong in both directions. Those are real
politicians who really do file disclosures, so a genuine feed carrying them
would be silently suppressed; and a mock roster that gained a ninth name would
slip straight through.

The write path is what separates the two populations, and it closed on
2026-07-18. Every fabricated row predates that; anything a real source writes
from now on is after it. So the cutoff is a fact about when fabrication
stopped, not a guess about content — and it needs no maintenance when a real
feed is finally wired, because real rows simply fall on the other side of it.

NOT DELETED, DELIBERATELY
-------------------------
This filter suppresses; it does not purge. Deleting 338,015 production rows is
an operator decision with no undo, and suppressing them removes the harm
without taking it. If the founder wants them gone, that is a separate, explicit
call — see docs/TODO.md.

WHEN A REAL FEED ARRIVES
------------------------
`settings.smart_money_congress_csv_url` already points at the signal-system
workbook's SMART MONEY & CONGRESS tab, and `sheet_feed` already parses it — but
it only increments `sub_smart_money` by per-ticker appearance count and never
stores the individual trades as `CongressTrade` rows. Wiring that is what makes
the Premium claim true again. Until then the feed is honestly empty, and the
marketing says so.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ColumnElement

from app.models import CongressTrade

#: The instant fabricated writes stopped. Rows created strictly before this are
#: `mock_feed` output and must never be published. Measured: the newest
#: fabricated row in production was written 2026-07-18T14:53:19Z.
FABRICATION_STOPPED_AT = datetime(2026, 7, 19, tzinfo=UTC)


def is_publishable() -> ColumnElement[bool]:
    """SQLAlchemy predicate selecting only disclosures we can stand behind.

    Use this in EVERY query whose rows reach a user — the feed, the preview,
    the counts beside them, and the alert evaluator. A count that includes
    fabricated rows is as much a false claim as the rows themselves.
    """
    return CongressTrade.created_at >= FABRICATION_STOPPED_AT
