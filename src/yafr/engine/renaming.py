import re
from collections.abc import Iterable
from pathlib import Path
from string import Formatter

from yafr.engine.discovery import directory_root, discover_files, file_state
from yafr.engine.errors import PlanError
from yafr.engine.models import Operation, OperationPlan
from yafr.engine.planning import (
    check_name,
    extension,
    normalize_extensions,
    validate_plan,
)


def plan_rename(
    source: str | Path,
    *,
    pattern: str = "{n}",
    start: int = 1,
    season: int = 1,
    extensions: Iterable[str] | None = None,
    known_extensions: Iterable[str] = (),
    recursive: bool = False,
    include_hidden: bool = False,
    exclude: Iterable[Path] = (),
) -> OperationPlan:
    """Build a rename plan without changing files."""
    try:
        if type(start) is not int or type(season) is not int or min(start, season) < 1:
            raise PlanError("Start and season must be positive integers")
        for _, field, spec, conversion in Formatter().parse(pattern):
            if field is None:
                continue
            spec = spec or ""
            if field not in {"n", "season", "episode"} or conversion is not None:
                raise PlanError(f"Invalid pattern field: {field!r}")
            if not re.fullmatch(r"(?:0[1-9][0-9]*d)?", spec):
                raise PlanError(f"Invalid number format: {spec!r}")
            if spec and int(spec[1:-1]) > 255:
                raise PlanError("Padding width must not exceed 255")
        check_name(pattern.format(n=start, season=season, episode=start))
        root = directory_root(source)
        selected = None if extensions is None else normalize_extensions(extensions)
        known = normalize_extensions(known_extensions) + (selected or ())
        files = discover_files(
            root, recursive=recursive, include_hidden=include_hidden, exclude=exclude
        )
        operations = []
        number = start
        for path in files:
            suffix = extension(path, known)
            if selected is not None and suffix[1:].casefold() not in selected:
                continue
            name = pattern.format(n=number, season=season, episode=number) + suffix
            check_name(name)
            operations.append(Operation(path, path.with_name(name), file_state(path)))
            number += 1
        plan = OperationPlan(root, root, tuple(operations))
        validate_plan(plan)
        return plan
    except (OSError, ValueError) as exc:
        raise PlanError(str(exc)) from exc
