"""Embed impression counter — one AGGREGATED row per (day, host, symbol, surface).

WHY THIS TABLE EXISTS
---------------------
Tapeline ships two embeddable surfaces whose entire point is to be rendered on
*someone else's* site:

  - `/badge/{SYMBOL}`        — shields.io-style SVG, dropped into GitHub READMEs
  - `/embed/score/{SYMBOL}`  — iframe widget, dropped into blogs / Substacks

Both were completely uninstrumented. Every render was an invisible brand
impression: we could not tell whether the embed loop works at all, which sites
carry us, or which tickers people actually embed. `/embed/score` even carried a
comment promising referrers would be "aggregated later in analytics" — never
implemented. This table is that implementation.

SHAPE: AGGREGATED, NOT AN EVENT LOG
-----------------------------------
These are hotlinked images. A single popular README can fire thousands of
requests a day, so a row-per-request event log (the `cap_events` shape) would be
the wrong trade. Instead one row per (day, host, symbol, surface) bucket is
INCREMENTED — bounded by the number of distinct embedding sites, not by traffic.
The unique constraint is what makes the increment safe under concurrency.

PRIVACY (the reason this is hostname-only)
------------------------------------------
`host` stores the embedding site's HOSTNAME ONLY, never the full referring URL.
Same posture as `users.signup_referrer_host`: a referring URL's path/query can
carry a search term, a document title, a session id, or an account handle from
a third-party site. We store `blog.example.com`, never
`blog.example.com/u/jsmith?token=…`. Normalisation + the length cap live in
`services/embed_impressions.normalize_embed_host`; the String(100) column is the
structural backstop.

COUNTS ARE DIRECTIONAL, NOT EXACT — DO NOT "FIX" THE DISCREPANCY
----------------------------------------------------------------
The badge response is CDN-cached (`s-maxage=60, stale-while-revalidate=300`) and
the iframe page is served from Next's cache too. A render served from cache never
reaches our origin and is therefore never counted. Real impressions will always
exceed this table's totals, by a factor that varies with each embedding page's
traffic shape. That is the intended trade: cheap embeds beat exact counts. Use
these numbers for RANKING (which host, which symbol, which trend) and never as
an absolute impression count — and do not add a cache-busting param or a
client-side beacon to "reconcile" them.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# The two embeddable surfaces. Validated centrally (services/embed_impressions)
# so a typo at a call site can never fragment the dataset into a third bucket.
EMBED_SURFACES: frozenset[str] = frozenset({"badge", "iframe"})

# Hostname cap. Matches users.signup_referrer_host's String(100) — a real
# hostname is far shorter, so this only ever truncates junk.
MAX_HOST_LEN = 100


class EmbedImpression(Base):
    __tablename__ = "embed_impressions"
    __table_args__ = (
        # The bucket identity. This constraint is load-bearing: the recorder
        # does UPDATE-then-INSERT-on-miss, and relies on the INSERT failing
        # (IntegrityError) when a concurrent request created the same bucket
        # first, at which point it retries the increment.
        UniqueConstraint(
            "day", "host", "symbol", "surface", name="uq_embed_impression_bucket"
        ),
        # The admin readout's two roll-ups are "last N days by host" and
        # "last N days by symbol"; both start with a day-range scan.
        Index("ix_embed_impressions_day_host", "day", "host"),
        Index("ix_embed_impressions_day_symbol", "day", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # UTC day bucket. Deliberately a DATE, not a timestamp: the whole point of
    # the table is that intra-day precision is neither available (CDN caching)
    # nor useful (the question is "which sites, trending which way").
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Embedding site's hostname — HOSTNAME ONLY, lowercased, `www.` stripped.
    # Never a path, never a query string. See the module docstring.
    host: Mapped[str] = mapped_column(String(MAX_HOST_LEN), nullable=False)

    # The embedded ticker. Not an FK: an embed can outlive a ticker leaving the
    # universe, and this is an analytics trail, not a relational fact.
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)

    # One of EMBED_SURFACES.
    surface: Mapped[str] = mapped_column(String(8), nullable=False)

    # Origin-observed renders in this bucket. Under-counts by the CDN hit rate
    # (see module docstring) — directional, never exact.
    impressions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
