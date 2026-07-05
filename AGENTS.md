# Project Rules

## Tooling

- Install skills/agents/plugins via the Claude Code ecosystem (opencode supports it natively).
  Use `npx skills add <owner/repo@skill> -y` (project-level). Global `-g` is unsupported for most packs.
  Output goes to `.agents/skills/` and symlinks to Claude Code automatically.
- Trigger skills from opencode by invoking the Skill tool with the skill name.

## Skills Installed

Installed via `npx skills add` into `.agents/skills/`:

- anthropics/skills, anthropics/claude-code
- vercel-labs/agent-skills, vercel-labs/agent-browser
- mattpocock/skills, obra/superpowers
- supabase/agent-skills, shadcn/ui
- leonxlnx/taste-skill, pbakaus/impeccable