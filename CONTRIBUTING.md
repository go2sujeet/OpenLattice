# Contributing to OpenLattice

Thanks for your interest in contributing. This document covers how to get set up, add new generators, and submit changes.

---

## Dev environment setup

OpenLattice uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
git clone https://github.com/<your-fork>/OpenLattice.git
cd OpenLattice

uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

uv pip install -e .
```

Verify the install:

```bash
openlattice --help
```

---

## Running the CLI locally

The `openlattice` command is the main entry point.

```bash
# Preview what will be generated (dry run)
openlattice plan example.lattice

# Write generated files to ./generated/
openlattice apply example.lattice
```

Both commands read a `.lattice` spec file and operate on the parsed `LatticeSpec` IR (see `openlattice/ir.py`).

---

## Adding a new generator

Each generator is a Python module under `openlattice/generators/` that exposes a single function:

```python
def generate(spec: LatticeSpec) -> str:
    ...
```

It receives a fully-parsed `LatticeSpec` and returns the complete text of the file to write. That's the entire contract.

**Step-by-step:**

1. Create `openlattice/generators/my_target_gen.py`.

2. Import the IR types you need:

   ```python
   from openlattice.ir import LatticeSpec, EntityDef, ApiDef, FieldDef
   ```

3. Implement `generate(spec: LatticeSpec) -> str`. Walk `spec.entities`, `spec.apis`, `spec.events`, etc., and build up the output string however you like (f-strings, a list of lines joined at the end, a template engine — all fine).

4. Wire it up in `openlattice/cli.py`:

   ```python
   from openlattice.generators import my_target_gen

   # Inside the `apply` command, add an entry to the `files` list:
   (out_dir / "my_output.py", my_target_gen.generate(spec)),
   ```

5. Add a matching line to the `plan` command so users can see what will be generated.

See `openlattice/generators/fastapi_gen.py` and `sqlalchemy_gen.py` for complete, working examples.

---

## Submitting a pull request

1. Fork the repository on GitHub.
2. Create a feature branch off `main`:
   ```bash
   git checkout -b feat/my-generator
   ```
3. Make your changes. Keep commits focused and descriptive.
4. Push and open a PR against `main` on the upstream repo.
5. Fill in the PR description explaining what the change does and why.

There are no automated tests yet — manual verification with `openlattice plan` / `openlattice apply` on the provided `example.lattice` is the current baseline.

---

## Filing issues

Open an issue on GitHub for:

- Bug reports (include the `.lattice` file that triggers the problem and the full error output)
- Feature requests (describe the use case, not just the solution)
- Generator ideas or questions about the IR design

Please search existing issues before opening a new one.
