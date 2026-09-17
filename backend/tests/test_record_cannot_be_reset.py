"""No endpoint can delete, re-rank or silently rewrite a recorded scorecard entry.

The public record says each trading day's top 10 is recorded at the close and
entries are not re-ranked or deleted. Until this file, that sentence depended
on nobody calling POST /api/admin/scorecard/reset: a 2026-05-10 pre-launch
cleanup that dropped EVERY row (`wipe_all=true`) or every row matching a
bad-data predicate, with any admin session or the X-Admin-Key header.

Production on 2026-09-18: daily_scorecard ids run 81..930 with no gaps (850
rows, 85 sessions of ten, the sequence at 930), the first surviving row is
2026-05-11, and 9 rows still match the endpoint's own "bad" predicate. So ids
1-80 (eight sessions of ten) were deleted before the record starts, and nothing
has been deleted since. The endpoint is gone rather than guarded because
nothing needs it: tests seed and clean their own rows through the ORM.

What remains, and is pinned here:
  1. The route does not exist, and a call to it moves no row.
  2. No write-method route anywhere in the app references the record tables or
     the jobs that write them.
  3. No code under app/ deletes, truncates or re-ranks the table; the only
     writers of the value columns are the back-check (pending rows only) and
     rederive_scorecard.
  4. No migration rewrites the table except 0034, already disclosed as the
     2026-06-15 restatement.
  5. rederive_scorecard, the one documented correction path, refuses to write
     unless a dated restatement that names every column it writes is already in
     scorecard_export.RESTATEMENTS, and only for rows recorded before that date.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
import sys
import uuid as _uuid
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import DailyScorecardEntry, User
from app.scripts import rederive_scorecard as rs
from app.services.scorecard_export import RESTATEMENTS

APP_DIR = Path(__file__).resolve().parents[1] / "app"
VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "rederive-scorecard.yml"
)

#: Dates no other test seeds. Ranks above 10 keep clear of any real (as_of, rank).
RESET_DAY = date(2093, 3, 2)
_SYM = "ZZRST"
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _code_only(src: str) -> str:
    """Drop full-line comments so prose about a removed path cannot trip a guard."""
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))


async def _clean(*days: date) -> None:
    async with session_scope() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.as_of.in_(days)))


async def _snapshot(day: date) -> list[tuple]:
    async with session_scope() as s:
        rows = (await s.execute(
            select(DailyScorecardEntry)
            .where(DailyScorecardEntry.as_of == day)
            .order_by(DailyScorecardEntry.rank)
        )).scalars().all()
        return [
            (r.id, r.symbol, r.rank, r.score_at_flag, r.price_at_flag, r.price_next_day,
             r.change_pct_1d_after, r.spy_change_pct_1d, r.alpha_vs_spy)
            for r in rows
        ]


async def _admin_cookies(client: httpx.AsyncClient, monkeypatch) -> httpx.Cookies:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"record-admin-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
    return r.cookies


# --------------------------------------------------------------------------
# 1. The reset endpoint is gone, and calling it moves nothing
# --------------------------------------------------------------------------


async def test_an_admin_cannot_reset_the_record_through_the_api(monkeypatch) -> None:
    await _clean(RESET_DAY)
    async with session_scope() as s:
        # Row 1 is ordinary. Row 2 matches the old endpoint's "bad" predicate
        # (next-day price equals flag price with a 0% move), which the default
        # mode deleted; wipe_all deleted both.
        s.add(DailyScorecardEntry(
            as_of=RESET_DAY, symbol=_SYM, rank=91, score_at_flag=80.0,
            price_at_flag=10.0, price_next_day=11.0, change_pct_1d_after=10.0,
            spy_change_pct_1d=1.0, alpha_vs_spy=9.0,
        ))
        s.add(DailyScorecardEntry(
            as_of=RESET_DAY, symbol=_SYM + "B", rank=92, score_at_flag=70.0,
            price_at_flag=10.0, price_next_day=10.0, change_pct_1d_after=0.0,
            spy_change_pct_1d=0.5, alpha_vs_spy=-0.5,
        ))
    before = await _snapshot(RESET_DAY)
    assert len(before) == 2

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cookies = await _admin_cookies(client, monkeypatch)
            # The admin session is real: an admin-only read still answers.
            ok = await client.get("/api/admin/stats", cookies=cookies)
            assert ok.status_code == 200, ok.text
            for body in ({"wipe_all": True}, {"wipe_all": False}, {}):
                r = await client.post("/api/admin/scorecard/reset", json=body, cookies=cookies)
                assert r.status_code in (404, 405), (
                    f"POST /api/admin/scorecard/reset answered {r.status_code} for {body}: "
                    "an admin can still delete recorded entries"
                )
        assert await _snapshot(RESET_DAY) == before, "a recorded entry moved"
    finally:
        await _clean(RESET_DAY)


def _write_routes() -> list[tuple[str, APIRoute]]:
    """Every POST/PUT/PATCH/DELETE route, as (module, route).

    Walks each APIRouter defined in app/routers/ directly, plus the assembled
    app's own routes (recursing into mounts). Reading only `app.routes` is not
    enough: newer FastAPI (0.141 in CI) no longer flattens included routers
    into it, and the walk then saw 2 write routes instead of the real set.
    """
    import app.routers as routers_pkg

    found: dict[int, tuple[str, APIRoute]] = {}
    for info in pkgutil.iter_modules(routers_pkg.__path__):
        mod = importlib.import_module(f"app.routers.{info.name}")
        for obj in vars(mod).values():
            if isinstance(obj, APIRouter):
                for route in obj.routes:
                    if isinstance(route, APIRoute) and route.methods & _WRITE_METHODS:
                        found[id(route)] = (info.name, route)
    stack = list(app.routes)
    while stack:
        route = stack.pop()
        if isinstance(route, APIRoute):
            if route.methods & _WRITE_METHODS and id(route) not in found:
                found[id(route)] = (route.endpoint.__module__, route)
        elif getattr(route, "routes", None):
            stack.extend(route.routes)
    return list(found.values())


def test_the_route_walk_sees_the_write_routes() -> None:
    routes = _write_routes()
    paths = {(mod, r.path) for mod, r in routes}
    assert len(routes) > 20, f"the walk found only {len(routes)} write routes"
    # Known write routes, so a walk that silently misses routers fails here.
    assert ("admin", "/users/{user_id}/tier") in paths
    assert ("admin", "/growth-tick/run") in paths


def test_no_route_path_under_scorecard_accepts_a_write() -> None:
    offenders = [
        (mod, sorted(route.methods & _WRITE_METHODS), route.path)
        for mod, route in _write_routes()
        if mod.endswith("scorecard") or "scorecard" in route.path.lower()
    ]
    assert not offenders, f"write routes on the record: {offenders}"


# --------------------------------------------------------------------------
# 2. No write-method route reaches the record tables or their writers
# --------------------------------------------------------------------------

#: Names a write route has no business touching. Covers the table, the ORM
#: class, the point-in-time archive and every job that writes either.
_RECORD_TOKENS = (
    "DailyScorecardEntry",
    "daily_scorecard",
    "ScoreSnapshot",
    "score_snapshot",
    "capture_score_snapshots",
    "backcheck_yesterday",
    "backcheck_all_pending",
    "_ensure_daily_scorecard",
    "rederive_scorecard",
    "_rederive",
)


def test_no_write_route_references_the_record() -> None:
    offenders = []
    for mod, route in _write_routes():
        src = _code_only(inspect.getsource(route.endpoint))
        hits = [t for t in _RECORD_TOKENS if t in src]
        if hits:
            offenders.append((mod, route.path, hits))
    assert not offenders, (
        "a POST/PUT/PATCH/DELETE route references the public record or a job that "
        f"writes it: {offenders}"
    )


def test_admin_router_does_not_import_the_record_model() -> None:
    src = _code_only((APP_DIR / "routers" / "admin.py").read_text(encoding="utf-8"))
    assert "DailyScorecardEntry" not in src
    assert "scorecard/reset" not in src


# --------------------------------------------------------------------------
# 3. Nothing under app/ deletes, truncates or re-ranks the table
# --------------------------------------------------------------------------

_RAW_SQL_MUTATION = re.compile(
    r"\b(delete\s+from|update|truncate(\s+table)?)\s+\"?daily_scorecard\b", re.IGNORECASE
)
#: A Python attribute assignment statement. Line-anchored, so SQL text such as
#: "WHERE e.symbol = tickers.symbol" inside a string does not count.
_IDENTITY_ASSIGN = re.compile(
    r"^\s*[\w.]+\.(as_of|symbol|rank|score_at_flag)\s*=(?!=)", re.MULTILINE
)
_VALUE_ASSIGN = re.compile(
    r"^\s*[\w.]+\.(price_at_flag|price_next_day|change_pct_1d_after|spy_change_pct_1d"
    r"|alpha_vs_spy)\s*=(?!=)",
    re.MULTILINE,
)
#: The only modules allowed to set the value columns on an existing row.
_VALUE_WRITERS = {
    ("services", "scorecard_backcheck.py"),  # pending rows only, see below
    ("scripts", "rederive_scorecard.py"),  # restatement-gated, see section 5
}


def test_no_code_under_app_deletes_truncates_or_reranks_the_record() -> None:
    value_writers: set[tuple[str, ...]] = set()
    for path in APP_DIR.rglob("*.py"):
        rel = path.relative_to(APP_DIR).parts
        code = _code_only(path.read_text(encoding="utf-8"))
        assert "delete(DailyScorecardEntry" not in code, rel
        assert "update(DailyScorecardEntry" not in code, rel
        assert not _RAW_SQL_MUTATION.search(code), (rel, _RAW_SQL_MUTATION.search(code))
        if "DailyScorecardEntry" not in code:
            continue
        # A module holding recorded rows never deletes one through the session.
        assert not re.search(r"\.delete\(\s*(e|entry|row|r|live)\s*\)", code), rel
        assert not _IDENTITY_ASSIGN.search(code), (
            f"{rel} assigns an identity column on a scorecard row "
            f"({_IDENTITY_ASSIGN.search(code)}): that is a re-rank"
        )
        if _VALUE_ASSIGN.search(code):
            value_writers.add(tuple(rel))
    assert value_writers == _VALUE_WRITERS, (
        f"modules writing recorded values changed: {sorted(value_writers)}"
    )


def test_the_backcheck_only_fills_pending_rows() -> None:
    from app.services import scorecard_backcheck as bc

    for fn in (bc.backcheck_yesterday, bc.backcheck_all_pending):
        src = _code_only(inspect.getsource(fn))
        assert "DailyScorecardEntry.price_next_day.is_(None)" in src, (
            f"{fn.__name__} no longer restricts itself to rows without a next-day "
            "price, so it can overwrite a recorded result"
        )


# --------------------------------------------------------------------------
# 4. Migrations
# --------------------------------------------------------------------------

#: 0034 capped score_at_flag at 100 on 2026-06-15; disclosed as that restatement.
_DISCLOSED_MIGRATIONS = {"20260615_0034_clamp_scorecard_scores.py"}


def test_no_migration_rewrites_the_record_except_the_disclosed_one() -> None:
    assert any(r["date"] == "2026-06-15" for r in RESTATEMENTS)
    found = set()
    for path in VERSIONS_DIR.glob("*.py"):
        code = _code_only(path.read_text(encoding="utf-8"))
        if _RAW_SQL_MUTATION.search(code) or re.search(
            r"(delete|update)\(\s*(sa\.)?table\(\s*[\"']daily_scorecard", code
        ):
            found.add(path.name)
    assert found == _DISCLOSED_MIGRATIONS, (
        f"migrations that rewrite daily_scorecard: {sorted(found)}. A new one needs "
        "a dated entry in scorecard_export.RESTATEMENTS first."
    )


# --------------------------------------------------------------------------
# 5. The documented correction path cannot write without a restatement
# --------------------------------------------------------------------------

_TODAY = date(2026, 9, 18)


def test_apply_without_a_restatement_is_refused() -> None:
    for bad in (None, ""):
        with pytest.raises(rs.RestatementRequiredError):
            rs.apply_window_until(bad, None, _TODAY)


def test_apply_with_an_undisclosed_date_is_refused() -> None:
    assert not any(r["date"] == "2026-09-17" for r in RESTATEMENTS)
    with pytest.raises(rs.RestatementRequiredError):
        rs.apply_window_until("2026-09-17", None, _TODAY)
    with pytest.raises(rs.RestatementRequiredError):
        rs.apply_window_until("25/08/2026", None, _TODAY)


def test_a_future_dated_restatement_is_refused(monkeypatch) -> None:
    future = [*RESTATEMENTS, {"date": "2026-12-01", "fields_changed": ", ".join(rs.WRITTEN_FIELDS)}]
    monkeypatch.setattr(rs, "RESTATEMENTS", future)
    with pytest.raises(rs.RestatementRequiredError):
        rs.apply_window_until("2026-12-01", None, _TODAY)


def test_a_restatement_that_does_not_name_the_written_columns_is_refused() -> None:
    # 2026-06-15 changed score_at_flag only; it cannot cover a price rewrite.
    with pytest.raises(rs.RestatementRequiredError):
        rs.apply_window_until("2026-06-15", None, _TODAY)


def test_a_restatement_only_reaches_rows_recorded_before_it() -> None:
    assert rs.apply_window_until("2026-08-25", None, _TODAY) == date(2026, 8, 24)
    assert rs.apply_window_until("2026-08-25", date(2026, 9, 10), _TODAY) == date(2026, 8, 24)
    assert rs.apply_window_until("2026-08-25", date(2026, 7, 1), _TODAY) == date(2026, 7, 1)


def test_the_cli_refuses_apply_without_a_restatement(monkeypatch) -> None:
    ran = []
    monkeypatch.setattr(rs, "_rederive", lambda *a, **k: ran.append(a))
    monkeypatch.setattr(rs.asyncio, "run", lambda coro: None)
    monkeypatch.setattr(sys, "argv", ["rederive_scorecard", "--apply"])
    with pytest.raises(SystemExit) as exc:
        rs.main()
    assert exc.value.code == 2
    assert not ran


async def _fake_window(symbol, start, end):
    return {start: 20.0, end: 30.0}


async def test_rederive_apply_writes_nothing_without_a_restatement(monkeypatch) -> None:
    day = date(2026, 8, 3)  # Monday; next session 2026-08-04 closed long ago
    await _clean_symbol(day)
    async with session_scope() as s:
        s.add(DailyScorecardEntry(
            as_of=day, symbol=_SYM, rank=93, score_at_flag=80.0, price_at_flag=10.0,
            price_next_day=11.0, change_pct_1d_after=10.0, spy_change_pct_1d=1.0,
            alpha_vs_spy=9.0,
        ))
    monkeypatch.setattr(rs, "_vendor_key", lambda: "test-key")
    monkeypatch.setattr(rs, "_unadjusted_window", _fake_window)
    try:
        before = await _row(day)
        changed = await rs._rederive(day, True, 0.0, False, day, None)
        assert changed == 0
        assert await _row(day) == before, "a rewrite happened with no restatement named"
    finally:
        await _clean_symbol(day)


async def test_rederive_apply_cannot_reach_rows_recorded_after_the_restatement(
    monkeypatch,
) -> None:
    after = date(2026, 9, 1)  # recorded after the 2026-08-25 restatement
    await _clean_symbol(after)
    async with session_scope() as s:
        s.add(DailyScorecardEntry(
            as_of=after, symbol=_SYM, rank=94, score_at_flag=80.0, price_at_flag=10.0,
            price_next_day=11.0, change_pct_1d_after=10.0, spy_change_pct_1d=1.0,
            alpha_vs_spy=9.0,
        ))
    monkeypatch.setattr(rs, "_vendor_key", lambda: "test-key")
    monkeypatch.setattr(rs, "_unadjusted_window", _fake_window)
    try:
        before = await _row(after)
        await rs._rederive(after, True, 0.0, False, after, "2026-08-25")
        assert await _row(after) == before, (
            "an old restatement's date was used to rewrite a row recorded after it"
        )
    finally:
        await _clean_symbol(after)


async def test_rederive_apply_still_works_under_a_disclosed_restatement(monkeypatch) -> None:
    """The guard must not simply break the correction path it gates."""
    day = date(2026, 8, 3)
    await _clean_symbol(day)
    async with session_scope() as s:
        s.add(DailyScorecardEntry(
            as_of=day, symbol=_SYM, rank=95, score_at_flag=80.0, price_at_flag=10.0,
            price_next_day=11.0, change_pct_1d_after=10.0, spy_change_pct_1d=1.0,
            alpha_vs_spy=9.0,
        ))
    monkeypatch.setattr(rs, "_vendor_key", lambda: "test-key")
    monkeypatch.setattr(rs, "_unadjusted_window", _fake_window)

    async def _only_ours(since, until=None):
        return [e for e in await _orig_load(since, until) if e.symbol == _SYM]

    _orig_load = rs._load
    monkeypatch.setattr(rs, "_load", _only_ours)
    try:
        changed = await rs._rederive(day, True, 0.0, False, day, "2026-08-25")
        assert changed == 1
        row = await _row(day)
        assert row[1:3] == (_SYM, 95), "identity columns moved"
        assert row[3] == 80.0, "score_at_flag moved"
        assert row[4] == 20.0 and row[5] == 30.0
    finally:
        await _clean_symbol(day)


async def _row(day: date) -> tuple:
    rows = [r for r in await _snapshot(day) if r[1] == _SYM]
    assert len(rows) == 1
    return rows[0]


async def _clean_symbol(day: date) -> None:
    async with session_scope() as s:
        await s.execute(
            delete(DailyScorecardEntry).where(
                DailyScorecardEntry.as_of == day, DailyScorecardEntry.symbol == _SYM
            )
        )


def test_the_operator_workflow_passes_the_restatement_on_apply() -> None:
    code = _code_only(WORKFLOW.read_text(encoding="utf-8"))
    assert "--apply --restatement ${RESTATEMENT}" in code
    assert "RESTATEMENT: ${{ inputs.restatement }}" in code
    assert re.search(r"--apply\"\s*;;", code) is None, "apply mode still runs without a restatement"
