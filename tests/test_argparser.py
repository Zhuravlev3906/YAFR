from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from yafr.cli.argparser import cli
from yafr.config import ConfigError

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "yafr.config.service.user_config_path",
        lambda *args, **kwargs: tmp_path / "user-config",
    )


@pytest.mark.parametrize("args", [["--help"], ["rename", "--help"]])
def test_help_does_not_load_config(args: list[str]) -> None:
    with patch("yafr.app.load_config") as load:
        result = runner.invoke(cli, args)
    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "rename" in result.stdout
    load.assert_not_called()


def test_no_command_shows_help() -> None:
    result = runner.invoke(cli, [])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "rename" in result.output


def test_default_settings_and_preview_do_not_change_files(tmp_path: Path) -> None:
    source = tmp_path / "Фото с пробелами"
    source.mkdir()
    original = source / "original.jpg"
    original.write_bytes(b"unchanged content")

    result = runner.invoke(cli, ["rename", str(source)])

    assert result.exit_code == 0, result.output
    assert f"Source: {source.resolve()}" in result.stdout
    assert "Pattern: {n}" in result.stdout
    assert "Start: 1" in result.stdout
    assert "Recursive: False" in result.stdout
    assert "Preview only. Use --apply to make changes." in result.stdout
    assert result.stderr == ""
    assert list(source.iterdir()) == [original]
    assert original.read_bytes() == b"unchanged content"
    assert not (tmp_path / "user-config").exists()


@pytest.mark.parametrize(
    ("flags", "expected_pattern", "expected_start", "expected_recursive"),
    [
        ([], "{n:03d}", 7, True),
        (["--no-recursive"], "{n:03d}", 7, False),
        (
            ["--pattern", "S{season:02d}E{episode:02d}", "--start", "3"],
            "S{season:02d}E{episode:02d}",
            3,
            True,
        ),
    ],
)
def test_file_settings_and_cli_overrides(
    tmp_path: Path,
    flags: list[str],
    expected_pattern: str,
    expected_start: int,
    expected_recursive: bool,
) -> None:
    config = tmp_path / "settings.toml"
    content = '[general]\nrecursive = true\n[rename]\npattern = "{n:03d}"\nstart = 7\n'
    config.write_text(content, encoding="utf-8")

    result = runner.invoke(
        cli, ["rename", str(tmp_path), "--config", str(config), *flags]
    )

    assert result.exit_code == 0, result.output
    assert f"Pattern: {expected_pattern}" in result.stdout
    assert f"Start: {expected_start}" in result.stdout
    assert f"Recursive: {expected_recursive}" in result.stdout
    assert config.read_text(encoding="utf-8") == content


def test_recursive_flag_enables_recursion(tmp_path: Path) -> None:
    result = runner.invoke(cli, ["rename", str(tmp_path), "--recursive"])
    assert result.exit_code == 0, result.output
    assert "Recursive: True" in result.stdout


def test_relative_source_is_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["rename", "."])
    assert result.exit_code == 0, result.output
    assert f"Source: {tmp_path.resolve()}" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["rename"],
        ["unknown"],
        ["rename", ".", "--start", "0"],
        ["rename", ".", "--start", "-1"],
        ["rename", ".", "--start", "text"],
        ["rename", ".", "--start"],
        ["rename", ".", "--unknown"],
    ],
)
def test_bad_arguments_fail_before_loading_config(args: list[str]) -> None:
    with patch("yafr.app.load_config") as load:
        result = runner.invoke(cli, args)
    assert result.exit_code == 2
    assert result.stderr
    assert "Preview only" not in result.output
    load.assert_not_called()


@pytest.mark.parametrize("is_file", [False, True])
def test_source_must_be_an_existing_directory(tmp_path: Path, is_file: bool) -> None:
    source = tmp_path / "source"
    if is_file:
        source.write_text("file", encoding="utf-8")
    with patch("yafr.app.load_config") as load:
        result = runner.invoke(cli, ["rename", str(source)])
    assert result.exit_code == 2
    assert result.stderr
    load.assert_not_called()


@pytest.mark.parametrize("content", [None, "[broken", "[rename]\nstart = 0"])
def test_config_errors_go_to_stderr(tmp_path: Path, content: str | None) -> None:
    config = tmp_path / "invalid.toml"
    if content is not None:
        config.write_text(content, encoding="utf-8")
    result = runner.invoke(cli, ["rename", str(tmp_path), "--config", str(config)])
    assert result.exit_code == 2
    assert str(config) in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output
    if content is None:
        assert not config.exists()


def test_invalid_pattern_goes_through_config_validation(tmp_path: Path) -> None:
    result = runner.invoke(cli, ["rename", str(tmp_path), "--pattern", "{unknown}"])
    assert result.exit_code == 2
    assert "rename.pattern" in result.stderr
    assert result.stdout == ""


def test_config_error_is_displayed_without_traceback(tmp_path: Path) -> None:
    with patch("yafr.app.load_config", side_effect=ConfigError("Access denied")):
        result = runner.invoke(cli, ["rename", str(tmp_path)])
    assert result.exit_code == 2
    assert result.stderr == "Access denied\n"
    assert result.stdout == ""
