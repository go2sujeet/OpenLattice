# Feature Loop

Run this loop verbatim for any task of the form "add X", "build X",
"implement X", or "support X". Do not freelance the order — each step
feeds the next.

## Steps

1. **Spec** — Invoke `to-prd`. Capture the one-paragraph intent, the
   acceptance criteria, and the out-of-scope list. Park the PRD in
   `.agents/plans/<task>-prd.md`.

2. **Plan** — Invoke `writing-plans`. Break the PRD into ordered phases,
   each ending green (tests + gate). Reject plans that have a phase which
   cannot end green on its own.

3. **Codebase map** — Invoke `codebase-design` (or `domain-modeling`
   for schema-touching work). Identify the exact files the change
   touches, the abstractions to reuse, and the ones to avoid. Record
   `file:line` references in the plan.

4. **Test first** — Invoke `tdd` (or `test-driven-development`). Write a
   failing test that encodes the acceptance criteria. For generator
   changes, write the new `tests/golden/<name>.py` expectation first;
   the test must fail before any generator code is touched.

5. **Implement** — Invoke `implement`. Make the failing test pass. Do
   not add scope the PRD did not ask for; spawn a follow-up todo
   instead.

6. **Verify** — Run the full Done Gate (`.agents/gates.md`). All items
   must be green. If any red, return to step 5.

7. **Review** — Invoke `code-review` on the diff. High-confidence
   findings are fixed immediately; low-confidence ones are noted as
   follow-ups.

8. **Merge** — Invoke `finishing-a-development-branch`. Squash-merge
   only if the plan was single-phase; otherwise preserve the phase
   commits. Delete the feature branch on merge.

## Time budget

A feature that takes more than 4 loop iterations of step 5-7 is too
big. Split it. The harness is designed for small, independently green
changes — that is what makes it fast.