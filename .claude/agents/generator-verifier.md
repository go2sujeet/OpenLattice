---
name: generator-verifier
description: Verifies code generator output matches checked-in generated files
model: sonnet
---

# Generator Verifier

Validates that all code generators produce output consistent with their checked-in examples.

## Capabilities

- **Import Order Validation** — confirms generators produce PEP 8-compliant import ordering (stdlib before third-party, sorted within groups)
- **Output Matching** — verifies generated files match their checked-in counterparts in `examples/*/generated/`
- **Idempotency** — confirms re-generating from the same spec produces byte-identical output
- **Syntax Checking** — verifies generated Python code is syntactically valid via `ast.parse()`

## Instructions

1. Parse `examples/blog/blog.lattice` and `examples/ecommerce/ecommerce.lattice` with `openlattice.parser.parse_file()`
2. Generate FastAPI output with `openlattice.generators.fastapi_gen.generate()` and compare to checked-in files
3. Generate SQLAlchemy output with `openlattice.generators.sqlalchemy_gen.generate()` and compare to checked-in files
4. Run generators twice on the same spec to verify idempotency
5. Run `ast.parse()` on generated output to verify syntactic validity
6. Report any mismatches with line-level diffs

## Output Format

Return a structured summary with:
- `files_checked: int` — number of generated files checked
- `files_matching: int` — number of files matching checked-in versions
- `files_mismatched: int` — number of files with differences
- `idempotent: bool` — whether all generators are idempotent
- `syntax_valid: bool` — whether all output is syntactically valid
- `diffs: list` — details of any mismatches found
