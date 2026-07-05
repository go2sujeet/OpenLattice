from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from openlattice.generators.fastapi_gen import generate as gen_fastapi
from openlattice.generators.sqlalchemy_gen import generate as gen_sqlalchemy
from openlattice.ir import LatticeSpec
from openlattice.parser import ParseError, parse_file
from openlattice.state import (
    DiffResult,
    ResourceState,
    StateFile,
    build_new_state,
    diff_spec_against_state,
    load_state,
    save_state,
    spec_resources,
)

console = Console()
STATE_FILE = ".lattice-state.json"


def _render_plan(diff: DiffResult, spec: LatticeSpec, state: StateFile) -> Text:
    t = Text()
    current: dict[tuple[str, str], ResourceState] = {(r.type, r.label): r for r in state.resources}
    all_res: dict[tuple[str, str], dict[str, Any]] = {
        (rt, lb): attrs for rt, lb, attrs in spec_resources(spec)
    }

    for (rt, lb), attrs in all_res.items():
        ref = f"{rt}.{lb}"
        if ref in diff.to_add:
            t.append(f'\n  + resource "{rt}" "{lb}"', style="green")
            t.append("  # will be created\n", style="dim")
            for k, v in attrs.items():
                if isinstance(v, dict):
                    v_dict = cast(dict[str, str], v)
                    fields_str = ", ".join(f"{fk}: {fv}" for fk, fv in v_dict.items())
                    t.append(f"      {k} = {{{fields_str}}}\n", style="green")
                elif isinstance(v, list):
                    t.append(f"      {k} = {v}\n", style="green")
                else:
                    t.append(f'      {k} = "{v}"\n', style="green")
        elif ref in diff.to_change:
            old = current[(rt, lb)].attributes
            t.append(f'\n  ~ resource "{rt}" "{lb}"', style="yellow")
            t.append("  # will be updated\n", style="dim")
            for k in set(list(old.keys()) + list(attrs.keys())):
                oval = old.get(k)
                nval = attrs.get(k)
                if oval != nval:
                    t.append(f"    ~ {k} = ", style="yellow")
                    t.append(f"{oval!r}", style="red")
                    t.append(" → ", style="dim")
                    t.append(f"{nval!r}\n", style="green")

    for ref in diff.to_destroy:
        rt, lb = ref.split(".", 1)
        t.append(f'\n  - resource "{rt}" "{lb}"', style="red")
        t.append("  # will be destroyed\n", style="dim")

    nadd = len(diff.to_add)
    nchange = len(diff.to_change)
    ndestroy = len(diff.to_destroy)
    t.append(f"\nPlan: {nadd} to add, {nchange} to change, {ndestroy} to destroy.\n", style="bold")

    if nadd + nchange + ndestroy == 0:
        t.append("\nNo changes. Infrastructure is up-to-date.\n", style="bold green")

    return t


@click.group()
def cli():
    """OpenLattice — declarative application specification compiler."""
    pass


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def plan(spec_file: str):
    """Show execution plan: what will be added, changed, or destroyed."""
    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise SystemExit(1)

    state = load_state(STATE_FILE)
    diff = diff_spec_against_state(spec, state)

    content = Text()
    content.append(f"Spec: {spec_file}\n\n", style="dim")
    content.append(_render_plan(diff, spec, state))
    content.append("\n  Will generate:\n", style="dim")
    content.append("    → generated/main.py        FastAPI app + routes\n", style="cyan")
    content.append("    → generated/models.py      SQLAlchemy models\n", style="cyan")
    if diff.to_add or diff.to_change or diff.to_destroy:
        content.append(
            f"\n  Run `openlattice apply {spec_file}` to perform these actions.", style="dim"
        )

    console.print(Panel(content, title="OpenLattice Plan", border_style="blue"))


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def apply(spec_file: str):
    """Apply spec: generate files and update state."""
    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise SystemExit(1)

    state = load_state(STATE_FILE)
    diff = diff_spec_against_state(spec, state)

    if not (diff.to_add or diff.to_change or diff.to_destroy):
        console.print("[green]No changes.[/green] State is up-to-date.")
        return

    console.print(f"Applying OpenLattice spec: [bold]{spec_file}[/bold]\n")

    out_dir = Path("generated")
    out_dir.mkdir(exist_ok=True)

    files = {
        out_dir / "main.py": gen_fastapi(spec),
        out_dir / "models.py": gen_sqlalchemy(spec),
    }
    for path, content in files.items():
        path.write_text(content)
        console.print(f"  [green]✓[/green] {path}")

    new_state = build_new_state(spec, state)
    save_state(new_state, STATE_FILE)
    console.print(
        f"\nDone. [bold]{len(files)}[/bold] files written. State updated (serial={new_state.serial})."
    )


@cli.command()
def show():
    """Show current state."""
    state = load_state(STATE_FILE)
    if not state.resources:
        console.print("No state found. Run [bold]openlattice apply[/bold] first.")
        return
    console.print(f"[bold]State[/bold] (serial={state.serial}, lineage={state.lineage[:8]}…)\n")
    for r in state.resources:
        console.print(f"  [cyan]{r.type}.{r.label}[/cyan]  hash={r.spec_hash[:18]}…")
