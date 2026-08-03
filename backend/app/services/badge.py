"""Embeddable SVG score badge — a distribution loop.

Anyone can drop `<img src="https://api.tapeline.io/api/public/badge/NVDA.svg">`
on a blog, a GitHub README, a StockTwits post, or a Discord embed. Each render
is a brand impression + a link back to the ticker page — growth through usage,
not through us posting anything.

Descriptive-only by construction: the badge shows the numeric Tapeline Score and
its published descriptive band label (HIGH CONVICTION … WEAK). No buy/sell/
recommend language — same compliance posture as the public ticker pages.
"""
from __future__ import annotations

# Score bands → (fallback label, badge colour). Colours are dark enough to keep
# white text legible. Thresholds mirror the canonical signal taxonomy in
# services/tier.py / the public /how-it-works pages — do not drift them.
_BANDS: list[tuple[float, str, str]] = [
    (85.0, "HIGH CONVICTION", "#15803d"),
    (70.0, "STRONG SETUP", "#16a34a"),
    (55.0, "CONSTRUCTIVE", "#2563eb"),
    (40.0, "NEUTRAL", "#475569"),
    (25.0, "CAUTION", "#b45309"),
    (0.0, "WEAK", "#dc2626"),
]

_NEUTRAL_COLOR = "#475569"


def _band(score: float) -> tuple[str, str]:
    for floor, label, color in _BANDS:
        if score >= floor:
            return label, color
    return "WEAK", "#dc2626"


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Approximate advance width of 11px bold Verdana. Good enough for padding a
# two-segment badge; exact per-glyph metrics aren't worth a font dependency.
_CHAR_W = 7.0
_PAD = 10.0
_HEIGHT = 28


def render_score_badge(
    symbol: str,
    name: str | None,
    score: float | None,
    signal: str | None,
) -> str:
    """Return a self-contained SVG string for the given ticker's score.

    Renders a graceful "no score" badge (never raises) when the symbol is
    unknown or unscored, so an embedded <img> never breaks.
    """
    symbol = (symbol or "?").upper()

    if score is None:
        left_label = "no score"
        color = _NEUTRAL_COLOR
        score_txt = "—"
    else:
        derived_label, color = _band(score)
        left_label = (signal or derived_label).upper()
        # FLOOR, not round: the band labels use `score >= threshold`, so a 69.7
        # rounded up to "70" would read "70 · CONSTRUCTIVE" — contradicting the
        # published band (70 = STRONG SETUP). floor(score) is always in the same
        # band as the stored signal, so the number and label never disagree.
        score_txt = f"{int(score)}"

    left = f"tapeline · {symbol}"
    right = f"{score_txt} · {left_label}"

    lw = round(len(left) * _CHAR_W + 2 * _PAD)
    rw = round(len(right) * _CHAR_W + 2 * _PAD)
    total = lw + rw

    aria = (
        f"Tapeline Score for {symbol}"
        + (f" ({name})" if name else "")
        + (f": {score_txt} — {left_label}" if score is not None else ": no score yet")
    )

    left_e = _xml_escape(left)
    right_e = _xml_escape(right)
    aria_e = _xml_escape(aria)
    color_e = _xml_escape(color)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{_HEIGHT}" '
        f'role="img" aria-label="{aria_e}">'
        f"<title>{aria_e}</title>"
        f'<clipPath id="r"><rect width="{total}" height="{_HEIGHT}" rx="5"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{lw}" height="{_HEIGHT}" fill="#11151d"/>'
        f'<rect x="{lw}" width="{rw}" height="{_HEIGHT}" fill="{color_e}"/>'
        f"</g>"
        f'<g fill="#ffffff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11" font-weight="bold">'
        f'<text x="{lw / 2:.0f}" y="18">{left_e}</text>'
        f'<text x="{lw + rw / 2:.0f}" y="18">{right_e}</text>'
        f"</g>"
        f"</svg>"
    )
