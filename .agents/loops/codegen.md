# Codegen Change Loop

Run this loop for any change to `openlattice/generators/fastapi_gen.py`
or `openlattice/generators/sqlalchemy_gen.py`. Code generators are the
most regression-prone code in this repo because output is large, text-
based, and easy to silently alter. This loop is the strictest of the
four.

## Steps

1. **Intend** — Write the expected new output as a new
   `tests/golden/<name>.py` file OR a planned modification to an existing
   golden. This is the contract: the generator will produce exactly this.

2. **Plan** — Invoke `writing-plans`. Identify the exact generator
   function(s) to change, the IR shapes they consume, and any new field
   types or DSL constructs involved.

3. **Test first** — Add a test in `tests/test_codegen_golden.py` that
   compares generator output against the new/updated golden. It must
   RED before any generator code is touched. To seed the golden (this
   one time), run `UPDATE_GOLDEN=1 uv run pytest tests/test_codegen_golden.py`
   and commit the golden in the same change.

4. **Implement** — Invoke `implement`. Modify the generator. The
   golden test goes GREEN. Run it twice (the determinism guard catches
   dict-ordering bugs automatically; if it goes RED, you introduced
   non-determinism).

5. **Verify** — Run the full Done Gate (`.agents/gates.md`). All four
   golden tests (two snapshot + two determinism) must pass. No other
   tests may regress.

6. **Review** — Invoke `code-review` on: (a) the generator diff, and
   (b) the golden diff. Both are equally important — the reviewer asks
   "is the new output what users would expect to see in their generated
   codebase?" Bad formatting in emitted code is a bug.

7. **Merge** — Invoke `finishing-a-development-branch`. The generator
   change and the golden update are in the same commit; never split
   them. A codegen change without a golden update is a regression by
   definition.

## Common pitfall

Never use `UPDATE_GOLDEN=1` to "fix" a failing codegen test in step 4
or later. That flag is only to seed the golden in step 3. After step 3,
the golden is locked; if the generator output drifts, the generator is
wrong, not the golden.