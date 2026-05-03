"""User + subscription + alert rule models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    # User id: when Clerk is wired, uses Clerk's id. In the interim native auth mode,
    # we generate "u_<uuid>" ids on signup. Either way the schema stays identical.
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False, index=True, unique=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)

    # Native auth — bcrypt hash. Null means user was created via Clerk webhook.
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Owner/operator flag. Set via seed script or DB update, never via signup.
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Trial state — auto-started on signup, downgrades to free at end if no card
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Referral program — a user's own sharable code + who referred them
    referral_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    referred_by: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)

    # Lifetime deal marker — never expires, never billed after purchase
    is_lifetime: Mapped[bool] = mapped_column(default=False, nullable=False)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # E.164-format phone for SMS alerts. Premium-only feature; Twilio-delivered.
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Discord webhook URL for posting alerts into the user's own server.
    # Pro+ feature, free to deliver — just an HTTP POST to the user's Discord URL.
    discord_webhook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Drip-email dedupe — comma-separated day tokens already sent ("3,7,13,end").
    # The daily worker checks this before sending so a worker restart mid-day
    # doesn't double-send. Welcome (day 0) is fire-once on signup, not tracked here.
    drip_state: Mapped[str] = mapped_column(String(40), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)  # Stripe subscription id
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)  # score|squeeze|regime|congress
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = any ticker
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)  # email|telegram
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(400), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    delivered: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
