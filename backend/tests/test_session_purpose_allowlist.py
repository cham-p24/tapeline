"""A token minted for one purpose must not work as another.

THE BUG
-------
`decode_session_token` rejected exactly one purpose:

    if payload.get("purpose") == "mfa":
        return None

Everything else fell through. Several short-lived tokens are signed with the
SAME secret and carry a `purpose` claim, and one of them — the 30-day
trusted-device cookie (`services/signin_codes.issue_trusted_device_token`) —
carries `sub` and `epoch` in exactly the shape a session does. So it decoded as
a full session. Verified by running it, not by reading:

    decode_session_token(<trusted-device token>)  ->  ("user_123", 7)

That token exists only to prove a browser already passed an emailed sign-in
code. It is not a credential for the product, and it lives 30 days.

WHY AN ALLOWLIST
----------------
A denylist has to be updated every time someone adds a purpose, and the cost of
forgetting is silent privilege escalation — which is precisely what happened
when the trusted-device token was introduced after the "mfa" check was written.
An allowlist fails the other way: a new purpose is refused until someone
deliberately admits it.

Sessions minted before the claim existed carry no `purpose` at all, so None is
allowed separately. Adding "session" to the set would not have grandfathered
them in.
"""

import pytest

from app.services.mfa import issue_mfa_token
from app.services.session import (
    _SESSION_PURPOSES,
    decode_session_token,
    issue_session_token,
    verify_session_token,
)
from app.services.signin_codes import is_trusted_device, issue_trusted_device_token


class TestTrustedDeviceIsNotASession:
    """The regression, both directions."""

    def test_a_device_token_is_not_accepted_as_a_session(self):
        tok = issue_trusted_device_token("user_123", 7)
        assert decode_session_token(tok) is None
        assert verify_session_token(tok) is None

    def test_but_it_still_works_as_a_device_token(self):
        """The fix must not break the feature. If it did, every returning user
        would get an emailed code on a browser they had already verified — and
        that would make Resend a hard dependency of signing in, which is the
        exact outcome the new-device-only design was chosen to avoid."""
        tok = issue_trusted_device_token("user_123", 7)
        assert is_trusted_device(tok, "user_123", 7) is True

    def test_a_real_session_still_decodes(self):
        tok = issue_session_token("user_123", 7)
        assert decode_session_token(tok) == ("user_123", 7)


class TestEveryOtherPurposeIsRefused:
    def test_the_mfa_challenge_is_still_refused(self):
        """The original denylist entry, now covered by the allowlist."""
        assert decode_session_token(issue_mfa_token("user_123")) is None

    def test_an_unknown_purpose_is_refused_by_default(self):
        """The property that makes this an allowlist. A purpose added tomorrow
        is refused until someone deliberately admits it — the opposite of the
        denylist, where a new purpose is silently accepted."""
        import jwt

        from app.services.session import _session_secret

        forged = jwt.encode(
            {"sub": "user_123", "epoch": 7, "purpose": "some_future_thing"},
            _session_secret(),
            algorithm="HS256",
        )
        assert decode_session_token(forged) is None

    def test_a_legacy_session_with_no_purpose_claim_is_still_accepted(self):
        """Sessions minted before the claim existed must not be invalidated —
        that would sign out every outstanding user on deploy."""
        import jwt

        from app.services.session import _session_secret

        legacy = jwt.encode(
            {"sub": "user_123", "epoch": 0},
            _session_secret(),
            algorithm="HS256",
        )
        assert decode_session_token(legacy) == ("user_123", 0)


def test_the_allowlist_is_actually_an_allowlist():
    """Pins the shape, so a later edit cannot quietly turn it back into a
    denylist while these tests keep passing."""
    import ast
    import inspect
    import textwrap

    from app.services import session as mod

    tree = ast.parse(textwrap.dedent(inspect.getsource(mod)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)

    assert "_SESSION_PURPOSES" in code
    assert "not in _SESSION_PURPOSES" in code, "the check is no longer an allowlist"
    # The denylist shape, banned.
    assert "== 'mfa'" not in code and '== "mfa"' not in code, (
        "back to a denylist — every new purpose would be accepted by default"
    )


@pytest.mark.parametrize("purpose", ["trusted_device", "mfa", "reset", "verify"])
def test_no_non_session_purpose_is_in_the_allowlist(purpose):
    assert purpose not in _SESSION_PURPOSES
