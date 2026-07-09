from pathlib import Path

import pytest
from click.testing import CliRunner

from openlattice.cli import cli

SPEC_A = """
resource "lattice_entity" "author" {
  name = "Author"
  fields = {
    id       = "uuid"
    username = "string"
  }
}
"""

SPEC_B = """
resource "lattice_entity" "product" {
  name = "Product"
  fields = {
    id    = "uuid"
    price = "int"
  }
}
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_spec(tmp_path: Path, name: str, content: str) -> Path:
    spec_path = tmp_path / name
    spec_path.write_text(content)
    return spec_path


def test_apply_with_output_dir_writes_files_there(runner: CliRunner, tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, "a.lattice", SPEC_A)
    out_dir = tmp_path / "out_a"
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        cli,
        [
            "apply",
            str(spec_path),
            "--output-dir",
            str(out_dir),
            "--state-file",
            str(state_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "schemas.py").exists()
    assert (out_dir / "models.py").exists()
    assert (out_dir / "routes.py").exists()
    assert (out_dir / "app.py").exists()
    assert not (tmp_path / "generated").exists()


def test_apply_output_dir_without_state_file_colocates_state(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path, "a.lattice", SPEC_A)
    out_dir = tmp_path / "out_a"

    result = runner.invoke(cli, ["apply", str(spec_path), "--output-dir", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert (out_dir / ".lattice-state.json").exists()
    assert not (tmp_path / ".lattice-state.json").exists()


def test_apply_with_neither_flag_preserves_default_behavior(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    spec_path = _write_spec(tmp_path, "a.lattice", SPEC_A)

    result = runner.invoke(cli, ["apply", str(spec_path)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "generated" / "schemas.py").exists()
    assert (tmp_path / "generated" / "models.py").exists()
    assert (tmp_path / "generated" / "routes.py").exists()
    assert (tmp_path / "generated" / "app.py").exists()
    assert (tmp_path / ".lattice-state.json").exists()


def test_apply_two_specs_two_output_dirs_no_cross_contamination(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_a = _write_spec(tmp_path, "a.lattice", SPEC_A)
    spec_b = _write_spec(tmp_path, "b.lattice", SPEC_B)
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    result_a = runner.invoke(cli, ["apply", str(spec_a), "--output-dir", str(out_a)])
    result_b = runner.invoke(cli, ["apply", str(spec_b), "--output-dir", str(out_b)])

    assert result_a.exit_code == 0, result_a.output
    assert result_b.exit_code == 0, result_b.output

    main_a = (out_a / "schemas.py").read_text()
    models_a = (out_a / "models.py").read_text()
    main_b = (out_b / "schemas.py").read_text()
    models_b = (out_b / "models.py").read_text()

    assert "Author" in main_a or "Author" in models_a
    assert "Product" in main_b or "Product" in models_b
    assert "Product" not in main_a and "Product" not in models_a
    assert "Author" not in main_b and "Author" not in models_b

    assert (out_a / ".lattice-state.json").exists()
    assert (out_b / ".lattice-state.json").exists()


def test_plan_accepts_output_dir_flag(runner: CliRunner, tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, "a.lattice", SPEC_A)
    out_dir = tmp_path / "out_a"

    result = runner.invoke(cli, ["plan", str(spec_path), "--output-dir", str(out_dir)])

    assert result.exit_code == 0, result.output
    # Rich may wrap/truncate long paths across lines, so check the pieces
    # rather than the exact joined path string.
    output_no_newlines = result.output.replace("\n", "")
    assert "out_a" in output_no_newlines
    assert "schemas.py" in output_no_newlines
    assert "models.py" in output_no_newlines
    assert "routes.py" in output_no_newlines
    assert "app.py" in output_no_newlines
