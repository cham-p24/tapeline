"""One-off tightening pass on marketing-page section padding.

Drops py-16/py-14/py-12 by one Tailwind notch so the marketing surfaces
feel denser without losing readable breathing room. Skips the in-app
(/app/app/*) pages because those use a different layout density and
the founder's feedback was specifically about the marketing site.

Run from the worktree root:
    python scripts/tighten-spacing.py
"""
import re
import pathlib

SUBS = [
    # Combined Tailwind responsive padding — match before bare patterns.
    (r"py-16 sm:py-20", "py-10 sm:py-14"),
    (r"py-14 sm:py-20", "py-10 sm:py-14"),
    (r"py-14 sm:py-16", "py-10 sm:py-12"),
    (r"py-12 sm:py-20", "py-8 sm:py-12"),
    (r"py-12 sm:py-16", "py-8 sm:py-12"),
    (r"py-12 sm:py-14", "py-8 sm:py-10"),
    (r"py-10 sm:py-14", "py-8 sm:py-10"),
]

BARE = [
    # Bare py-16 / py-12 inside className attributes — touched only on
    # outer-wrapper elements so we don't accidentally compress button
    # padding or table cell heights.
    #
    # The negative-lookbehind `(?<!:)` is critical: it stops the bare
    # rule from eating the `sm:py-12` that the combined-padding pass
    # above just produced. Without it, "py-14 sm:py-16" -> "py-10
    # sm:py-12" -> (bare rule fires) -> "py-10 sm:py-8", which is
    # nonsense (mobile padding ends up larger than desktop).
    (
        re.compile(r'((?:className|class)="[^"]*?(?<![\w:]))\bpy-16\b'),
        lambda m: m.group(1) + "py-10",
    ),
    (
        re.compile(r'((?:className|class)="[^"]*?(?<![\w:]))\bpy-12\b'),
        lambda m: m.group(1) + "py-8",
    ),
]

ROOT = pathlib.Path("frontend")
SEP = "/"

changed = []
for path in ROOT.rglob("*.tsx"):
    posix = str(path).replace("\\", SEP)
    if "/app/app/" in posix:
        # In-app surfaces use their own density; the founder's feedback
        # was about marketing pages.
        continue
    if "/__tests__/" in posix:
        continue
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in SUBS:
        text = re.sub(old, new, text)
    for rx, fn in BARE:
        text = rx.sub(fn, text)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        changed.append(posix)

print(f"Files updated: {len(changed)}")
for p in changed:
    print(f"  {p}")
