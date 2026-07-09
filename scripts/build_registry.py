#!/usr/bin/env python3
"""Build docs/registry.json from the .lattice specs under examples/*.

Scans examples/*/*.lattice (top-level spec files only — files under
examples/*/generated/ are code-generator output, not specs, and are
skipped), parses each with the real openlattice parser, and emits a
sorted JSON manifest describing each example's resource counts.

Usage:
    uv run python scripts/build_registry.py

Exits non-zero if any .lattice file fails to parse (after printing a
warning to stderr and skipping it), so CI can catch a broken example
without blocking the registry build for the others.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openlattice.parser import ParseError, parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
OUTPUT_PATH = REPO_ROOT / "docs" / "registry.json"

# Resource-type counts, in the order they should appear in "resource_types".
_RESOURCE_ATTRS = (
    ("entities", "entities"),
    ("apis", "apis"),
    ("events", "events"),
    ("workflows", "workflows"),
    ("queues", "queues"),
    ("connectors", "connectors"),
    ("agents", "agents"),
)


def _leading_comment_description(spec_path: Path, name: str) -> str:
    """Return the first `#`-comment line at the top of the file as a
    description, or a generic fallback if there isn't one."""
    with open(spec_path) as f:
        first_line = f.readline().strip()
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip()
    return f"{name} example"


def build_manifest_entry(spec_path: Path) -> dict[str, object]:
    name = spec_path.parent.name
    spec = parse_file(str(spec_path))

    counts = {label: len(getattr(spec, attr)) for attr, label in _RESOURCE_ATTRS}
    resource_types = [label for _, label in _RESOURCE_ATTRS if counts[label] > 0]

    return {
        "name": name,
        "spec_file": str(spec_path.relative_to(REPO_ROOT)),
        "counts": counts,
        "resource_types": resource_types,
        "description": _leading_comment_description(spec_path, name),
    }


def main() -> int:
    spec_paths = sorted(EXAMPLES_DIR.glob("*/*.lattice"))

    entries: list[dict[str, object]] = []
    had_error = False

    for spec_path in spec_paths:
        try:
            entries.append(build_manifest_entry(spec_path))
        except (ParseError, OSError) as exc:
            had_error = True
            print(f"warning: skipping {spec_path}: {exc}", file=sys.stderr)

    entries.sort(key=lambda entry: entry["name"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(entries)} example(s) to {OUTPUT_PATH.relative_to(REPO_ROOT)}")

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
