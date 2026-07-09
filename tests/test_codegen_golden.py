"""Golden snapshot tests for the code generators.

Locks generator output byte-for-byte so any behavior change is an explicit,
reviewed diff rather than silent drift. Goldens live in tests/golden/ and are
committed to git.

To intentionally update goldens after a deliberate generator change, run:

    UPDATE_GOLDEN=1 uv run pytest tests/test_codegen_golden.py

Without that env var, the test FAILS on any mismatch, printing a unified diff.
This mirrors --update-snapshots flows in mature snapshot frameworks and ensures
generator changes are always reviewer-visible.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openlattice.generators.events_gen import generate as gen_events
from openlattice.generators.fastapi_gen import generate as gen_fastapi
from openlattice.generators.sqlalchemy_gen import generate as gen_sqlalchemy
from openlattice.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


def _snapshot(spec_file: Path, gen_fn, golden_file: Path) -> None:
    spec = parse_file(str(spec_file))
    actual = gen_fn(spec)
    golden_path = GOLDEN_DIR / golden_file
    golden_path.parent.mkdir(parents=True, exist_ok=True)

    if UPDATE:
        golden_path.write_text(actual)
        pytest.skip(f"golden updated: {golden_file}")

    if not golden_path.exists():
        pytest.fail(
            f"Golden {golden_file} missing. Run with UPDATE_GOLDEN=1 to seed it. "
            "Then commit the golden as the regression anchor."
        )

    expected = golden_path.read_text()
    assert actual == expected, (
        f"Generator output drifted from golden {golden_file}.\n\n"
        "If this change is intentional, update the golden:\n"
        f"    UPDATE_GOLDEN=1 uv run pytest {Path(__file__).name}\n"
        "Then review and commit the golden diff.\n\n"
        "Falling back to a textual diff for visibility:\n" + _diff(expected, actual)
    )


def _diff(expected: str, actual: str) -> str:
    import difflib

    return "\n".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="golden (expected)",
            tofile="generator (actual)",
            n=3,
        )
    )


def test_fastapi_golden_example() -> None:
    _snapshot(
        REPO_ROOT / "example.lattice",
        gen_fastapi,
        Path("example_main.py"),
    )


def test_sqlalchemy_golden_example() -> None:
    _snapshot(
        REPO_ROOT / "example.lattice",
        gen_sqlalchemy,
        Path("example_models.py"),
    )


def test_fastapi_golden_deterministic() -> None:
    """Generator must be pure: same spec in -> same bytes out, twice."""
    spec = parse_file(str(REPO_ROOT / "example.lattice"))
    first = gen_fastapi(spec)
    second = gen_fastapi(spec)
    assert first == second, "FastAPI generator is non-deterministic"


def test_sqlalchemy_golden_deterministic() -> None:
    """Generator must be pure: same spec in -> same bytes out, twice."""
    spec = parse_file(str(REPO_ROOT / "example.lattice"))
    first = gen_sqlalchemy(spec)
    second = gen_sqlalchemy(spec)
    assert first == second, "SQLAlchemy generator is non-deterministic"


def test_events_golden_ecommerce() -> None:
    _snapshot(
        REPO_ROOT / "examples" / "ecommerce" / "ecommerce.lattice",
        gen_events,
        Path("ecommerce_events.py"),
    )


def test_events_golden_deterministic() -> None:
    """Generator must be pure: same spec in -> same bytes out, twice."""
    spec = parse_file(str(REPO_ROOT / "examples" / "ecommerce" / "ecommerce.lattice"))
    first = gen_events(spec)
    second = gen_events(spec)
    assert first == second, "Events generator is non-deterministic"
