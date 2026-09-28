from pathlib import Path
from typing import Annotated, Any

import typer

from yafr.config import ConfigError, load_config

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
    recursive: Annotated[
        bool | None,
        typer.Option("--recursive/--no-recursive"),
    ] = None,
) -> None:
    """Check settings for batch renaming."""
    overrides: dict[str, Any] = {}

    rename_options = {
        key: value
        for key, value in {"pattern": pattern, "start": start}.items()
        if value is not None
    }

    if rename_options:
        overrides["rename"] = rename_options

    if recursive is not None:
        overrides["general"] = {"recursive": recursive}

    try:
        config = load_config(config_file, overrides=overrides)
    except ConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    typer.echo(f"Source: {source}")
    typer.echo(f"Pattern: {config.rename.pattern}")
    typer.echo(f"Start: {config.rename.start}")
    typer.echo(f"Recursive: {config.general.recursive}")
    typer.echo("Preview only: the engine is not implemented.")
