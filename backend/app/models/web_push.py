"""Web Push subscription record — one per (user, browser/device)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WebPushSubscription(Base):
    """
    A browser PushSubscription as returned by `pushManager.subscribe()`.

    The `endpoint` URL is the FCM/Mozilla Push Service URL that the Service
    Worker will receive notifications through. The two keys are the ECDH
    public key + auth secret needed to encrypt payload deliveries.

    One user can have multiple subscriptions (one per browser/device).
    Unsubscribing on the browser side returns 410 from the endpoint;
    the worker should delete those rows lazily.
    """
    __tablename__ = "web_push_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_web_push_user_endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(200), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(100), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
