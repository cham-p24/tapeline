"""POST /api/survey -- the customer survey, open to anyone with the link.

NO AUTH, BY DESIGN AND NOT BY OMISSION
--------------------------------------
Two independent reasons, either of which would be sufficient.

1. **Most recipients cannot log in from an email.** Of 32 external accounts, 22
   never came back after their signup day and only 8 ever performed a real product
   action. Putting a sign-in wall in front of the one thing you are asking a
   dormant user to do is asking them to do two things.

2. **The email promises the link does not identify them.** Authenticating the
   submission would make that sentence false. The survey is unlinked to `users`
   on purpose -- see `models/survey.py`.

The cost is that a stranger with the URL can post. At a list of 23 people that is
a rounding error, and it is bounded by the per-IP limit below plus a honeypot.
Nothing here grants anything, changes an account, or costs money, so the worst
case of an abusive post is a junk row the founder deletes.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import SurveyResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Same shape as routers/contact.py: 5 posts per IP per 10 minutes.
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_SEC = 600
_recent_by_ip: dict[str, deque[float]] = defaultdict(deque)

#: Q1's option list. Kept here rather than in a DB constraint because the option
#: list is a HYPOTHESIS about how people relate to the product, and the whole
#: point of asking is that it has never been tested. An unrecognised value is
#: stored as given rather than coerced -- coercing to "other" is how the
#: cancellation flow ended up with three nulls and no idea why.
STATUS_OPTIONS = (
    # People with a Tapeline account.
    "using_it",
    "signed_up_not_used",
    "used_then_stopped",
    "dont_remember",
    # People on the newsletter list who never made an account. 14 of the 46
    # reachable addresses are these, and every option above presupposes a
    # signup — so without these two the instrument asks a third of the
    # audience a question with no true answer, which is the textbook
    # false-presupposition defect and produces a fabricated answer or an
    # abandoned form.
    "no_account_meaning_to",
    "no_account_not_for_me",
)


class SurveySubmission(BaseModel):
    status: str | None = Field(None, max_length=60)
    trigger_story: str | None = Field(None, max_length=4000)
    friction: str | None = Field(None, max_length=4000)
    wants_call: bool = False
    contact_email: str | None = Field(None, max_length=320)
    # Honeypot. Bots fill every field; the real form keeps this off-screen.
    website: str | None = Field(None, max_length=200)


@router.post("/survey")
async def submit_survey(
    body: SurveySubmission,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Record one survey response. Idempotency is deliberately NOT enforced.

    A respondent who submits twice has said something twice, and at this sample
    size a duplicate is visible by eye. Silently dropping a second submission
    would more likely discard a correction than prevent an abuse.
    """
    # Honeypot: pretend success. Never tell a bot it was detected.
    if body.website:
        logger.info("survey.honeypot_tripped")
        return {"ok": True}

    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    hits = _recent_by_ip[ip]
    while hits and now - hits[0] > _RATE_LIMIT_WINDOW_SEC:
        hits.popleft()
    if len(hits) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many submissions.")
    hits.append(now)

    story = (body.trigger_story or "").strip()
    friction = (body.friction or "").strip()
    email = (body.contact_email or "").strip().lower() or None
    if email and not _EMAIL_RX.match(email):
        raise HTTPException(status_code=400, detail="That email doesn't look right.")

    # An entirely empty submission is a mis-click, not an answer.
    if not any([body.status, story, friction, body.wants_call, email]):
        raise HTTPException(status_code=400, detail="Nothing to record.")

    session.add(SurveyResponse(
        survey_key="2026_09",
        status=body.status or None,
        trigger_story=story or None,
        friction=friction or None,
        wants_call=bool(body.wants_call),
        contact_email=email,
    ))
    await session.commit()

    logger.info(
        "survey.response_recorded status=%s story_len=%d friction_len=%d "
        "wants_call=%s left_email=%s",
        body.status, len(story), len(friction), body.wants_call, bool(email),
    )
    return {"ok": True}
