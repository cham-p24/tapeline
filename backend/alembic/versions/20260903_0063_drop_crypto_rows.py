"""Delete crypto-classed ticker rows — they collide with real listings.

Measured on production 2026-09-03. Four REAL, named, listed securities were
being published with a cryptocurrency's price, because the signal sheet writes
a crypto row over the vendor's equity row of the same symbol:

  SOL  Emeren Group Ltd (NYSE solar, ~$1.94)   published at $64.45   (Solana)
  EOS  Eaton Vance Enhanced Equity Income II   published at $0.0625  (EOS token)
  BGB  Blackstone Strategic Credit 2027 Term   published at $1.8568
  LEO  BNY Mellon Strategic Municipals Inc     published at $6.15    (UNUS SED LEO)

Each carried a six-factor score and a CAUTION/NEUTRAL label on a public
per-ticker page with JSON-LD structured data — i.e. a false statement of fact
about a named real security, published under a no-AFSL publisher posture and
fed to the answer engines that are currently the only channel producing
signups. That is worse than serving nothing.

54 rows carry a crypto asset_class (stored with the sheet's raw emoji
decoration, e.g. "₿ crypto"). Delete all of them:

  - The ~50 pure-crypto rows (ADA, DOT, …) do not belong in a US-equity/ETF
    scanner at all. The six-factor model cannot score a token — no Form 4
    filings and no company fundamentals means ~45% of the composite weight is
    a constant, capping every token at 77.5/100.
  - The 4 collision rows are CORRUPT, not merely unwanted. Deleting them lets
    `signal_publisher._refresh_universe` re-create each symbol from the vendor
    with the correct name, asset class and price on its next run.

Restoring the corrupt rows in place is deliberately NOT attempted: this
migration has no access to correct prices, and writing a guessed one would
repeat the original sin in the other direction.

Forward-only. `services/sheet_feed.parse_signals_csv` now drops crypto rows at
ingest, so they do not come back. `tests/test_no_crypto_in_equity_universe.py`
is the regression guard.

Revision id kept short — version_num is VARCHAR(32).
"""
from alembic import op
import sqlalchemy as sa

revision = "0063_drop_crypto"
down_revision = "0062_ticker_last_agg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ILIKE '%crypto%' rather than an equality: the stored values carry the
    # sheet's emoji prefix ("₿ crypto") as well as, potentially, the clean
    # "crypto" that normalize_asset_class produces.
    op.execute(
        sa.text("DELETE FROM tickers WHERE asset_class ILIKE '%crypto%'")
    )


def downgrade() -> None:
    # Deliberately empty. These rows were corrupt or out of scope; recreating
    # them would republish the collision this migration exists to end. The
    # legitimate equities among them are restored by the vendor refresh.
    pass
