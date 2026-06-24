"""SEC EDGAR direct adapter — 8-K material event filings, free + fast.

Why this exists:
    The news wires (Massive, Finnhub) re-report material 8-K filings
    after they hit EDGAR — typically 5-30 minutes lag for the bigger
    items, longer for smaller filers. EDGAR itself publishes the raw
    filing the moment the filer submits, with no rate limit beyond fair-
    access (10 req/sec). For Tapeline that means surfacing material
    events 5-30 minutes earlier than the news bar would show them
    through any paid wire — and at zero marginal cost.

What we surface:
    8-K filings from the EDGAR "current filings" Atom feed
    (https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&
    type=8-K&output=atom). Each filing lists the company name, CIK,
    filing time, accession number, and a link to the filing detail page.

How we tag tickers:
    SEC publishes a CIK → ticker lookup at
    https://www.sec.gov/files/company_tickers.json (about 700 KB,
    refreshed on EDGAR's schedule). We fetch this once a day, cache it
    in memory, and use it to attach a `tickers` field to each filing.

What we DON'T do (yet):
    Parse the 8-K item codes ("Item 1.01 Material Definitive Agreement",
    "Item 2.02 Results of Operations and Financial Condition") to
    classify the filing by category. That's a follow-up — the filing
    title from EDGAR already includes the item codes for the major
    events, and a future enhancement could extract them into a
    structured category tag.

SEC fair-access requirements:
    User-Agent must identify the application + a contact email.
    Rate limit is 10 req/sec. We poll once every 5 min, so the limit
    never bites.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# SEC requests this in every request — they actively block "python-requests/..."
# default User-Agents. Identifying the app + a reachable contact email is
# fair-access compliant. Update the email if it ever changes.
_USER_AGENT = "Tapeline (tapeline.io) owner@tapeline.io"

# Endpoints
_EDGAR_CURRENT_8K_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar?"
    "action=getcurrent&type=8-K&output=atom&count=100"
)
_EDGAR_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"

# In-memory CIK → ticker map. Loaded lazily on first call to fetch_8k_filings
# and refreshed daily (the SEC file itself only changes monthly-ish, but
# 24h cache is conservative).
_CIK_TICKER_MAP: dict[str, str] = {}
_CIK_MAP_LOADED_AT: float = 0.0
_CIK_MAP_TTL_SECONDS = 86400  # 24h


async def _load_cik_ticker_map() -> dict[str, str]:
    """Fetch SEC's company_tickers.json and build a CIK → ticker lookup.

    The file is a JSON object keyed by row number, each row containing
    cik_str, ticker, title. We want zero-padded 10-digit CIK strings so
    they match the format used in the Atom feed's <id> URLs.
    Cached for 24h in memory.
    """
    global _CIK_TICKER_MAP, _CIK_MAP_LOADED_AT
    now = time.time()
    if _CIK_TICKER_MAP and (now - _CIK_MAP_LOADED_AT) < _CIK_MAP_TTL_SECONDS:
        return _CIK_TICKER_MAP

    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(_EDGAR_COMPANY_TICKERS, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("edgar.cik_map_fetch_failed")
        return _CIK_TICKER_MAP  # return stale if we have it, empty otherwise

    new_map: dict[str, str] = {}
    for row in data.values() if isinstance(data, dict) else []:
        cik = str(row.get("cik_str") or "").strip()
        ticker = str(row.get("ticker") or "").strip().upper()
        if cik and ticker:
            new_map[cik.zfill(10)] = ticker
    if new_map:
        _CIK_TICKER_MAP = new_map
        _CIK_MAP_LOADED_AT = now
        logger.info("edgar.cik_map_loaded count=%d", len(new_map))
    return _CIK_TICKER_MAP


# Atom feed XML namespaces — EDGAR uses both the standard Atom ns and a
# custom <id> URL format we parse below.
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

# CIK appears in the <id> URL like:
#   https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001318605&...
# We extract the zero-padded 10-digit string.
_CIK_FROM_URL_RE = re.compile(r"CIK=(\d{1,10})", re.IGNORECASE)


async def fetch_8k_filings() -> list[dict[str, Any]]:
    """Pull the most recent 8-K filings from EDGAR's current-filings Atom feed.

    Returns one dict per filing:
        {
            "id":           str,    # EDGAR accession number, used as NewsItem.id
            "title":        str,    # "8-K — [filing description]"
            "publisher":    "SEC EDGAR",
            "url":          str,    # link to the filing detail page
            "published_at": datetime (UTC, timezone-aware),
            "tickers":      [str],  # resolved via CIK → ticker map; may be empty
            "description":  str | None,  # short summary from Atom <summary>
        }

    Sorted newest-first by published_at. Returns [] on any error so the
    caller can continue without blowing up the worker tick.
    """
    cik_map = await _load_cik_ticker_map()

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/atom+xml, application/xml, text/xml",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(_EDGAR_CURRENT_8K_ATOM, headers=headers)
            r.raise_for_status()
            xml_text = r.text
    except Exception:
        logger.exception("edgar.8k_fetch_failed")
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.exception("edgar.8k_parse_failed")
        return []

    rows: list[dict[str, Any]] = []
    for entry in root.findall("a:entry", _ATOM_NS):
        try:
            row = _parse_entry(entry, cik_map)
            if row is not None:
                rows.append(row)
        except Exception:
            logger.exception("edgar.entry_parse_skipped")
            continue

    # Sort newest first — the feed is already approximately ordered but
    # we don't trust it (EDGAR sometimes reorders during high-load minutes).
    rows.sort(key=lambda r: r["published_at"], reverse=True)
    return rows


def _parse_entry(entry: ET.Element, cik_map: dict[str, str]) -> dict[str, Any] | None:
    """Convert one <entry> element into our normalized dict shape."""
    title_el = entry.find("a:title", _ATOM_NS)
    link_el = entry.find("a:link", _ATOM_NS)
    id_el = entry.find("a:id", _ATOM_NS)
    updated_el = entry.find("a:updated", _ATOM_NS)
    summary_el = entry.find("a:summary", _ATOM_NS)

    title = (title_el.text if title_el is not None else "").strip()
    url = (link_el.attrib.get("href") if link_el is not None else "").strip()
    raw_id = (id_el.text if id_el is not None else "").strip()
    updated = (updated_el.text if updated_el is not None else "").strip()
    summary = (summary_el.text if summary_el is not None else "").strip() or None

    if not title or not url or not updated:
        return None

    # Parse the ISO-8601 timestamp EDGAR gives us (e.g. "2026-05-16T14:32:11-04:00").
    try:
        published_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        else:
            published_at = published_at.astimezone(UTC)
    except ValueError:
        return None

    # Extract CIK from the entry's <id> URL or from the link href.
    cik_str = ""
    m = _CIK_FROM_URL_RE.search(raw_id) or _CIK_FROM_URL_RE.search(url)
    if m:
        cik_str = m.group(1).zfill(10)

    ticker = cik_map.get(cik_str, "")
    tickers = [ticker] if ticker else []

    # EDGAR accession numbers look like "0001628280-26-012345" — those make
    # great stable IDs for our NewsItem table. Fall back to a hash of the
    # raw_id if we can't extract one.
    accession = ""
    am = re.search(r"(\d{10}-\d{2}-\d{6})", raw_id)
    if am:
        accession = am.group(1)
    item_id = accession or raw_id[-79:]  # cap at NewsItem.id String(80)

    return {
        "id":           item_id,
        "title":        title[:300],         # NewsItem.title is String(300)
        "publisher":    "SEC EDGAR",
        "url":          url[:500],            # NewsItem.url is String(500)
        "published_at": published_at,
        "tickers":      tickers,
        "description":  summary,
    }


async def refresh_8k_into_news_items() -> dict[str, int]:
    """Pull the latest 8-K filings and INSERT new ones into the news_items table.

    Returns counts so the worker can log how many new rows landed.
    Idempotent — duplicate IDs are skipped via the primary-key constraint
    (NewsItem.id is the EDGAR accession number, which never changes).
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db import session_scope
    from app.models import NewsItem

    filings = await fetch_8k_filings()
    if not filings:
        return {"fetched": 0, "inserted": 0}

    async with session_scope() as session:
        # Single bulk pre-check to skip rows we already have — saves N round-trips
        ids = [f["id"] for f in filings]
        existing_q = await session.execute(
            select(NewsItem.id).where(NewsItem.id.in_(ids))
        )
        existing_ids = {row[0] for row in existing_q.all()}

        inserted = 0
        for f in filings:
            if f["id"] in existing_ids:
                continue
            row = NewsItem(
                id=f["id"],
                title=f["title"],
                publisher=f["publisher"],
                author=None,
                published_at=f["published_at"],
                url=f["url"],
                description=(f["description"] or "")[:1000] if f["description"] else None,
                tickers=",".join(f["tickers"])[:2000],
                sentiment=None,
            )
            session.add(row)
            inserted += 1

        try:
            await session.commit()
        except IntegrityError:
            # Race against another worker — let it through, log, move on.
            await session.rollback()
            logger.warning("edgar.insert_race_recovered")
            return {"fetched": len(filings), "inserted": 0}

    logger.info("edgar.refreshed fetched=%d inserted=%d", len(filings), inserted)
    return {"fetched": len(filings), "inserted": inserted}
