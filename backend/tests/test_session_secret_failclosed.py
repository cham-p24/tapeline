"""SESSION_SECRET must fail CLOSED in non-dev environments.

Previously _session_secret() fell back to deriving the key from
STRIPE_WEBHOOK_SECRET, and failing that a constant hardcoded in a public repo —
either of which made session cookies + the 2FA challenge token forgeable. It now
raises in prod when the secret is unset, and the startup check turns that into a
boot failure so a misconfiguration surfaces at deploy, not on a user's request.
"""
from __future__ import annotations

import pytest


def test_session_secret_fails_closed_in_prod_when_unset(monkeypatch):
    from app.services import session as sess

    monkeypatch.setattr(sess.settings, "session_secret", "", raising=False)
    monkeypatch.setattr(sess.settings, "stripe_webhook_secret", "whsec_x", raising=False)
    monkeypatch.setattr(sess.settings, "app_env", "production", raising=False)

    # Even with a Stripe webhook secret present, it must NOT be used as a
    # fallback — that was the forgeable derivation.
    with pytest.raises(RuntimeError):
        sess._session_secret()


def test_session_secret_uses_the_explicit_value(monkeypatch):
    from app.services import session as sess

    monkeypatch.setattr(sess.settings, "session_secret", "s3cr3t-value", raising=False)
    monkeypatch.setattr(sess.settings, "app_env", "production", raising=False)
    assert sess._session_secret() == "s3cr3t-value"


def test_session_secret_dev_fallback_is_stable_and_does_not_raise(monkeypatch):
    from app.services import session as sess

    monkeypatch.setattr(sess.settings, "session_secret", "", raising=False)
    monkeypatch.setattr(sess.settings, "app_env", "development", raising=False)
    # Dev keeps a stable constant so local sessions survive restarts.
    assert sess._session_secret() == sess._session_secret()
    assert sess._session_secret()  # non-empty


def test_startup_check_refuses_to_boot_in_prod_when_unset(monkeypatch):
    from app import main as m

    monkeypatch.setattr(m.settings, "session_secret", "", raising=False)
    monkeypatch.setattr(m.settings, "app_env", "production", raising=False)
    with pytest.raises(RuntimeError):
        m._check_session_secret()


def test_startup_check_passes_when_secret_is_set(monkeypatch):
    from app import main as m

    monkeypatch.setattr(m.settings, "session_secret", "set", raising=False)
    monkeypatch.setattr(m.settings, "app_env", "production", raising=False)
    m._check_session_secret()  # must not raise


def test_startup_check_is_a_noop_in_development(monkeypatch):
    from app import main as m

    monkeypatch.setattr(m.settings, "session_secret", "", raising=False)
    monkeypatch.setattr(m.settings, "app_env", "development", raising=False)
    m._check_session_secret()  # must not raise
