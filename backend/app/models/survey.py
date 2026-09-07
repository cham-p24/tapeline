"""Customer survey responses.

WHY THIS TABLE EXISTS AND WHY IT IS SHAPED LIKE THIS
----------------------------------------------------
The September 2026 survey is a recruiting instrument, not a measurement one:
23 reachable people, ~6 expected responses. See `docs/growth/SURVEY_METHODOLOGY.md`
for the arithmetic. That shapes the schema in three ways.

1. **No user_id, no token, no join back to `users`.** The survey link is the same
   for everyone. The email tells respondents the link does not identify them, and
   a per-recipient token would quietly make that false. The cost is that responses
   cannot be segmented -- which costs nothing, because at n=8 nothing is separable
   below a 75-point gap anyway.

2. **`contact_email` is separate and optional.** It is supplied by the respondent
   only if they want a reply or a call. That is a deliberate, visible act by them,
   not a silent identifier attached by us.

3. **Free text is stored as given, and is NOT for republication.** Anyone who
   answered under "the link doesn't identify you" has not consented to being
   quoted. See the public-repo warning at the top of `docs/FEEDBACK_LOG.md` before
   copying anything out of here.

COMPLIANCE
----------
No question on the form asks about money, holdings, position size, experience or
goals -- collecting a person's financial circumstances is the step that turns
general information into personal advice, which the publisher exemption depends on
never happening. If a respondent volunteers something like that in a free-text
box anyway, it is not to be acted on, transcribed, or followed up.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )

    #: Which survey this belongs to, so a later one does not have to migrate.
    survey_key: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True, default="2026_09",
    )

    #: Q1, the one-tap status question. Free-form rather than an enum on purpose:
    #: the option list is a hypothesis, and a DB constraint on it would make the
    #: hypothesis expensive to change between surveys.
    status: Mapped[str | None] = mapped_column(String(60), nullable=True)

    #: Q2 -- "What was going on the week you signed up?" The unaided open box, and
    #: the one thing the form can ask that the database cannot answer.
    trigger_story: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Q3 -- "What, if anything, was confusing or frustrating about it?"
    friction: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Q4 -- the actual point of the exercise.
    wants_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Optional, respondent-supplied. Only present if they asked for a reply.
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
