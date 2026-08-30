"""PowerShell scripts in this repo must be pure ASCII.

WHY THIS EXISTS
---------------
`scripts/meta-capi-golive.ps1` was written with typographic em-dashes in its
strings and box-drawing characters in its comment rules. It was never actually
run until 2026-08-30, and then it failed on the founder's machine with a cascade
of parse errors that looked nothing like an encoding problem:

    Unexpected token '}' in expression or statement.
    The ampersand (&) character is not allowed...
    The string is missing the terminator: ".
    Missing closing '}' in statement block or type definition.

The cause: the file has **no BOM**, and **Windows PowerShell 5.1 reads a BOM-less
file as ANSI**, not UTF-8. A UTF-8 em-dash (`E2 80 94`) decodes to `a~"` under
Windows-1252 — and that stray double-quote *terminates the string early*. Every
later error is fallout from that one mis-decoded character.

It is a nasty failure mode precisely because the file looks correct in every
editor, `git diff` shows nothing wrong, and the script parses fine under
PowerShell 7 (which assumes UTF-8). It only breaks in Windows PowerShell 5.1,
which is the shell the founder actually launches.

WHY ASCII RATHER THAN "ADD A BOM"
---------------------------------
A BOM would also fix it, but it is a property of the file that is invisible,
easy to strip (many tools rewrite files without it), and silently reintroduces
the bug when lost. ASCII-only is checkable, obvious in review, and correct under
every encoding and shell. The characters involved are decorative — em-dashes and
box-drawing rules in comments — so nothing of value is lost.

Restricting this to `.ps1` is deliberate: Python, TypeScript and Markdown in this
repo are read as UTF-8 by their own toolchains and use non-ASCII text
intentionally (the ad copy, the docs). PowerShell run by 5.1 is the one place the
encoding is genuinely ambiguous.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# `.claude/worktrees` holds throwaway per-agent checkouts of this same repo, so
# scanning it double-reports every file and fails on copies nobody edits.
_SKIP_DIRS = {"node_modules", ".venv", "worktrees", ".git"}


def _powershell_scripts() -> list[Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.ps1")
        if _SKIP_DIRS.isdisjoint(p.parts)
    )


def test_there_are_powershell_scripts_to_check() -> None:
    """Guard the guard: if the glob silently matches nothing, the rest passes vacuously."""
    assert _powershell_scripts(), "no .ps1 files found - the glob is wrong"


def test_powershell_scripts_contain_no_non_ascii() -> None:
    offenders: list[str] = []

    for script in _powershell_scripts():
        text = script.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            bad = {ch for ch in line if ord(ch) > 127}
            if bad:
                rel = script.relative_to(REPO_ROOT).as_posix()
                shown = " ".join(f"{ch!r}(U+{ord(ch):04X})" for ch in sorted(bad))
                offenders.append(f"{rel}:{lineno} contains {shown}")

    assert not offenders, (
        "PowerShell scripts must be pure ASCII - Windows PowerShell 5.1 reads a\n"
        "BOM-less file as ANSI, so a UTF-8 em-dash decodes to a stray quote that\n"
        "terminates the string and cascades into unrelated-looking parse errors.\n"
        "Use '-' for dashes and \"...\" for quotes.\n\n" + "\n".join(offenders)
    )
