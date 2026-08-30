"""Every marketing email must carry a VISIBLE, login-free unsubscribe link.

Why this file exists
--------------------
Until 2026-08-31 the shared footer in `email_design._footer()` offered three
links — Email preferences, Account, Billing — and all three point at `/app/*`,
which `frontend/middleware.ts` puts behind auth. So no Tapeline email carried
an opt-out a recipient could use without logging in. The only working opt-out
was the `List-Unsubscribe` header, which many clients never render.

Under the Australian Spam Act 2003 — the governing law, since Tapeline sends
from Melbourne, not the laxer US CAN-SPAM opt-out regime most email advice is
written against — an unsubscribe facility must be functional and reasonably
usable. ACMA has enforced exactly this (Telstra, A$626,000, October 2024).

The tokenised no-auth unsubscribe machinery already existed in
`services/unsubscribe.py`; it was simply never surfaced in the body. These
tests pin that it now is, and that transactional mail is correctly excluded.
"""
from __future__ import annotations

import pytest

from app.services import email as email_mod
from app.services.email_design import UNSUB_PLACEHOLDER, shell

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sending(monkeypatch):
    """Configure the sender and capture the Resend payload without a network call."""
    # services/unsubscribe.py mints its token from get_settings().session_secret
    # (not email.py's own secret), so the settings object is what has to carry
    # it — otherwise unsubscribe_url() returns None and the link renders empty,
    # which is exactly the bug this file exists to catch.
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "resend_api_key", "re_test_key", raising=False)
    monkeypatch.setattr(s, "session_secret", "unit-test-secret", raising=False)
    monkeypatch.setattr(s, "app_url", "https://tapeline.io", raising=False)
    monkeypatch.setattr(
        email_mod.settings, "resend_api_key", "re_test_key", raising=False
    )

    captured: dict = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "email_test"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None, timeout=None):
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(email_mod.httpx, "AsyncClient", _Client)
    return captured


async def _send(html: str, **kwargs):
    return await email_mod.send_email(
        to="reader@example.com", subject="Test", html=html, **kwargs
    )


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
async def test_every_rendered_email_carries_the_placeholder():
    """The footer is shared, so the placeholder reaches all 47 templates."""
    body = shell("<p>anything</p>")
    assert UNSUB_PLACEHOLDER in body


async def test_marketing_send_gets_a_visible_login_free_link(sending, monkeypatch):
    """The whole point: a link in the BODY that needs no sign-in."""
    monkeypatch.setenv("APP_URL", "https://tapeline.io")
    html = shell("<p>weekly digest</p>")

    await _send(html, unsubscribe_user_id="u_123", unsubscribe_category="weekly_newsletter")

    sent = sending["json"]["html"]
    assert UNSUB_PLACEHOLDER not in sent, "placeholder leaked into a real send"
    assert ">Unsubscribe<" in sent, "no visible unsubscribe link in the body"
    assert "no sign-in needed" in sent

    # And it must NOT be an auth-gated /app/* URL — that is the defect.
    import re

    hrefs = re.findall(r'href="([^"]+)"', sent)
    unsub = [h for h in hrefs if "unsubscribe" in h.lower()]
    assert unsub, f"no unsubscribe href found among {hrefs}"
    for href in unsub:
        assert "/app/" not in href, f"unsubscribe link is auth-gated: {href}"


async def test_transactional_send_has_no_unsubscribe_offer(sending):
    """A password reset is not a commercial electronic message.

    Offering an opt-out from mail the account depends on is both wrong and
    legally unnecessary — so the placeholder is stripped, not resolved.
    """
    html = shell("<p>reset your password</p>")

    await _send(html)  # no unsubscribe_user_id => transactional

    sent = sending["json"]["html"]
    assert UNSUB_PLACEHOLDER not in sent, "placeholder leaked into a real send"
    assert ">Unsubscribe<" not in sent


async def test_placeholder_never_survives_to_the_wire(sending):
    """Belt and braces: whatever the branch, the raw comment must not ship."""
    for kwargs in ({}, {"unsubscribe_user_id": "u_1"}):
        sending.clear()
        await _send(shell("<p>x</p>"), **kwargs)
        assert UNSUB_PLACEHOLDER not in sending["json"]["html"]


async def test_send_still_succeeds_if_the_footer_resolver_breaks(sending, monkeypatch):
    """A footer failure must never cost the email.

    The List-Unsubscribe header remains a functioning opt-out, so degrading to
    'no visible link' beats not delivering a trial-expiry notice at all.
    """
    import app.services.unsubscribe as unsub_mod

    def _boom(*a, **k):
        raise RuntimeError("token minting is down")

    monkeypatch.setattr(unsub_mod, "unsubscribe_url", _boom)

    res = await _send(shell("<p>x</p>"), unsubscribe_user_id="u_123")
    assert res.get("id") == "email_test", "send should survive a footer failure"
