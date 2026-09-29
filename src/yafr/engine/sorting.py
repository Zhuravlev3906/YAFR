from collections.abc import Iterable, Mapping
from pathlib import Path

from yafr.engine.discovery import directory_root, discover_files, file_state
from yafr.engine.errors import PlanError
from yafr.engine.models import Operation, OperationPlan
from yafr.engine.planning import (
    check_name,
    check_parents,
    extension,
    name_key,
    normalize_extensions,
    validate_plan,
)


def plan_sort(
    source: str | Path,
    *,
    groups: Mapping[str, Iterable[str]],
    output: str | Path | None = None,
    fallback: str | None = None,
    recursive: bool = False,
    include_hidden: bool = False,
    exclude: Iterable[Path] = (),
) -> OperationPlan:
    """Build a sorting plan; unknown extensions stay unless fallback is set."""
    try:
        root = directory_root(source)
        target = root if output is None else Path(output).expanduser().absolute()
        check_parents(target)
        target = target.resolve()
        lookup: dict[str, str] = {}
        names: set[str] = set()
        for group, values in groups.items():
            check_name(group)
            if name_key(group) in names:
                raise PlanError(f"Duplicate group name: {group}")
            names.add(name_key(group))
            for suffix in normalize_extensions(values):
                if suffix in lookup:
                    raise PlanError(f"Duplicate extension: {suffix}")
                lookup[suffix] = group
        if fallback is not None:
            check_name(fallback)
            if name_key(fallback) in names and fallback not in groups:
                raise PlanError(f"Fallback conflicts with a group name: {fallback}")
        folders = {target / name for name in groups}
        if fallback is not None:
            folders.add(target / fallback)
        for folder in folders:
            check_parents(folder)
            if root == folder or root.is_relative_to(folder):
                raise PlanError("Source must not be inside a destination group")
        files = discover_files(
            root,
            recursive=recursive,
            include_hidden=include_hidden,
            exclude=(*exclude, *folders),
        )
        operations = []
        for path in files:
            destination_group = lookup.get(
                extension(path, lookup)[1:].casefold(), fallback
            )
            destination = (
                path
                if destination_group is None
                else target / destination_group / path.name
            )
            operations.append(Operation(path, destination, file_state(path)))
        # Skipped files may remain outside an external output root.
        plan = OperationPlan(root, target, tuple(operations))
        validate_plan(plan)
        return plan
    except OSError as exc:
        raise PlanError(str(exc)) from exc
