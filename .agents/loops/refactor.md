# Refactor Loop

Run this loop for "clean up X", "refactor Y", "simplify Z", or any
change that preserves behavior while restructuring code. The
non-negotiable rule: behavior is unchanged if and only if the golden
snapshots and the test suite both stay green without modifications.

## Steps

1. **Plan** — Invoke `request-refactor-plan`. Identify the smell, the
   target shape, and the blast radius. Explicitly list which goldens
   must NOT change and which tests must stay green.

2. **Architecture** — Invoke `improve-codebase-architecture` and
   `requesting-code-review` on the plan (not the code yet). Get the plan
   reviewed before writing code — refactors without review are the
   fastest way to introduce regression.

3. **Test baseline** — Run `uv run pytest -q` and capture the pass
   count. Run `UPDATE_GOLDEN=0 uv run pytest tests/test_codegen_golden.py`
   and confirm all goldens match. This is the pre-refactor baseline.

4. **Refactor** — Invoke `implement`. Make the structural change. Do
   not modify tests or goldens in this step. If you feel the need to
   modify a test, the refactor is changing behavior — return to step 1.

5. **Verify behavior preserved** — Run the full Done Gate
   (`.agents/gates.md`). Critical: the pass count from step 3 must be
   identical or higher, and goldens must match byte-for-byte (no
   `UPDATE_GOLDEN=1` here — goldens must NOT change during refactors).

6. **Review** — Invoke `receiving-code-review` on the diff. The
   reviewer confirms: same behavior, cleaner structure, no new public
   API surface.

7. **Merge** — Invoke `finishing-a-development-branch`. Preserve the
   refactor as a single commit with a "refactor(scope):" prefix so it
   is bisectable as a no-behavior-change commit.