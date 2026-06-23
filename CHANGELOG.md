# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
