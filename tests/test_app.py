import errno
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from yafr.app import main, prepare_operation, run_operation
from yafr.cli.argparser import cli
from yafr.engine import PlanError

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("yafr.app", "yafr.config.service"):
        monkeypatch.setattr(
            f"{module}.user_config_path", lambda *args, **kwargs: tmp_path
        )


def test_app_excludes_default_config_and_preserves_compound_suffix(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    content = '[rename]\npattern = "{n:03d}"\n'
    config.write_text(content)
    (tmp_path / "archive.tar.gz").write_bytes(b"archive")
    operation = prepare_operation("rename", tmp_path)
    assert len(operation.plan.operations) == 1
    assert operation.plan.operations[0].destination.name == "001.tar.gz"
    assert run_operation(operation).successful
    assert (tmp_path / "archive.tar.gz").exists()
    assert run_operation(operation, apply=True).successful
    assert (tmp_path / "001.tar.gz").read_bytes() == b"archive"
    assert config.read_text() == content


def test_app_applies_same_plan_and_rejects_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "a.jpg"
    source.write_bytes(b"before")
    operation = prepare_operation("rename", tmp_path)
    source.write_bytes(b"after change")
    with pytest.raises(PlanError):
        run_operation(operation, apply=True)
    assert not (tmp_path / "1.jpg").exists()


def test_rename_cli_applies_settings_and_excludes_explicit_config(
    tmp_path: Path,
) -> None:
    source = tmp_path / "a.mkv"
    source.write_bytes(b"video")
    config = tmp_path / "settings.toml"
    config.write_text('[rename]\npattern = "S{season:02d}E{episode:02d}"')
    result = runner.invoke(
        cli,
        [
            "rename",
            str(tmp_path),
            "--config",
            str(config),
            "--season",
            "2",
            "--start",
            "3",
            "--ext",
            "mkv",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "S02E03.mkv").read_bytes() == b"video"
    assert config.exists()
    assert "completed: 1" in result.stdout


@pytest.mark.parametrize("apply", [False, True])
def test_sort_cli_preview_and_apply(tmp_path: Path, apply: bool) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"photo")
    output = tmp_path / "sorted"
    args = ["sort", str(source), "--output", str(output)]
    args.append("--apply" if apply else "--dry-run")
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert (output / "images/a.jpg").exists() is apply
    assert (source / "a.jpg").exists() is not apply
    if not apply:
        assert not output.exists()


@pytest.mark.parametrize("command", ["sort", "rename"])
def test_conflicting_flags_fail_before_preparation(
    tmp_path: Path, command: str
) -> None:
    with patch("yafr.cli.argparser.prepare_operation") as prepare:
        result = runner.invoke(cli, [command, str(tmp_path), "--apply", "--dry-run"])
    assert result.exit_code == 2
    prepare.assert_not_called()


def test_engine_failure_returns_nonzero_and_report(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"photo")
    (tmp_path / "b.jpg").write_bytes(b"photo")
    with patch(
        "yafr.engine.executor._move_no_replace",
        side_effect=OSError(errno.EACCES, "Denied"),
    ):
        result = runner.invoke(cli, ["rename", str(tmp_path), "--apply"])
    assert result.exit_code == 1
    assert "Denied" in result.stderr
    assert "failed: 1" in result.stdout
    assert "not_started: 1" in result.stdout
    assert (tmp_path / "a.jpg").exists()


def test_engine_interruption_returns_130(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"photo")
    with patch("yafr.engine.executor._move_no_replace", side_effect=KeyboardInterrupt):
        result = runner.invoke(cli, ["rename", str(tmp_path), "--apply"])
    assert result.exit_code == 130
    assert "Interrupted" in result.stderr


def test_entry_point_runs_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["yafr", "--help"])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 0
    output = capsys.readouterr().out
    assert "rename" in output
    assert "sort" in output
