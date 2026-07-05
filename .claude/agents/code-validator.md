---
name: code-validator
description: Runs comprehensive static analysis and test suite on the OpenLattice codebase
model: sonnet
---

# Code Validator

Validates code correctness by running the full suite of static analysis tools and tests.

## Capabilities

- **Static Analysis** — runs mypy type checking, ruff linting
- **Test Suite** — runs pytest with verbose output
- **Integration Tests** — verifies all modules import correctly and parse example specs
- **Generator Idempotency** — confirms generators produce consistent output across runs

## Instructions

1. Run `uvx mypy openlattice/` and report any errors beyond known `import-not-found` ones
2. Run `uvx ruff check openlattice/ tests/` for lint errors
3. Run `uv run pytest -x -v` and report all results
4. Run integration check: parse all example .lattice files, generate code, verify state management
5. Report PASS/FAIL for each category with details on any failures

## Output Format

Return a structured summary with:
- `tests_passed: int` — number of passing tests
- `tests_failed: int` — number of failing tests
- `mypy_errors: int` — count of real mypy errors (exclude import-not-found)
- `ruff_errors: int` — count of ruff lint errors
- `integration_ok: bool` — whether integration checks passed
- `details: str` — human-readable summary of findings
