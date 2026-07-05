# Done Gate

A task is **not done** until every item below is green. No exceptions, no
"will fix later". If any item fails, the task stays `in_progress` and the
agent continues working.

This file is read by the agent at the end of every task. Treat it as a
hard contract, not a guideline.

## Mandatory checks (in order)

1. **Tests** — `uv run pytest -q` exits 0. Skipped tests require an
   inline reason (`pytest.skip("reason")`). New tests landed with the
   change, not in a follow-up.

2. **Lint** — `uv run ruff check` exits 0. The baseline (34 errors) was
   captured at harness install on commit `28cfa1c`; cleanup may reduce
   the count but never increase it. New code that adds lint errors is a
   regression.

3. **Format** — `uv run ruff format --check` exits 0. Run
   `uv run ruff format` to fix.

4. **Type check** — `uv run basedpyright` exits 0 OR the error count is
   ≤ baseline (40 errors / 285 warnings). Any new strict-mode error in
   code touched by this task is a regression, even if the total stays
   under baseline.

5. **Plan smoke** — `uv run openlattice plan example.lattice` exits 0.
   Cheap end-to-end check that the parser + state machine still work.

6. **Apply smoke** — `uv run openlattice apply example.lattice` either
   reports "No changes" (state matches spec) or regenerates output that
   matches `tests/golden/`. If goldens changed, the diff is reviewed and
   committed in the same change.

7. **Code review** — `code-review` skill (or `code-reviewer` for a local
   diff) has been run on the change. High-confidence findings are either
   fixed or explicitly accepted with a one-line reason in the commit
   body.

8. **Verification** — `verification-before-completion` skill has been
   invoked. The agent has re-read the diff and confirmed it does what
   the task asked for, nothing more, nothing less.

## Failure protocol

- Any check red → mark task `in_progress` (do not mark `completed`).
- Fix the failure, re-run the gate from the top.
- If a check is genuinely unfixable in this task (e.g. requires a
  cross-team API change), surface it as a follow-up todo in the task and
  get explicit user approval to ship without that gate item. Record the
  exception in the commit body with the word `EXCEPTION:`.

## Golden snapshot policy

Goldens in `tests/golden/` lock current generator output. To update them
intentionally:

```
UPDATE_GOLDEN=1 uv run pytest tests/test_codegen_golden.py
```

Then review the golden diff in `git diff tests/golden/` and commit it in
the same change as the generator modification. Never commit a generator
change without a golden update (or an explicit deletion) in the same
commit.