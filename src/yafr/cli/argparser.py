from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from yafr.app import prepare_operation, run_operation
from yafr.config import ConfigError
from yafr.engine import EngineError, OperationStatus, PlanError

cli = typer.Typer(no_args_is_help=True)


@cli.callback()
def root() -> None:
    """Organize and rename local files."""


@cli.command()
def rename(
    source: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, resolve_path=True),
    ],
    config_file: Annotated[
        Path | None,
        typer.Option("--config", help="Config file path."),
    ] = None,
    pattern: Annotated[
        str | None,
        typer.Option(help="File name pattern."),
    ] = None,
    start: Annotated[
        int | None,
        typer.Option(min=1, help="First file number."),
    ] = None,
    season: Annotated[int | None, typer.Option(min=1)] = None,
    extensions: Annotated[list[str] | None, typer.Option("--ext")] = None,
    include_hidden: Annotated[
        bool | None, typer.Option("--include-hidden/--no-include-hidden")
    ] = None,
    apply: Annotated[bool, typer.Option("--apply")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    recursive: Annotated[
        bool | None,
        typer.Option("--recursive/--no-recursive"),
    ] = None,
) -> None:
    """Preview or apply batch renaming."""
    overrides: dict[str, Any] = {}

    rename_options = {
        key: value
        for key, value in {"pattern": pattern, "start": start, "season": season}.items()
        if value is not None
    }

    if rename_options:
        overrides["rename"] = rename_options

    general = {
        key: value
        for key, value in {
            "recursive": recursive,
            "include_hidden": include_hidden,
        }.items()
        if value is not None
    }
    if general:
        overrides["general"] = general
    _run("rename", source, config_file, overrides, apply, dry_run, extensions)


@cli.command()
def sort(
    source: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)
    ],
    config_file: Annotated[
        Path | None, typer.Option("--config", help="Config file path.")
    ] = None,
    output: Annotated[Path | None, typer.Option(help="Destination folder.")] = None,
    recursive: Annotated[
        bool | None, typer.Option("--recursive/--no-recursive")
    ] = None,
    include_hidden: Annotated[
        bool | None, typer.Option("--include-hidden/--no-include-hidden")
    ] = None,
    apply: Annotated[bool, typer.Option("--apply")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Preview or apply sorting by extension."""
    overrides: dict[str, Any] = {}
    if output is not None:
        overrides["sort"] = {"output": str(output)}
    general = {
        key: value
        for key, value in {
            "recursive": recursive,
            "include_hidden": include_hidden,
        }.items()
        if value is not None
    }
    if general:
        overrides["general"] = general
    _run("sort", source, config_file, overrides, apply, dry_run)


def _run(
    command: Literal["rename", "sort"],
    source: Path,
    config_file: Path | None,
    overrides: dict[str, Any],
    apply: bool,
    dry_run: bool,
    extensions: list[str] | None = None,
) -> None:
    if apply and dry_run:
        raise typer.BadParameter("--apply and --dry-run cannot be used together")
    try:
        operation = prepare_operation(
            command,
            source,
            config_file=config_file,
            overrides=overrides,
            extensions=extensions,
        )
        typer.echo(f"Source: {operation.plan.source_root}")
        if command == "rename":
            typer.echo(f"Pattern: {operation.config.rename.pattern}")
            typer.echo(f"Start: {operation.config.rename.start}")
        typer.echo(f"Recursive: {operation.config.general.recursive}")
        for item in operation.plan.operations:
            typer.echo(f"{item.source} -> {item.destination}")
        report = run_operation(operation, apply=apply)
    except (ConfigError, PlanError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    except (EngineError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    except KeyboardInterrupt:
        typer.echo("Interrupted.", err=True)
        raise typer.Exit(code=130) from None

    for result in report.results:
        if result.status == OperationStatus.FAILED:
            typer.echo(f"Failed: {result.operation.source}: {result.reason}", err=True)
    counts = {
        status: sum(result.status == status for result in report.results)
        for status in OperationStatus
    }
    typer.echo(
        ", ".join(f"{status.value}: {count}" for status, count in counts.items())
    )
    if not apply:
        typer.echo("Preview only. Use --apply to make changes.")
    if report.interrupted:
        raise typer.Exit(code=130)
    if not report.successful:
        raise typer.Exit(code=1)
