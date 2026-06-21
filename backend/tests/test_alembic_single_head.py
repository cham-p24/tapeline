"""Guard against a forked Alembic migration graph (more than one head).

When two parallel PRs each add a migration whose ``down_revision`` points at
the same parent, the revision graph forks into TWO heads. ``alembic upgrade
head`` then refuses to run ("Multiple head revisions are present...") and the
backend deploy fails. This has broken the deploy several times — each fix being
a manual merge migration after the fact.

This test catches the fork at PR time: CI goes red on the PR that introduces
the second head, before it can reach a deploy. It reads the migration scripts
straight off disk via Alembic's ``ScriptDirectory`` — no database connection,
no app import, no ``env.py`` execution — so it's fast and dependency-light
(Alembic is already a dependency).

If this test fails, run ``alembic merge heads`` (or merge the two specific
heads it lists) to collapse the graph back to a single head, then commit the
generated merge migration.
"""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

# tests/ lives directly under backend/, so the repo's backend root and the
# alembic config sit one level up from this file. Resolving relative to
# __file__ makes the test independent of pytest's working directory — CI runs
# ``pytest -x`` from backend/, but local runs may invoke it from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"
_VERSIONS_DIR = _BACKEND_DIR / "alembic" / "versions"


def _script_directory() -> ScriptDirectory:
    """Build a ScriptDirectory from the on-disk config, cwd-independent.

    ``alembic.ini`` declares ``script_location = alembic`` (a *relative* path).
    Alembic resolves a relative ``script_location`` against the current working
    directory, not against the ini file — so if pytest runs from anywhere other
    than backend/, ScriptDirectory would look in the wrong place. We override
    the option with the absolute ``backend/alembic`` path to remove that
    ambiguity entirely.
    """
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_config_and_versions_exist() -> None:
    """Sanity check: the paths we resolved actually point at the migrations.

    Guards against a silent pass if the layout moves — a ScriptDirectory over
    an empty/missing folder reports zero heads, which would otherwise let the
    single-head assertion slip through unnoticed.
    """
    assert _ALEMBIC_INI.is_file(), f"alembic.ini not found at {_ALEMBIC_INI}"
    assert _VERSIONS_DIR.is_dir(), f"versions dir not found at {_VERSIONS_DIR}"
    assert any(_VERSIONS_DIR.glob("*.py")), "no migration scripts found"


def test_single_alembic_head() -> None:
    """The migration graph must have exactly one head.

    More than one head means two migrations forked off a shared parent and were
    never merged; ``alembic upgrade head`` will abort and the deploy breaks. Fix
    by running ``alembic merge heads`` and committing the merge migration.
    """
    heads = _script_directory().get_heads()
    assert len(heads) == 1, (
        f"Expected exactly 1 Alembic head, found {len(heads)}: {sorted(heads)}. "
        "Two migrations forked off the same parent without being merged. Run "
        "`alembic merge heads` (from backend/) and commit the resulting merge "
        "migration to collapse the graph back to a single head."
    )
