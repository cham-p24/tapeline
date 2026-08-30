"""Safe field access for Stripe vendor objects.

THE BUG THIS EXISTS TO PREVENT
------------------------------
In stripe-python >= 12 a `StripeObject` is NOT a dict subclass. Its MRO is
literally ('StripeObject', 'object') and it defines no `get`, `keys`, `items`
or `__iter__`. `__getitem__` works, so `obj["type"]` reads fine, but
`obj.get("type")` falls through to `__getattr__("get")`, misses `_data`, and
raises `AttributeError: get`.

That is PR #639: the webhook that GRANTS the paid tier called `.get()` on the
event and 500'd on every real Stripe delivery, so a customer could have been
charged and never received their tier. It survived because all nine webhook
tests monkeypatched `parse_webhook` to return a plain dict — the shape that
broke was the one shape never exercised.

It is not a one-off. The same mistake was made again on 2026-08-30 inside
`stripe_preflight.py`, the diagnostic written to detect it, on `stripe.Price`,
`stripe.Account` and a `ListObject`. mypy caught that one. This module exists
so there is a single obvious thing to reach for instead of a `.get()` that
looks correct and works fine against a dict fixture.

`routers/webhooks.py` keeps using `parse_webhook`'s plain-dict conversion —
that is a deliberate, documented choice for the ~34 call sites there. This is
for the other paths that hold a live vendor object.
"""
from __future__ import annotations

from typing import Any


def stripe_field(obj: Any, name: str, default: Any = None) -> Any:
    """Read `name` off a Stripe object, a plain dict, or None.

    Tries `__getitem__` first (works on both StripeObject and dict), then
    attribute access, then the default. Never raises for a missing field —
    a vendor payload that omits an optional key is normal, not exceptional.
    """
    if obj is None:
        return default
    try:
        value = obj[name]
    except Exception:
        value = getattr(obj, name, default)
    return default if value is None else value
