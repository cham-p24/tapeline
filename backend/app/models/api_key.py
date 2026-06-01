"""Public-API keys (Premium feature).

A Premium subscriber can mint API keys to hit the read-only `/api/v1/*`
surface programmatically. The key product is the *authenticated, versioned,
rate-tracked, revocable* contract — the same scores are also on the public
`/api/public/*` endpoints, but those carry no SLA, no per-caller quota, and
no stability guarantee.

Security posture:
  - We NEVER store the plaintext key. `key_hash` is sha256(full_key) hex; the
    full key (`tl_live_<32 hex>`) is shown to the user exactly once at creation.
  - `prefix` ("tl_live_xxxxxxxx", the first 16 chars) is stored in the clear so
    the management UI can let the user identify which key is which without ever
    surfacing the secret again.

Quota accounting lives on the row: `requests_today` counts calls in the UTC day
named by `requests_day` ("YYYY-MM-DD"); the authenticator rolls both over when
the day changes. The daily cap itself comes from `tier.effective_limit(user,
"api_requests_per_day")` (Premium paid = 1,000; Premium trial = 100), so the
cap tracks tier/trial state without being denormalised onto the key.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    # ak_<24 hex> — 27 chars, well under the 32-char alembic version ceiling
    # convention we keep for ids generally.
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(60), ForeignKey("users.id"), nullable=False, index=True
    )
    # Human label so a developer can tell "prod-bot" from "laptop-script".
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # First 16 chars of the key ("tl_live_" + 8 hex) — shown for identification.
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # sha256(full_key) hex — the only representation of the secret we persist.
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Rolling daily quota counter. `requests_day` is the UTC date string the
    # `requests_today` count belongs to; both reset on the authenticator's
    # first call of a new day.
    requests_today: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    requests_day: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Lifetime call count — never reset; powers the "total requests" stat.
    request_count_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
