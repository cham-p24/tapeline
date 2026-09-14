"""Vendor-neutral failure types for the worker's factor passes.

The passes in `app.workers.signal_publisher` stamp every symbol they attempt,
so they must tell three outcomes apart: an ANSWER (stamp it), a THROTTLE (the
vendor refused the caller, not the symbol - never stamp it) and an UNAVAILABLE
call (stamp it, but count it, because a run of them is an outage).

Those rules were written against Finnhub, whose adapter raised its own types.
The insider pass now reads SEC EDGAR directly (`services/edgar_form4.py`), so the
pass catches these bases and each vendor raises its own subclass. The concrete
types keep their vendor names in logs; the pass's decisions do not depend on
which vendor it was.
"""
from __future__ import annotations


class VendorThrottledError(Exception):
    """The vendor refused the CALLER (rate limit or rejected credentials).

    Says nothing about the symbol asked about, and applies to every symbol asked
    next. Subclasses carry `endpoint` and `status`."""

    endpoint: str
    status: int


class VendorUnavailableError(Exception):
    """The vendor did not answer: a non-200 that is not a throttle, a transport
    error or timeout, or a body that is not what the vendor sends.

    Deliberately not a subclass of VendorThrottledError: the passes stamp these
    and count them, and never stamp a throttle. Subclasses carry `endpoint`."""

    endpoint: str
