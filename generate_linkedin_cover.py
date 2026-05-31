"""LinkedIn company-page cover — 1128 × 191 px (LinkedIn's exact spec).

Matches the Tapeline brand: dark background, blue pill mark, Inter font,
"Read the tape." slogan (2026-05-14 brand decision; was "One transparent
score per US stock" — don't revert).
"""
import os

from PIL import Image, ImageDraw, ImageFont

# --- Tapeline brand palette ----------------------------------------------
BG_DARK = (10, 10, 10)
ACCENT = (59, 130, 246)            # #3B82F6 — Tapeline blue (NOT green)
FG = (244, 244, 245)               # #F4F4F5
MUTED = (156, 163, 175)            # #9CA3AF

# --- LinkedIn company-page cover dimensions ------------------------------
W, H = 1128, 191                   # LinkedIn's exact required size

im = Image.new("RGB", (W, H), BG_DARK)
d = ImageDraw.Draw(im)

# Font setup — Inter preferred, fallbacks for printers/systems without it
def find_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

FONT_TITLE = find_font([
    r"C:\Windows\Fonts\Inter-Bold.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
], 64)
FONT_TAGLINE = find_font([
    r"C:\Windows\Fonts\Inter-Regular.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
], 22)

# --- Layout --------------------------------------------------------------
# Wordmark left-aligned with comfortable margin; tagline directly below.
# Pill mark on the right balances visually.

# Wordmark
d.text((60, 50), "Tapeline", font=FONT_TITLE, fill=FG, anchor="lt")

# Tagline — the current Tapeline slogan
d.text((60, 130), "Read the tape.", font=FONT_TAGLINE, fill=MUTED, anchor="lt")

# Brand pill mark, right-aligned, vertically centred
pill_w, pill_h = 180, 40
pill_x = W - pill_w - 60
pill_y = (H - pill_h) // 2
d.rounded_rectangle(
    (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
    radius=pill_h // 2, fill=ACCENT,
)

im.save(r"C:\Project 1\tapeline-linkedin-cover.png", "PNG")
print(f"saved tapeline-linkedin-cover.png ({W}x{H}px, dark bg, blue pill, Read the tape.)")
