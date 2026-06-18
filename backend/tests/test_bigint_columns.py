"""Count columns must be 64-bit BIGINT, not 32-bit INTEGER.

Regression guard for the integer-overflow incident: a high-turnover ticker
(ADTX, ~5.28B shares) overflowed the 32-bit INTEGER `tickers.volume` and
aborted the whole scan-tick write every cycle (NumericValueOutOfRange),
which also flooded Sentry. These columns must stay BigInteger.
"""
from sqlalchemy import BigInteger

from app.models.calendar_events import IPOEvent
from app.models.holdings import InstitutionalHolding
from app.models.ticker import Ticker


def test_ticker_volume_is_bigint():
    assert isinstance(Ticker.__table__.c.volume.type, BigInteger)


def test_holdings_shares_is_bigint():
    assert isinstance(InstitutionalHolding.__table__.c.shares.type, BigInteger)


def test_ipo_shares_offered_is_bigint():
    assert isinstance(IPOEvent.__table__.c.shares_offered.type, BigInteger)
