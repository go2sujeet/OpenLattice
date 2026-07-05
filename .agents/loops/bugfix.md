# Bugfix Loop

Run this loop for any task of the form "X is broken", "why does Y fail",
"fix Z", or a failing test/CI signal. The non-negotiable rule: the bug
is not "fixed" until a regression test reproduces it and then passes.

## Steps

1. **Triage** — Invoke `triage`. Capture: exact repro steps, expected
   vs. actual output, environment (Python/OS/uv version), and the first
   failing commit if discoverable. Park in `.agents/plans/<task>-triage.md`.

2. **Root cause** — Invoke `systematic-debugging` then `diagnosing-bugs`.
   Formulate the most specific hypothesis that explains the symptom. Do
   not patch symptoms; find the cause. Bisect if needed
   (`git bisect start`).

3. **Reproduce in a test** — Write a new test in `tests/` that fails
   with the current code and would pass after the fix. For generator
   bugs, add a `tests/golden/<bug-name>.py` case. The test must RED
   before the fix is written. If you cannot write a reproducing test,
   you do not understand the bug — go back to step 2.

4. **Fix** — Invoke `implement`. Make the reproducing test pass. Touch
   as few files as possible; the smaller the diff, the safer the fix.

5. **Verify** — Run the full Done Gate (`.agents/gates.md`). The new
   regression test must stay green. No other test may regress.

6. **Review** — Invoke `code-review` on the diff. Bug fixes are higher
   risk than features because they imply the existing tests missed the
   bug; the reviewer should ask "why didn't existing tests catch this?"
   and add a guard if the answer is "lack of coverage".

7. **Merge** — Invoke `finishing-a-development-branch`. The regression
   test and fix are in the same commit; never split them.