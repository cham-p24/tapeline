"""Shared guards for the one-off broadcast scripts that run unattended in public.

`scripts/update_send.py` (the September product update) and the survey reminder
in `scripts/survey_send.py` both run from a GitHub Actions workflow over
`flyctl ssh`. This repo is public, so each job's log is world-readable, and a
retry of either is a human pressing "Re-run" with no view of what Resend has.
Two properties follow, and both scripts need exactly the same answer to each:

  * NO ADDRESS IN THE LOG. `--quiet` gates the scripts' own per-recipient lines,
    but it cannot reach what other code writes. `send_email` logs `to=` at
    WARNING when there is no Resend key and at ERROR when its undeliverable check
    fails; an exception message can carry an address; and with no logging
    configured Python prints WARNING and above straight to stderr, which is the
    same public log. `configure_quiet_logging` routes every log line — and any
    uncaught traceback — through `RedactAddresses`.
  * AN ERROR AFTER THE REQUEST LEFT IS NOT A FAILURE. `outcome_unknown` separates
    errors after which Resend may already have queued the email (stamp it, so a
    retry does not send it again) from errors that prove Resend never had it
    (leave it unstamped, so a retry is the fix).

Extracted from `update_send.py` (#814) so the survey reminder uses the same
implementation rather than a second copy, and so neither send depends on the
other script still existing: both workflows are deleted once they have run.
"""
from __future__ import annotations

import logging
import re
import sys
from types import TracebackType

#: Anything shaped like local@domain. Deliberately loose: redacting a
#: non-address that happens to contain "@" costs nothing in a count-only log,
#: and missing a real address costs a customer's privacy.
ADDRESS_SHAPED = re.compile(r"[^\s<>\"'(),;:\[\]]+@[^\s<>\"'(),;:\[\]]+")


class RedactAddresses(logging.Formatter):
    """Formats a record — traceback included — then removes address-shaped text."""

    def format(self, record: logging.LogRecord) -> str:
        return ADDRESS_SHAPED.sub("<address>", super().format(record))


def _log_uncaught(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    """sys.excepthook under --quiet: an uncaught traceback goes through the
    redacting handler instead of being printed raw by the interpreter."""
    logging.getLogger("uncaught").critical(
        "run aborted by an uncaught exception", exc_info=(exc_type, exc, tb),
    )


def configure_quiet_logging() -> logging.Handler:
    """Route every log line, and any uncaught traceback, through RedactAddresses."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(RedactAddresses("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.WARNING)
    sys.excepthook = _log_uncaught
    return handler


def outcome_unknown(exc: BaseException) -> bool:
    """Whether Resend may have accepted the email even though the send raised.

    True only for errors that can happen AFTER the request reached Resend: a
    timeout or broken connection while writing the request or reading the
    response, a malformed response, or a 5xx (a gateway can answer 502/504
    after the upstream queued the email). False for anything that proves
    Resend never took it: a connect or pool timeout, a refused connection, a
    4xx rejection, or an error raised before the POST, such as a render bug.

    `send_email` posts with a 10-second timeout and then raise_for_status(), so
    treating the first group as failures leaves the recipient unstamped and the
    retry mails them a second time (reproduced for the product update: a
    ReadTimeout on the first call, two deliveries across two runs).
    """
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (
        httpx.ReadTimeout, httpx.WriteTimeout,
        httpx.ReadError, httpx.WriteError, httpx.CloseError,
        httpx.RemoteProtocolError, httpx.DecodingError,
    ))
