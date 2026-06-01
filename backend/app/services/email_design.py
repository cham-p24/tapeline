"""Tapeline email design system.

Every renderer in `app.services.email` composes its body via the helpers
in this module and wraps the result with `shell()`. The shell handles:

- **Light + dark mode** via `@media (prefers-color-scheme: dark)`. Default
  is light because (a) Gmail web/mobile ignores the media query and
  auto-inverts light emails when the user's Gmail theme is dark, so a
  light base ends up looking right in both modes, and (b) Stripe / Linear
  / Vercel / Mercury / Notion all default light — finance + SaaS norm.
- **System font stack.** Inter and JetBrains Mono don't load in 80%+ of
  email clients; we fall back to the user's system UI font, which is what
  every best-in-class SaaS does.
- **560px max-width container** with generous section padding.
- **Preheader text** — the hidden snippet that previews in the inbox list
  next to the subject. Massive open-rate lever; every transactional email
  should have one.
- **MSO conditionals** for Outlook desktop button rendering (VML).
- **color-scheme meta** so Gmail doesn't double-invert our dark overrides.

Inline styles carry the BASE (light) appearance because Outlook desktop +
Gmail web only reliably respect inline. The `<style>` block in `<head>`
provides the dark override via media query — Apple Mail, Outlook iOS,
Hey, and most webmail clients honour it.

The helpers below are intentionally small + composable. A renderer
typically reads:

    shell(
        h1("Welcome, " + name) +
        lead("Your 14-day Premium trial is live.") +
        button("Open the scanner", "https://tapeline.io/app/scanner") +
        muted_footnote("No card on file. We'll remind you before the trial ends."),
        preheader="Your 14-day Premium trial is live — open the scanner.",
    )

Never inline raw HTML in a renderer if a helper exists for it. The
consistency is the brand.
"""
from __future__ import annotations

# ── Design tokens ────────────────────────────────────────────────────────────
#
# Light defaults are inline on every element. Dark overrides live in the
# <style> block via `@media (prefers-color-scheme: dark)` and are scoped to
# semantic classes (.tl-bg, .tl-fg, .tl-card, etc.) so the override is
# class-driven, not selector-prefix driven.
#
# Keep the palette minimal: one accent, one neutral scale per mode, and
# the four signal colours that already encode our product semantics
# (green = bullish, red = bearish, amber = caution, slate = neutral).

# Light mode
# LIGHT_BG was pure white #ffffff until 2026-05-19 — bumped to a soft
# blue tint so emails carry the brand atmosphere we ship on the website
# (body::before page-wide gradient at ~14% accent). Hex #f4f8ff is
# basically white with a hint of iOS systemBlue — invisible to anyone
# scanning quickly, recognisable as "the Tapeline emails look like
# Tapeline" to anyone who's been on the site. Email clients vary in
# CSS gradient support (Outlook desktop renders nothing) so a solid
# tint is more reliable than a gradient.
LIGHT_BG = "#e8f0fc"           # blue-tinted atmosphere (canvas + card insets) —
                               # matches the web app's accent-glow background
LIGHT_PANEL = "#ffffff"        # clean white reading surface the content floats on
LIGHT_BORDER = "#dbe3f0"       # soft blue-grey hairline
LIGHT_FG = "#0a0a0a"           # primary text (web --fg)
LIGHT_MUTED = "#52525b"        # secondary text — darkened from #6b7280 for legibility
LIGHT_SUBTLE = "#6b7280"       # footnote / footer — darkened from #9ca3af, which
                               # failed WCAG AA (2.8:1) on the panel

# Dark mode (used in `@media (prefers-color-scheme: dark)`)
# DARK_BG was #0a0a0a — bumped to a faint blue-shifted near-black for
# parity with the light-mode blue tint above. Still effectively dark
# but with the same brand hue at the canvas level.
DARK_BG = "#0a0d14"            # blue-shifted near-black atmosphere (canvas + insets)
DARK_PANEL = "#121723"        # blue-tinted dark reading surface
DARK_BORDER = "#252b38"       # blue-grey hairline (more visible than #1f1f23)
DARK_FG = "#f4f4f5"           # primary text (web --fg)
DARK_MUTED = "#a9b1bf"        # secondary text — brightened from #9ca3af for legibility
DARK_SUBTLE = "#8b93a3"       # footnote / footer — brightened from #6b7280 for contrast

ACCENT = "#007AFF"             # iOS systemBlue — matches the web app's --accent
ACCENT_HOVER = "#0064dc"

# Signal palette — saturated enough to read on both light and dark.
SIG_BULL = "#10b981"            # HIGH CONVICTION / STRONG SETUP
SIG_CONSTRUCTIVE = "#14b8a6"    # CONSTRUCTIVE
SIG_NEUTRAL = "#94a3b8"         # NEUTRAL
SIG_CAUTION = "#f59e0b"         # CAUTION
SIG_BEAR = "#ef4444"            # WEAK

# System font stacks — what every best-in-class SaaS email uses. Web
# fonts (Inter, JetBrains Mono) don't load in Gmail/Outlook desktop, so
# falling back to the system UI font is the most predictable choice.
FONT_SANS = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)
FONT_MONO = (
    "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "
    "'Liberation Mono', 'Courier New', monospace"
)


# ── Shell ────────────────────────────────────────────────────────────────────

def shell(body: str, *, preheader: str = "") -> str:
    """Wrap a body fragment in the full Tapeline email document.

    `preheader` is the hidden snippet that shows in the inbox preview
    next to the subject line. Make it a one-sentence summary of the
    email's payload — not a repeat of the subject. Open-rate lever.
    """
    preheader_html = (
        f'<div style="display:none;font-size:1px;color:{LIGHT_BG};'
        f'line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;'
        f'mso-hide:all;">{_escape(preheader)}</div>'
        if preheader else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>Tapeline</title>
<style>
  /* Reset known-bad defaults across clients */
  body, table, td, p, a, h1, h2, h3, div {{ font-family: {FONT_SANS}; }}
  table {{ border-collapse: collapse !important; }}
  img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }}
  a {{ text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* Dark-mode overrides — class-keyed so each renderer's inline light-mode
     styles get superseded only where we tag a class. Apple Mail, Outlook
     iOS, Hey, and most webmail clients honour this; Gmail web/mobile will
     fall back to the inline light styles (and may auto-invert, which is
     fine because the meta color-scheme above signals support). */
  @media (prefers-color-scheme: dark) {{
    .tl-bg     {{ background: {DARK_BG} !important; }}
    .tl-panel  {{ background: {DARK_PANEL} !important; border-color: {DARK_BORDER} !important; }}
    .tl-card   {{ background: {DARK_BG} !important; border-color: {DARK_BORDER} !important; }}
    .tl-fg     {{ color: {DARK_FG} !important; }}
    .tl-muted  {{ color: {DARK_MUTED} !important; }}
    .tl-subtle {{ color: {DARK_SUBTLE} !important; }}
    .tl-border-top {{ border-top-color: {DARK_BORDER} !important; }}
    .tl-divider {{ background: {DARK_BORDER} !important; }}
    .tl-link-muted {{ color: {DARK_MUTED} !important; }}
    .tl-link-subtle {{ color: {DARK_SUBTLE} !important; }}
  }}

  /* Mobile padding tighten-up */
  @media only screen and (max-width: 600px) {{
    .tl-container {{ padding: 24px 16px !important; }}
    .tl-panel-inner {{ padding: 24px !important; }}
    .tl-h1 {{ font-size: 22px !important; }}
  }}
</style>
</head>
<body class="tl-bg" style="margin:0;padding:0;background:{LIGHT_BG};color:{LIGHT_FG};font-family:{FONT_SANS};-webkit-font-smoothing:antialiased;">
{preheader_html}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" class="tl-bg" style="background:{LIGHT_BG};">
  <tr>
    <td align="center" class="tl-container" style="padding:40px 16px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560" class="tl-panel" style="width:100%;max-width:560px;background:{LIGHT_PANEL};border:1px solid {LIGHT_BORDER};border-radius:12px;">
        <tr>
          <td class="tl-panel-inner" style="padding:36px;">
            {_brand_header()}
            {body}
            {_footer()}
          </td>
        </tr>
      </table>
      <p class="tl-subtle" style="margin:18px 0 0;font-size:11px;line-height:1.5;color:{LIGHT_SUBTLE};text-align:center;font-family:{FONT_SANS};">
        Tapeline · Melbourne, Australia · <a href="https://tapeline.io" class="tl-link-subtle" style="color:{LIGHT_SUBTLE};text-decoration:underline;">tapeline.io</a>
      </p>
    </td>
  </tr>
</table>
</body>
</html>"""


def _brand_header() -> str:
    """The Tapeline stripe + wordmark at the top of every email."""
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 28px;">
      <tr>
        <td style="vertical-align:middle;padding-right:10px;">
          <div style="width:28px;height:6px;border-radius:999px;background:linear-gradient(90deg,#007AFF,#5856D6);"></div>
        </td>
        <td class="tl-fg" style="vertical-align:middle;font-size:16px;font-weight:600;letter-spacing:-0.01em;color:{LIGHT_FG};font-family:{FONT_SANS};">
          Tapeline
        </td>
      </tr>
    </table>
    """


def _footer() -> str:
    """Shared footer — manage links + the not-investment-advice disclaimer.

    Order matters: the disclaimer comes first (legal) and the management
    links second (utility). Mirrors Stripe / Mercury layout.
    """
    return f"""
    <div class="tl-divider" style="height:1px;background:{LIGHT_BORDER};margin:36px 0 20px;"></div>
    <p class="tl-subtle" style="margin:0 0 10px;font-size:11px;line-height:1.6;color:{LIGHT_SUBTLE};font-family:{FONT_SANS};">
      <strong>Not investment advice.</strong> Tapeline is informational software — every score, signal, and headline is a data point, not a recommendation. Trade your own thesis.
    </p>
    <p class="tl-subtle" style="margin:0;font-size:11px;line-height:1.6;color:{LIGHT_SUBTLE};font-family:{FONT_SANS};">
      <a href="https://tapeline.io/app/settings/email" class="tl-link-subtle" style="color:{LIGHT_SUBTLE};text-decoration:underline;">Email preferences</a>
      &nbsp;·&nbsp;
      <a href="https://tapeline.io/app/account" class="tl-link-subtle" style="color:{LIGHT_SUBTLE};text-decoration:underline;">Account</a>
      &nbsp;·&nbsp;
      <a href="https://tapeline.io/app/billing" class="tl-link-subtle" style="color:{LIGHT_SUBTLE};text-decoration:underline;">Billing</a>
    </p>
    """


# ── Typography ───────────────────────────────────────────────────────────────

def h1(text: str) -> str:
    """The single page-heading at the top of the body. One per email."""
    return (
        f'<h1 class="tl-fg tl-h1" style="margin:0 0 12px;font-size:26px;line-height:1.25;'
        f'letter-spacing:-0.02em;font-weight:700;color:{LIGHT_FG};'
        f'font-family:{FONT_SANS};">{text}</h1>'
    )


def h2(text: str) -> str:
    """Subsection heading inside a body — e.g. "What's in your trial". Use sparingly."""
    return (
        f'<h2 class="tl-fg" style="margin:28px 0 10px;font-size:16px;line-height:1.4;'
        f'font-weight:600;color:{LIGHT_FG};font-family:{FONT_SANS};">{text}</h2>'
    )


def lead(text: str) -> str:
    """First paragraph after the h1 — the one-sentence framing of the email."""
    return (
        f'<p class="tl-muted" style="margin:0 0 24px;font-size:15px;line-height:1.55;'
        f'color:{LIGHT_MUTED};font-family:{FONT_SANS};">{text}</p>'
    )


def paragraph(text: str) -> str:
    """Standard body paragraph."""
    return (
        f'<p class="tl-fg" style="margin:0 0 16px;font-size:15px;line-height:1.6;'
        f'color:{LIGHT_FG};font-family:{FONT_SANS};">{text}</p>'
    )


def muted_paragraph(text: str) -> str:
    """De-emphasised paragraph for context, caveats, or footnotes."""
    return (
        f'<p class="tl-muted" style="margin:0 0 16px;font-size:14px;line-height:1.6;'
        f'color:{LIGHT_MUTED};font-family:{FONT_SANS};">{text}</p>'
    )


def footnote(text: str) -> str:
    """Smallest tier — beneath a CTA, e.g. "7-day money back, cancel anytime"."""
    return (
        f'<p class="tl-subtle" style="margin:16px 0 0;font-size:12px;line-height:1.5;'
        f'color:{LIGHT_SUBTLE};font-family:{FONT_SANS};">{text}</p>'
    )


# ── Buttons ─────────────────────────────────────────────────────────────────

def button(label: str, url: str, *, variant: str = "primary") -> str:
    """A bulletproof CTA button.

    `variant`:
      - "primary": filled accent (default)
      - "urgent":  filled amber (use sparingly — only for "trial ends tomorrow")

    Built with MSO conditionals so Outlook desktop renders a real button
    instead of a styled anchor. Everywhere else, the regular `<a>` paints.
    Email-on-acid pattern adapted to system fonts.
    """
    if variant == "urgent":
        bg, fg = "#f59e0b", "#0a0a0a"
    else:
        bg, fg = ACCENT, "#ffffff"

    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px;">
      <tr>
        <td align="left" bgcolor="{bg}" style="border-radius:8px;">
          <!--[if mso]>
          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
            href="{url}" style="height:42px;v-text-anchor:middle;width:220px;" arcsize="20%" stroke="f" fillcolor="{bg}">
            <w:anchorlock/>
            <center style="color:{fg};font-family:{FONT_SANS};font-size:14px;font-weight:600;">{label}</center>
          </v:roundrect>
          <![endif]-->
          <!--[if !mso]><!-- -->
          <a href="{url}" target="_blank"
             style="display:inline-block;padding:12px 22px;background:{bg};color:{fg};
                    font-family:{FONT_SANS};font-size:14px;font-weight:600;line-height:1;
                    border-radius:8px;text-decoration:none;">{label}</a>
          <!--<![endif]-->
        </td>
      </tr>
    </table>
    """


def secondary_link(label: str, url: str) -> str:
    """A muted text link used in place of a second button — keeps the CTA
    hierarchy clean (one primary, one secondary)."""
    return (
        f'<a href="{url}" class="tl-link-muted" style="color:{LIGHT_MUTED};text-decoration:underline;'
        f'font-family:{FONT_SANS};font-size:14px;">{label}</a>'
    )


# ── Layout primitives ───────────────────────────────────────────────────────

def divider() -> str:
    """Hairline horizontal divider — use to separate two sections of a body."""
    return f'<div class="tl-divider" style="height:1px;background:{LIGHT_BORDER};margin:24px 0;"></div>'


def card(content: str, *, accent: bool = False) -> str:
    """An inset block — subtle background, rounded, used for picks, stats,
    callouts. `accent=True` adds a left-side accent stripe."""
    border_left = f"border-left:3px solid {ACCENT};" if accent else ""
    return f"""
    <div class="tl-card" style="background:{LIGHT_BG};border:1px solid {LIGHT_BORDER};{border_left}border-radius:8px;padding:18px 20px;margin:0 0 16px;">
      {content}
    </div>
    """


def stat_row(label: str, value: str, *, value_color: str | None = None) -> str:
    """A key/value pair line — used inside cards for "Baseline: 65" etc."""
    vc = value_color or LIGHT_FG
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 6px;">
      <tr>
        <td class="tl-muted" style="font-size:13px;color:{LIGHT_MUTED};font-family:{FONT_SANS};">{label}</td>
        <td align="right" class="tl-fg" style="font-size:13px;font-weight:600;color:{vc};font-family:{FONT_MONO};">{value}</td>
      </tr>
    </table>
    """


# ── Domain primitives ────────────────────────────────────────────────────────

def score_color(score: float | None) -> str:
    """Map a 0-100 composite score onto a signal-tier colour. Matches the
    same tier breaks used on /how-it-works."""
    if score is None:
        return LIGHT_SUBTLE
    if score >= 70:
        return SIG_BULL
    if score >= 55:
        return SIG_CONSTRUCTIVE
    if score >= 40:
        return SIG_NEUTRAL
    if score >= 25:
        return SIG_CAUTION
    return SIG_BEAR


def ticker_card(
    symbol: str,
    score: float | None,
    signal: str | None,
    reason: str | None,
    *,
    url: str | None = None,
) -> str:
    """A single ticker block — symbol on the left, score+signal stacked on
    the right, optional reason below. Used in welcome email, watchlist
    alert, and the digest's hero ticker."""
    href = url or f"https://tapeline.io/t/{symbol}"
    score_str = f"{score:.0f}" if score is not None else "—"
    signal_str = signal or "—"
    col = score_color(score)
    why = _escape((reason or "").strip())[:160]
    why_block = (
        f'<div class="tl-muted" style="margin-top:8px;color:{LIGHT_MUTED};font-size:13px;line-height:1.5;font-family:{FONT_SANS};">{why}</div>'
        if why else ""
    )
    return f"""
    <a href="{href}" target="_blank" style="display:block;text-decoration:none;color:inherit;">
      <div class="tl-card" style="background:{LIGHT_BG};border:1px solid {LIGHT_BORDER};border-radius:8px;padding:16px 18px;margin:0 0 10px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td style="vertical-align:middle;">
              <div class="tl-fg" style="font-family:{FONT_MONO};font-size:18px;font-weight:700;color:{LIGHT_FG};">{symbol}</div>
            </td>
            <td align="right" style="vertical-align:middle;">
              <div style="font-family:{FONT_MONO};font-size:24px;font-weight:700;color:{col};line-height:1;">{score_str}</div>
              <div style="margin-top:4px;font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:{col};font-family:{FONT_SANS};">{signal_str}</div>
            </td>
          </tr>
        </table>
        {why_block}
      </div>
    </a>
    """


def watchlist_table(items: list[dict]) -> str:
    """Compact data table for the EOD digest — one row per watchlist item.

    Each item: {symbol, score, signal, change_pct_1d, score_delta?, reason?}.
    """
    if not items:
        return ""
    rows = []
    for it in items:
        sym = _escape(it.get("symbol", ""))
        score = it.get("score") or 0
        sig = it.get("signal") or "—"
        change = it.get("change_pct_1d") or 0
        delta = it.get("score_delta")
        col_sig = score_color(score)
        change_col = SIG_BULL if change > 0 else SIG_BEAR if change < 0 else LIGHT_MUTED
        change_str = f"{'+' if change >= 0 else ''}{change:.2f}%"
        delta_str = ""
        if delta is not None and abs(delta) >= 1:
            d_col = SIG_BULL if delta > 0 else SIG_BEAR
            d_sign = "+" if delta > 0 else ""
            delta_str = (
                f'<span style="color:{d_col};font-size:11px;margin-left:6px;font-family:{FONT_MONO};">'
                f'Δ {d_sign}{delta:.1f}</span>'
            )
        reason = _escape((it.get("reason") or "").strip())[:140]
        rows.append(f"""
        <tr>
          <td class="tl-border-top" style="padding:12px 6px;border-top:1px solid {LIGHT_BORDER};">
            <a href="https://tapeline.io/t/{sym}" class="tl-fg" style="color:{LIGHT_FG};text-decoration:none;font-family:{FONT_MONO};font-weight:600;font-size:14px;">{sym}</a>
          </td>
          <td align="right" class="tl-border-top tl-fg" style="padding:12px 6px;border-top:1px solid {LIGHT_BORDER};font-family:{FONT_MONO};font-weight:600;font-size:14px;color:{LIGHT_FG};">{score:.1f}{delta_str}</td>
          <td class="tl-border-top" style="padding:12px 6px;border-top:1px solid {LIGHT_BORDER};font-size:11px;font-weight:500;color:{col_sig};font-family:{FONT_SANS};letter-spacing:0.05em;">{sig}</td>
          <td align="right" class="tl-border-top" style="padding:12px 6px;border-top:1px solid {LIGHT_BORDER};font-family:{FONT_MONO};font-size:13px;font-weight:500;color:{change_col};">{change_str}</td>
        </tr>
        """)
        if reason:
            rows.append(f"""
        <tr>
          <td colspan="4" class="tl-muted" style="padding:0 6px 10px;color:{LIGHT_MUTED};font-size:12px;line-height:1.5;font-style:italic;font-family:{FONT_SANS};">{reason}</td>
        </tr>""")
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" class="tl-card" style="width:100%;background:{LIGHT_BG};border:1px solid {LIGHT_BORDER};border-radius:8px;margin:0 0 16px;">
      <thead>
        <tr>
          <th align="left" class="tl-muted" style="padding:10px 6px;font-size:10px;text-transform:uppercase;color:{LIGHT_MUTED};letter-spacing:0.08em;font-weight:600;font-family:{FONT_SANS};">Ticker</th>
          <th align="right" class="tl-muted" style="padding:10px 6px;font-size:10px;text-transform:uppercase;color:{LIGHT_MUTED};letter-spacing:0.08em;font-weight:600;font-family:{FONT_SANS};">Score</th>
          <th align="left" class="tl-muted" style="padding:10px 6px;font-size:10px;text-transform:uppercase;color:{LIGHT_MUTED};letter-spacing:0.08em;font-weight:600;font-family:{FONT_SANS};">Signal</th>
          <th align="right" class="tl-muted" style="padding:10px 6px;font-size:10px;text-transform:uppercase;color:{LIGHT_MUTED};letter-spacing:0.08em;font-weight:600;font-family:{FONT_SANS};">1D</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


# ── Utility ──────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Minimal HTML escaping — values come from our own DB/API, but
    user-controlled fields (name, reason text, watchlist note) flow
    through these renderers, so escape defensively."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
