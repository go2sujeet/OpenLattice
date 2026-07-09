# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-07-09

### Added
- IR relationship modeling: typed `WorkflowStep` (input/output/on_error), workflow `trigger`, queue `message_type`/`dlq`, api `publishes`/`crud_operation`, event `published_by`/`consumed_by` cross-references
- `lattice_event` codegen — Pydantic event models (`events.py`)
- `lattice_workflow` codegen — step stubs + async orchestrator (`workflows.py`)
- `lattice_queue` codegen — task handler stubs + registry (`queues.py`)
- `lattice_connector` resource — outbound HTTP integration calls, with generated `httpx`-based clients (`connectors.py`) wired into matching workflow steps
- `lattice_agent` resource — IR/parser foundation for generating Pydantic-AI agents (codegen is a follow-up)
- `openlattice apply`/`plan --output-dir`/`-o` and `--state-file` flags — regenerate multiple specs into isolated directories
- `examples/ipaas/` — webhook-in → transform → Slack-out integration pipeline example, exercising events/workflows/queues/connectors together
- `docs/registry.html` — searchable index of example pipelines, generated from `examples/*/*.lattice` via `scripts/build_registry.py`
- `terraform-provider-openlattice/` — v0 OpenTofu/Terraform provider (`openlattice_pipeline` resource) wrapping the CLI for provisioning-style workflows

### Changed
- Generator output split into one file per concern: `schemas.py`, `models.py`, `routes.py`, `app.py` replace the old combined `main.py` (plus the new `events.py`/`workflows.py`/`queues.py`/`connectors.py` when present)
- Playground (`docs/index.html`) synced to TF-style `resource "lattice_type" "label" { ... }` syntax; added iPaaS as a fourth preset

### Fixed
- `basedpyright` strict-mode debt resolved and gated in CI
- Release workflow no longer fails overall on unconfigured PyPI trusted publishing (GitHub release + downloadable artifacts still publish independently)

## [0.1.0] - 2026-06-23

### Added
- Terraform-style `.lattice` DSL — `resource "lattice_entity" "..."` block syntax
- Two-pass recursive descent parser with cross-resource reference resolution
- SHA-256 content-hashed state file (`.lattice-state.json`) for drift detection
- `openlattice plan` — colorized +/-/~ diff of desired vs current state
- `openlattice apply` — incremental convergence, no-op when nothing changed
- `openlattice show` — display current state
- FastAPI generator with `List[X]` response models for collection endpoints
- SQLAlchemy model generator
- E-commerce and blog example specs with pre-generated code
- GitHub Pages playground — live parser + generators in the browser, no install needed
- GitHub Codespaces devcontainer
