# Dispatch Map

This file is the trigger map for the 107 installed skills. **Only the
skill listed for an intent fires automatically.** All other skills are
dormant unless invoked by explicit name.

This is the single source of truth that tames skill bloat. Without it,
the 107-skill catalog would cause trigger conflicts and prompt-budget
burn on every turn.

## Intent → Skill routing

| Intent signal                                | Primary                         | Support                                 |
|----------------------------------------------|---------------------------------|-----------------------------------------|
| "add X" / "build X" / "implement X"          | `writing-plans`                 | `codebase-design`, `tdd`                |
| "refactor" / "clean up" / "simplify"          | `request-refactor-plan`         | `improve-codebase-architecture`         |
| "it's broken" / "why does X fail" / "fix X"  | `systematic-debugging`          | `diagnosing-bugs`, `triage`             |
| "review this PR" / "audit diff"              | `code-review`                   | `requesting-code-review`               |
| "design the UI" / "make it look good"        | `frontend-design`               | `design-taste-frontend`, `shadcn`      |
| "deploy" / "ship to prod"                    | `deploy-to-vercel`              | —                                       |
| "write docs" / "document X"                  | `doc-coauthoring`               | `writing-guidelines`                    |
| "database" / "sql" / "schema"                | `supabase-postgres-best-practices` | `supabase`                           |
| "handoff" / "context for next session"       | `handoff`                       | `claude-handoff`                        |
| "is it done?" / "ready to merge?"            | `verification-before-completion` | `code-review`                          |
| "modify a generator"                         | (see `.agents/loops/codegen.md`) | `tdd`, `code-review`                   |
| "create a new skill"                         | `skill-creator`                 | `writing-great-skills`                  |
| "build an MCP server"                        | `mcp-builder`                   | `mcp-integration`                       |
| "spawn parallel agents"                      | `dispatching-parallel-agents`   | `subagent-driven-development`           |
| "idea → spec" / "brainstorm X"               | `brainstorming`                 | `to-prd`                                |

## Dormant list (invoke by name only)

The following skills do NOT auto-fire. Call them explicitly when
needed; otherwise they stay silent to save context budget:

- `algorithmic-art`, `slack-gif-creator`, `obsidian-vault`
- `scaffold-exercises`, `setup-matt-pocock-skills`, `edit-article`
- `teach`, `loop-me`, `grill-me`, `grill-with-docs`, `grilling`
- `claude-opus-4-5-migration`, `migrate-to-shoehorn`
- All `*-taste-*` design skills (use only when explicitly designing UI)
- `vercel-react-native-skills`, `vercel-react-view-transitions`
- `prototype`, `wizard`, `wayfinder`
- `internal-comms`, `research`, `research` (use only on demand)
- Document-format skills (`docx`, `pdf`, `xlsx`, `pptx`) — invoke when
  the user asks for a real file in that format; never auto-load.

## Conflict resolution

If two intents match (e.g. "fix the broken UI" matches both bugfix and
design rows), prefer the row matching the *verb* ("fix" → bugfix loop).
The bugfix loop itself can invoke `frontend-design` when it reaches the
implementation step.

## Update protocol

When new skills are installed via `npx skills add`, this file must be
updated in the same commit. A skill without a row here is dormant by
default.