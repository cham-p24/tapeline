"""Which listings are a company's common stock (`services/security_type.py`).

The insider pass gives an issuer's Form 4 lines to every common-stock ticker of
its CIK and to nothing else (`services/edgar_form4.py`, point 5), so this
predicate decides who carries an insider reading. Its failure modes are
asymmetric: flagging a real common stock withholds that stock's reading
entirely, while missing a preferred leaves it where the 2026-09-17 rule already
left most of them. So the first thing pinned here is PRECISION.

THE HAND LABELS. 125 symbols labelled by hand on 2026-09-18 from the stored
name, symbol, price, volume and market cap, BEFORE the predicate was run
against them (by the peer session "Clear smart-money scores after Form 4 ages
out"). Names and asset classes are the REAL production values, read-only on
2026-09-19. Measured:

* precision: none of the 77 labelled commons is flagged;
* recall: 42 of the 48 labelled non-commons are flagged (38 by the predicate,
  plus Strategy's four preferreds by the explicit symbol list). The six misses
  are pinned below as misses, so a change that starts catching them is noticed
  and the label reconsidered. Five are labels, not errors, for Form 4
  purposes; OBTC ("Common Units of Beneficial Interest", a grantor trust) is
  the issuer's only listed equity, so it is harmless for attribution too.

`universe` here is the labelled symbols plus the four-letter roots that exist
in production, which is all the fifth-letter U/R/W rules read.
"""
from __future__ import annotations

import pytest

from app.services.security_type import is_common_stock, is_non_common_listing

# (symbol, name as stored in production 2026-09-19, asset_class)
NOT_COMMON: list[tuple[str, str, str]] = [
    ('ADAMK', 'Adamas Trust, Inc. 9.600% Senior Notes Due 2031', 'equity'),
    ('ATLCZ', 'Atlanticus Holdings Corporation 9.25% Senior Notes due 2029', 'equity'),
    ('BA.PRA', 'Boeing Co', 'equity'),
    ('BCTXL', 'BriaCell Therapeutics Corp. Warrant expiring 2031', 'equity'),
    ('BHFAL', 'Brighthouse Financial, Inc. 6.25% Junior Subordinated Debentures due 2058', 'equity'),
    ('BHFAM', 'Brighthouse Financial, Inc. Depositary shares each representing a 1/1,000th Interest in a Share of 4.625% Non-Cumulative Preferred Stock, Series D', 'equity'),
    ('BTSGU', 'Brightspring Health Services Inc', 'equity'),
    ('BWBBP', 'Bridgewater Bancshares, Inc. Depositary Shares, Each Representing a 1/100th Interest in a Share of 5.875% Non-Cumulative Perpetual Preferred Stock, Series A', 'equity'),
    ('CNOBP', 'ConnectOne Bancorp, Inc. Depositary Shares, each representing a 1/40th interest in a share of 5.25% Fixed-Rate Reset Non-Cumulative Perpetual Preferred Stock, Series A', 'equity'),
    ('DHCNL', 'Diversified Healthcare Trust 6.25% Senior Notes Due 2046', 'equity'),
    ('EMP', 'Entergy Mississippi, LLC First Mortgage Bonds, 4.90% Series due October 1, 2066', 'equity'),
    ('FITBO', 'Fifth Third Bancorp Depositary Shares each representing a 1/1000th ownership interest in a share of Non-Cumulative Perpetual Preferred Stock, Series K', 'equity'),
    ('FULTP', 'Fulton Financial Corporation Depositary Shares, Each Representing a 1/40th Interest in a Share of Fixed Rate Non-Cumulative Perpetual Preferred Stock, Series A', 'equity'),
    ('GAINN', 'Gladstone Investment Corporation 5.00% Notes Due 2026', 'equity'),
    ('GECCG', 'Great Elm Capital Corp. 7.75% Notes Due 2030', 'equity'),
    ('GECCO', 'Great Elm Capital Corp. 5.875% Notes due 2026', 'equity'),
    ('GOOGN', 'Alphabet Inc. Depositary Shares representing a 1/20th Interest in a Share of Series B Mandatory Convertible Preferred Stock', 'equity'),
    ('HAVAR', 'Harvard Ave Acquisition Corporation Rights that convert on a 1/10th of 1 basis to Class A ordinary Shares', 'equity'),
    ('HONAV', 'Honeywell Aerospace Inc. Common Stock When Issued', 'equity'),
    ('IMPPP', 'Imperial Petroleum Inc. 8.75% Series A Cumulative Redeemable Perpetual Preferred Shares', 'equity'),
    ('JSM', 'Navient Corporation 6% Senior Notes due December 15, 2043', 'equity'),
    ('LILAV', 'Liberty Latin America Ltd Class A Common Stock Ex-Distribution When Issued', 'equity'),
    ('LILKV', 'Liberty Latin America Ltd Class C Common Stock Ex-Distribution When Issued', 'equity'),
    ('MARPS', 'Marine Petroleum Trust', 'equity'),
    ('MBINM', 'Merchants Bancorp Depositary Shares, Each Representing a 1/40th Interest in a Share of 8.25% Fixed-Rate Reset Series D Non-Cumulative Perpetual Preferred Stock', 'equity'),
    ('MBINN', 'Merchants Bancorp Depositary Shares Preferred Series C', 'equity'),
    ('MCHPP', 'Microchip Technology Incorporated Depositary Shares Each Representing a 1/20th Interest in a Share of 7.50% Series A Mandatory Convertible Preferred Stock', 'equity'),
    ('METCZ', 'Ramaco Resources, Inc. 8.375% Senior Notes due 2029', 'equity'),
    ('MTR', 'Mesa Royalty Trust', 'equity'),
    ('NEE.PRT', 'Nextera Energy Inc', 'equity'),
    ('NEWTG', 'NewtekOne, Inc. 8.50% Fixed Rate Senior Notes due 2029', 'equity'),
    ('NMFCZ', 'New Mountain Finance Corporation 8.250% Notes due 2028', 'equity'),
    ('OBTC', 'Osprey Bitcoin Trust Common Units of Beneficial Interest', 'equity'),
    ('OCCIN', 'OFS Credit Company, Inc. 5.25% Series E Term Preferred Stock Due 2026', 'equity'),
    ('OFSSO', 'OFS Capital Corporation 7.50% Notes due 2028', 'equity'),
    ('OXLCL', 'Oxford Lane Capital Corp. 6.75% Notes due 2031', 'equity'),
    ('OXSQH', 'Oxford Square Capital Corp. 7.75% Notes due 2030', 'equity'),
    ('RWAYL', 'Runway Growth Finance Corp. 7.50% Notes due 2027', 'equity'),
    ('STRC', 'Strategy Inc', 'equity'),
    ('STRD', 'Strategy Inc', 'equity'),
    ('STRF', 'Strategy Inc', 'equity'),
    ('STRK', 'Strategy Inc', 'equity'),
    ('TMUSI', 'T-Mobile US, Inc. 5.500% Senior Notes due June 2070', 'equity'),
    ('TPGXL', 'TPG Operating Group II, L.P. 6.950% Fixed-Rate Junior Subordinated Notes due 2064', 'equity'),
    ('WHFCL', 'WhiteHorse Finance, Inc. 7.875% Notes due 2028', 'equity'),
    ('WHLRL', 'Wheeler Real Estate Investment Trust, Inc. 7.00% Senior Subordinated Convertible Notes Due 2031', 'equity'),
    ('XELLL', 'Xcel Energy Inc. 6.25% Junior Subordinated Notes, Series due 2085', 'equity'),
    ('ZVZZT', 'ZVZZT', 'equity'),
]

COMMON: list[tuple[str, str, str]] = [
    ('AFCG', 'Advanced Flower Capital Inc. Common Stock', 'equity'),
    ('AKO.A', 'Embotelladora Andina S.A. Series A', 'equity'),
    ('ALCY', 'Alchemy Investments Acquisition Corp 1 Class A Ordinary Shares', 'equity'),
    ('ALPX', 'Alpex Acquisition Corporation Class A Ordinary Shares', 'equity'),
    ('AMST', 'Amesite Inc.', 'equity'),
    ('APAC', 'StoneBridge Acquisition II Corporation Class A Ordinary Shares', 'equity'),
    ('ARQ', 'Arq, Inc. Common Stock', 'equity'),
    ('ATII', 'Archimedes Tech SPAC Partners II Co. Ordinary Shares', 'equity'),
    ('AWRE', 'Aware Inc', 'equity'),
    ('BCAT', 'BlackRock Capital Allocation Term Trust', 'equity'),
    ('BCSS', 'Bain Capital GSS Investment Corp.', 'equity'),
    ('BEKE', 'KE Holdings Inc. American Depositary Shares (each representing three Class A Ordinary Shares)', 'equity'),
    ('BFC', 'Bank First Corporation Common Stock', 'equity'),
    ('BIP', 'Brookfield Infrastructure Partners L.P. Limited Partnership Units', 'equity'),
    ('BLZR', 'Trailblazer Acquisition Corp. Class A Ordinary Shares', 'equity'),
    ('BOH', 'Bank of Hawaii Corp.', 'equity'),
    ('BRAG', 'Bragg Gaming Group Inc. Common Shares', 'equity'),
    ('BRK-A', 'Berkshire Hathaway Inc', 'equity'),
    ('BRK.A', 'Berkshire Hathaway Inc.', 'equity'),
    ('CAN', 'Canaan Inc. American Depositary Shares', 'equity'),
    ('CAPL', 'CrossAmerica Partners LP Common units representing limited partner interests', 'equity'),
    ('CCD', 'Calamos Dynamic Convertible & Income Fund', 'equity'),
    ('CHCO', 'City Holding Co', 'equity'),
    ('CHW', 'Calamos Global Dynamic Income Fund', 'equity'),
    ('CISS', 'C3is Inc. Common Stock', 'equity'),
    ('CMCT', 'Creative Media & Community Trust Corporation Common stock', 'equity'),
    ('CMII', 'Columbus Circle Capital Corp II Class A Ordinary Shares', 'equity'),
    ('CMRC', 'Commerce.com, Inc. Series 1 Common Stock', 'equity'),
    ('CRAC', 'Crown Reserve Acquisition Corp. I Class A Ordinary Shares', 'equity'),
    ('CSAN', 'Cosan S.A. American Depositary Shares (each representing four Common Shares)', 'equity'),
    ('CXM', 'Sprinklr, Inc.', 'equity'),
    ('DMII', 'Drugs Made In America Acquisition II Corp. Ordinary Shares', 'equity'),
    ('ECPG', 'Encore Capital Group, Inc.', 'equity'),
    ('EMA', 'Emera Incorporated', 'equity'),
    ('ET', 'Energy Transfer LP Common Units representing limited partner interests', 'equity'),
    ('EVO', 'Evotec SE American Depositary Shares', 'equity'),
    ('FCBC', 'First Community Bankshares, Inc. (VA)', 'equity'),
    ('FSUN', 'FirstSun Capital Bancorp Common Stock', 'equity'),
    ('FVCB', 'FVCBankcorp, Inc. Common Stock', 'equity'),
    ('GBFH', 'GBank Financial Holdings Inc. Common Stock', 'equity'),
    ('GLPI', 'Gaming and Leisure Properties, Inc.', 'equity'),
    ('IPCX', 'Inflection Point Acquisition Corp. III Class A Ordinary Shares', 'equity'),
    ('IPFX', 'Inflection Point Acquisition Corp. VI Class A Ordinary Shares', 'equity'),
    ('IRS', 'IRSA Inversiones y Representaciones S.A. Global Depositary Shares', 'equity'),
    ('KFII', 'K&F Growth Acquisition Corp. II Class A Ordinary shares', 'equity'),
    ('LEN.B', 'Lennar Corporation Class B', 'equity'),
    ('LLYVA', 'Liberty Live Holdings, Inc. Series A Liberty Live Group Common Stock', 'equity'),
    ('LSH', 'Lakeside Holding Limited Common Stock', 'equity'),
    ('LUD', 'Luda Technology Group Limited', 'equity'),
    ('MDGL', 'Madrigal Pharmaceuticals, Inc. Common Stock', 'equity'),
    ('MKLY', 'McKinley Acquisition Corporation Class A Ordinary Shares', 'equity'),
    ('MSDL', 'Morgan Stanley Direct Lending Fund', 'equity'),
    ('MSTR', 'Strategy Inc', 'equity'),
    ('NAD', 'Nuveen Quality Municipal Income Fund', 'equity'),
    ('NBHC', 'National Bank Holdings Corp', 'equity'),
    ('NEU', 'NewMarket Corp', 'equity'),
    ('NNBR', 'NN Inc', 'equity'),
    ('NTWO', 'Newbury Street II Acquisition Corp Class A Ordinary Shares', 'equity'),
    ('NXB', 'NextBoat Inc.', 'equity'),
    ('NYXH', 'Nyxoah SA Ordinary Shares', 'equity'),
    ('OHAC', 'Oceanhawk Acquisition Corp. Class A Ordinary Shares', 'equity'),
    ('OTLY', 'Oatly Group AB American Depositary Shares', 'equity'),
    ('PAAC', 'Proem Acquisition Corp I Ordinary Shares', 'equity'),
    ('PAVS', 'Paranovus Entertainment Technology Ltd', 'equity'),
    ('PDC', 'Perpetuals.com Ltd American Depositary Shares', 'equity'),
    ('PFBC', 'Preferred Bank', 'equity'),
    ('PRFX', 'PRF Technologies Ltd', 'equity'),
    ('RNAC', 'Cartesian Therapeutics Inc', 'equity'),
    ('ROMA', 'Roma Green Finance Limited Class A Ordinary Shares', 'equity'),
    ('SBC', 'SBC Medical Group Holdings Inc', 'equity'),
    ('SES', 'SES AI Corp', 'equity'),
    ('SMFG', 'Sumitomo Mitsui Financial Group, Inc', 'equity'),
    ('SVAQ', 'Silicon Valley Acquisition Corp. Class A Ordinary Shares', 'equity'),
    ('TVIV', 'Texas Ventures Acquisition IV Corp Class A Ordinary Shares', 'equity'),
    ('UGP', 'Ultrapar Participacoes SA', 'equity'),
    ('WDH', 'Waterdrop Inc. American Depositary Shares (each representing the right to receive 10 Class A Ordinary Shares)', 'equity'),
    ('XTIA', 'XTI Aerospace, Inc. Common Stock', 'equity'),
]

#: Four-letter roots that exist in production, for the U/R/W symbol rules.
ROOTS = frozenset(['ADAM', 'ATLC', 'BCTX', 'BTSG', 'CNOB', 'FITB', 'FULT', 'GAIN', 'GECC', 'GOOG', 'GREE', 'HAVA', 'HONA', 'IMPP', 'LILA', 'MBIN', 'MCHP', 'METC', 'NEWT', 'NMFC', 'OCCI', 'OXLC', 'OXSQ', 'RWAY', 'TMUS', 'WHLR'])

UNIVERSE = frozenset(s for s, _n, _a in NOT_COMMON + COMMON) | ROOTS

#: Labelled non-common, NOT flagged - by design, see the module docstring.
#: HONAV, LILAV, LILKV: when-issued common stock. MARPS, MTR: royalty trusts
#: whose only listing is the trust's equity. OBTC: a grantor trust's units.
KNOWN_MISSES = frozenset({"HONAV", "LILAV", "LILKV", "MARPS", "MTR", "OBTC"})


def test_the_label_set_is_the_one_measured() -> None:
    assert (len(NOT_COMMON), len(COMMON)) == (48, 77)
    assert len({s for s, _n, _a in NOT_COMMON + COMMON}) == 125


@pytest.mark.parametrize(("symbol", "name", "asset_class"), COMMON, ids=[c[0] for c in COMMON])
def test_no_labelled_common_stock_is_flagged(symbol: str, name: str, asset_class: str) -> None:
    """Precision. A false positive here withholds a real stock's insider
    reading, so every labelled common must pass."""
    assert not is_non_common_listing(symbol, name, UNIVERSE)
    assert is_common_stock(symbol, name, asset_class, UNIVERSE)


@pytest.mark.parametrize(
    ("symbol", "name", "asset_class"),
    [c for c in NOT_COMMON if c[0] not in KNOWN_MISSES],
    ids=[c[0] for c in NOT_COMMON if c[0] not in KNOWN_MISSES],
)
def test_labelled_non_common_listings_are_flagged(symbol: str, name: str, asset_class: str) -> None:
    assert is_non_common_listing(symbol, name, UNIVERSE)
    assert not is_common_stock(symbol, name, asset_class, UNIVERSE)


def test_the_known_misses_are_still_misses() -> None:
    """Pinned so a rule that starts catching one is a visible decision, not a
    silent change of who carries an insider reading."""
    names = {s: n for s, n, _a in NOT_COMMON}
    assert set(names) >= KNOWN_MISSES
    assert [s for s in sorted(KNOWN_MISSES) if is_non_common_listing(s, names[s], UNIVERSE)] == []


def test_precision_and_recall_on_the_labels() -> None:
    flagged = {s for s, n, _a in NOT_COMMON + COMMON if is_non_common_listing(s, n, UNIVERSE)}
    labelled = {s for s, _n, _a in NOT_COMMON}
    assert flagged <= labelled, f"labelled commons flagged: {sorted(flagged - labelled)}"
    assert len(flagged) == 42


# ---------------------------------------------------------------------------
# The listings the attribution tests lean on, with their real names
# ---------------------------------------------------------------------------

REAL_COMMON = [
    ("GOOG", "Alphabet Inc. Class C Capital Stock", "equity"),
    ("GOOGL", "Alphabet Inc.", "equity"),
    ("NWS", "News Corp", "equity"),
    ("NWSA", "News Corp", "equity"),
    ("BRK.A", "Berkshire Hathaway Inc.", "equity"),
    ("BRK.B", "Berkshire Hathaway", "equity"),
    ("BRK-A", "Berkshire Hathaway Inc", "equity"),
    ("BRK-B", "Berkshire Hathaway Inc", "equity"),
    ("MSTR", "Strategy Inc", "equity"),
    ("JPM", "JPMorgan Chase", "equity"),
    # An ADR: "Depositary Shares" alone would read as a preferred.
    ("CEPU", "Central Puerto S.A. American Depositary Shares (each represents ten Common Shares)", "equity"),
    # "Preferred" is the bank's name, not a security type.
    ("PFBC", "Preferred Bank", "equity"),
    # An MLP's common units are its equity.
    ("CAPL", "CrossAmerica Partners LP Common units representing limited partner interests", "equity"),
    ("STLN", "Starling Oncology, Inc. Common Stock", "equity"),
]

REAL_NON_COMMON = [
    # Named exactly like MSTR: only the explicit symbol list catches these.
    ("STRK", "Strategy Inc", "equity"),
    ("STRC", "Strategy Inc", "equity"),
    ("STRF", "Strategy Inc", "equity"),
    ("STRD", "Strategy Inc", "equity"),
    ("TMUSZ", "T-Mobile US, Inc. 5.500% Senior Notes due March 2070", "equity"),
    ("GREEL", "Greenidge Generation Holdings Inc. 8.50% Senior Notes due 2026", "equity"),
    ("IMPPP", "Imperial Petroleum Inc. 8.75% Series A Cumulative Redeemable Perpetual Preferred Shares", "equity"),
    ("BHFAO", "Brighthouse Financial, Inc. Depositary Shares 6.75% Non-Cum Pfd Series B", "equity"),
    ("GOOGN", "Alphabet Inc. Depositary Shares representing a 1/20th Interest in a Share of "
              "Series B Mandatory Convertible Preferred Stock", "equity"),
    ("NRGU", "MicroSectors U.S. Big Oil 3x Leveraged ETNs due February 17, 2045", "etf"),
    ("VYLD", "Inverse VIX Short-Term Futures ETNs due March 22, 2045", "etf"),
    ("AMJB", "Alerian MLP Index ETNs due January 28 2044", "etf"),
    ("AMUB", "ETRACS Alerian MLP Index ETN Series B due July 18, 2042", "etf"),
    ("BCTXL", "BriaCell Therapeutics Corp. Warrant expiring 2031", "equity"),
    ("OIMAU", "OneIM Acquisition Corp. Units", "equity"),
    ("HAVAR", "Harvard Ave Acquisition Corporation Rights that convert on a 1/10th of 1 basis "
              "to Class A ordinary Shares", "equity"),
]


@pytest.mark.parametrize(("symbol", "name", "asset_class"), REAL_COMMON, ids=[c[0] for c in REAL_COMMON])
def test_real_common_stocks(symbol: str, name: str, asset_class: str) -> None:
    assert is_common_stock(symbol, name, asset_class, UNIVERSE)


@pytest.mark.parametrize(
    ("symbol", "name", "asset_class"), REAL_NON_COMMON, ids=[c[0] for c in REAL_NON_COMMON],
)
def test_real_non_common_listings(symbol: str, name: str, asset_class: str) -> None:
    assert not is_common_stock(symbol, name, asset_class, UNIVERSE)


def test_an_etn_is_flagged_by_name_even_outside_the_etf_bucket() -> None:
    """The asset class gate would catch an ETN stored as "etf" on its own, so
    this pins the NAME rule: an ETN that discovery stored as equity."""
    assert is_non_common_listing("AMUB", "ETRACS Alerian MLP Index ETN Series B due July 18, 2042")
    assert not is_common_stock("AMUB", "ETRACS Alerian MLP Index ETN Series B due July 18, 2042", "equity")


def test_strategys_preferreds_are_caught_by_symbol_not_by_name() -> None:
    """Mutation: drop the explicit list - "Strategy Inc" reads as common and
    STRK carries MSTR's insider sales again (#862's headline bug)."""
    for sym in ("STRK", "STRC", "STRF", "STRD"):
        assert is_non_common_listing(sym, "Strategy Inc")
    assert not is_non_common_listing("MSTR", "Strategy Inc")
    # The same holds for a lower-case or padded symbol.
    assert is_non_common_listing(" strk ", "Strategy Inc")


def test_outside_the_equity_bucket_nothing_is_common_stock() -> None:
    """An ETF has no insiders of its own; a row whose class is unknown is not
    KNOWN to be common stock. "stock" is the equity bucket's synonym."""
    assert not is_common_stock("USO", "United States Oil", "etf")
    assert not is_common_stock("AAPL", "Apple Inc.", None)
    assert not is_common_stock("AAPL", "Apple Inc.", "crypto")
    assert is_common_stock("AAPL", "Apple Inc.", " Stock ")


def test_the_fifth_letter_rules_need_the_root_in_the_universe() -> None:
    """OIMAU-style units, rights and warrants are only called so when their
    four-letter root is listed; a common stock that happens to be five letters
    ending in U, R or W is not."""
    assert is_non_common_listing("ABCDU", "ABCD Acquisition Corp", {"ABCD"})
    assert not is_non_common_listing("ABCDU", "ABCD Acquisition Corp", {"ZZZZ"})
    assert is_non_common_listing("ABCDR", "ABCD Acquisition Corp", {"ABCD"})
    # A W is a warrant only when the name says nothing (a placeholder).
    assert is_non_common_listing("ABCDW", "ABCDW", {"ABCD"})
    assert not is_non_common_listing("ABCDW", "ABCD Widgets Inc", {"ABCD"})
    assert not is_non_common_listing("ABCDW", "ABCDW", set())
