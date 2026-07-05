export const meta = {
  name: 'full-validation',
  description: 'Comprehensive validation: static analysis, generator check, state test, edge cases, HTML report',
  phases: [
    { title: 'Analyze', detail: 'Run static analysis tools' },
    { title: 'Verify Generators', detail: 'Check generator output matches' },
    { title: 'Verify State', detail: 'Test state management correctness' },
    { title: 'Review & Report', detail: 'Code review and HTML report' },
  ],
}

phase('Analyze')

const codeResults = await agent(
  `Validate the OpenLattice codebase by running:
  1. uvx mypy openlattice/ --config-file pyproject.toml
  2. uvx ruff check openlattice/ tests/
  3. uv run pytest -x -v
  4. uv run python -c "from openlattice.parser import parse_file; from openlattice.generators.fastapi_gen import generate; from openlattice.generators.sqlalchemy_gen import generate as gen_sqla"

  Report ALL results including counts.`,
  { label: 'static-analysis', phase: 'Analyze' }
)

phase('Verify Generators')

const genResults = await agent(
  `Verify the OpenLattice code generators produce correct output:
  1. Parse examples/blog/blog.lattice and examples/ecommerce/ecommerce.lattice
  2. Generate FastAPI and SQLAlchemy output for each
  3. Compare generated output against checked-in files in examples/*/generated/
  4. Verify generators are idempotent (same spec -> identical output on re-run)
  5. Use ast.parse() to verify generated code is syntactically valid
  6. Import the generated modules to check they load correctly

  Use uv run python -c "..." for each step. Report exact PASS/FAIL per check.`,
  { label: 'generator-verify', phase: 'Verify Generators' }
)

phase('Verify State')

const stateResults = await agent(
  `Verify OpenLattice state management correctness:
  1. Test compute_spec_hash determinism (same input -> same output)
  2. Test diff_spec_against_state: empty state -> all to_add
  3. Test diff: unchanged resources not in diff
  4. Test diff: changed resources in to_change
  5. Test diff: removed resources in to_destroy
  6. Test save/load round-trip via tmp file
  7. Test build_new_state: serial increments, lineage preserved
  8. Test full cycle: parse spec -> diff -> build -> save -> load -> re-diff (should be empty)

  Import existing tests from tests/test_state.py and augment with edge cases.
  Use uv run python -c "..." for each test. Report PASS/FAIL per check.`,
  { label: 'state-verify', phase: 'Verify State' }
)

phase('Review & Report')

const reviewResults = await agent(
  `Review the working tree diff (git diff HEAD) for OpenLattice for:
  1. Semantic bugs hidden in reformatting
  2. Type errors that tests might miss
  3. Import path correctness (especially LSP pygls changes)
  4. Any behavioral differences between old and new code

  Read the actual diff and analyze each changed file.
  Report any confirmed (CONFIRMED) or plausible (PLAUSIBLE) findings.`,
  { label: 'final-review', phase: 'Review & Report' }
)

return {
  static_analysis: codeResults,
  generators: genResults,
  state_management: stateResults,
  final_review: reviewResults,
  status: 'complete',
  timestamp: new Date().toISOString(),
}
