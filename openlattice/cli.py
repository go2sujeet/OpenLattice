import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from openlattice.parser import parse_file, ParseError
from openlattice.generators import fastapi_gen, sqlalchemy_gen

console = Console()


@click.group()
def cli():
    """OpenLattice — declarative application specification compiler."""
    pass


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def plan(spec_file: str):
    """Show what will be generated from SPEC_FILE."""
    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        sys.exit(1)

    body = Text()

    body.append("  Resources:\n")
    for entity in spec.entities:
        count = len(entity.fields)
        body.append(f"    + Entity:   {entity.name:<20} ({count} field{'s' if count != 1 else ''})\n", style="green")
    for api in spec.apis:
        body.append(f"    + API:      {api.name:<20} {api.method:<6} {api.path}\n", style="green")
    for event in spec.events:
        body.append(f"    + Event:    {event.name}\n", style="green")
    for workflow in spec.workflows:
        count = len(workflow.steps)
        body.append(f"    + Workflow: {workflow.name:<20} ({count} step{'s' if count != 1 else ''})\n", style="green")
    for queue in spec.queues:
        body.append(f"    + Queue:    {queue.name:<20} retries={queue.retries}\n", style="green")

    body.append("\n  Will generate:\n")
    body.append("    → generated/main.py        FastAPI app + routes\n", style="cyan")
    body.append("    → generated/models.py      SQLAlchemy models\n", style="cyan")

    body.append("\n  Run `openlattice apply <file>` to materialize.")

    console.print(Panel(body, title="OpenLattice Plan", expand=False))


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def apply(spec_file: str):
    """Generate application artifacts from SPEC_FILE."""
    spec_path = Path(spec_file)

    console.print(f"Applying OpenLattice spec: [bold]{spec_path.name}[/bold]\n")

    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        sys.exit(1)

    out_dir = Path.cwd() / "generated"
    out_dir.mkdir(exist_ok=True)

    files = [
        (out_dir / "main.py", fastapi_gen.generate(spec)),
        (out_dir / "models.py", sqlalchemy_gen.generate(spec)),
    ]

    for file_path, content in files:
        file_path.write_text(content)
        console.print(f"  [bold green]✓[/bold green] generated/{file_path.name}")

    console.print(f"\nDone. {len(files)} files written.")


if __name__ == "__main__":
    cli()
