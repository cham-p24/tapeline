"""POST /api/survey — public, unauthenticated, and it must stay that way.

The endpoint takes no auth because 22 of 32 external accounts never returned
after their signup day: a sign-in wall in front of the ask would be asking a
dormant person to do two things. It is also what keeps the recruiting email's
promise that the link does not identify the respondent.

That makes the honeypot and the empty-submission rejection load-bearing rather
than decorative, so both are tested here.
"""
from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db import session_scope
from app.main import app
from app.models import SurveyResponse


async def _post(payload: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        return await c.post("/api/survey", json=payload)


async def _count() -> int:
    async with session_scope() as s:
        return int(await s.scalar(select(func.count()).select_from(SurveyResponse)) or 0)


async def test_a_full_response_is_stored() -> None:
    before = await _count()
    r = await _post({
        "status": "used_then_stopped",
        "trigger_story": "I was screening by hand every Sunday night.",
        "friction": "Could not tell what the score was made of.",
        "wants_call": True,
        "contact_email": "Sam@Example.com ",
    })
    assert r.status_code == 200, r.text
    assert await _count() == before + 1

    async with session_scope() as s:
        row = (await s.execute(
            select(SurveyResponse).order_by(SurveyResponse.created_at.desc()).limit(1)
        )).scalar_one()
    assert row.status == "used_then_stopped"
    assert row.wants_call is True
    assert row.contact_email == "sam@example.com", "email should be normalised"
    assert row.survey_key == "2026_09"


async def test_a_partial_response_is_accepted() -> None:
    """Nothing on the form is required. Someone who taps one option and leaves
    has still told you something, and rejecting that would discard the cheapest
    answer on the instrument."""
    before = await _count()
    r = await _post({"status": "dont_remember"})
    assert r.status_code == 200, r.text
    assert await _count() == before + 1


async def test_an_entirely_empty_submission_is_rejected() -> None:
    before = await _count()
    r = await _post({})
    assert r.status_code == 400
    assert await _count() == before, "an empty mis-click was stored"


async def test_the_honeypot_reports_success_and_stores_nothing() -> None:
    """Never tell a bot it was detected — a 400 teaches it to retry without the
    field. Same posture as the signup honeypot."""
    before = await _count()
    r = await _post({"status": "using_it", "website": "http://spam.example"})
    assert r.status_code == 200, r.text
    assert await _count() == before, "a honeypot submission was stored"


async def test_a_malformed_email_is_rejected() -> None:
    before = await _count()
    r = await _post({"status": "using_it", "contact_email": "not-an-email"})
    assert r.status_code == 400
    assert await _count() == before


async def test_no_user_id_is_recorded() -> None:
    """The table deliberately has no join back to `users`.

    The email tells respondents the link does not identify them. If a column
    ever appears here that could, that sentence becomes false and the copy has
    to change with it.
    """
    cols = {c.name for c in SurveyResponse.__table__.columns}
    assert "user_id" not in cols
    assert cols == {
        "id", "survey_key", "status", "trigger_story", "friction",
        "wants_call", "contact_email", "created_at",
    }
