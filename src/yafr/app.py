from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_config_path

from yafr.config import Config, load_config
from yafr.engine import (
    ExecutionReport,
    OperationPlan,
    execute_plan,
    plan_rename,
    plan_sort,
)


@dataclass(frozen=True)
class PreparedOperation:
    config: Config
    plan: OperationPlan


def prepare_operation(
    command: Literal["rename", "sort"],
    source: Path,
    *,
    config_file: Path | None = None,
    overrides: dict[str, Any] | None = None,
    extensions: list[str] | None = None,
) -> PreparedOperation:
    """Load settings and build a plan without modifying files."""
    config = load_config(config_file, overrides=overrides)
    config_path = (
        config_file.expanduser()
        if config_file is not None
        else user_config_path("yafr", appauthor=False) / "config.toml"
    ).resolve()
    if command == "rename":
        plan = plan_rename(
            source,
            pattern=config.rename.pattern,
            start=config.rename.start,
            season=config.rename.season,
            extensions=extensions,
            known_extensions=[
                extension
                for values in config.sort.groups.values()
                for extension in values
            ],
            recursive=config.general.recursive,
            include_hidden=config.general.include_hidden,
            exclude=[config_path],
        )
    elif command == "sort":
        plan = plan_sort(
            source,
            groups=config.sort.groups,
            output=config.sort.output,
            fallback=config.sort.fallback,
            recursive=config.general.recursive,
            include_hidden=config.general.include_hidden,
            exclude=[config_path],
        )
    else:
        raise ValueError(f"Unknown command: {command}")
    return PreparedOperation(config, plan)


def run_operation(
    operation: PreparedOperation, *, apply: bool = False
) -> ExecutionReport:
    """Execute the prepared plan only when explicitly requested."""
    return execute_plan(operation.plan, apply=apply)


def main() -> None:
    from yafr.cli.argparser import cli

    try:
        cli()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
