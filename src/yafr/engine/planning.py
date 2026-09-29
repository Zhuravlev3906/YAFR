import os
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from yafr.engine.discovery import file_state
from yafr.engine.errors import PlanError
from yafr.engine.models import OperationPlan


def name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def check_name(name: str) -> None:
    if not name.strip() or name in {".", ".."} or any(c in name for c in "/\\\0"):
        raise PlanError(f"Invalid file name: {name!r}")
    if os.name == "nt":
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(
            f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
        )
        if (
            len(name.encode("utf-16-le")) // 2 > 255
            or any(ord(c) < 32 or c in '<>:"|?*' for c in name)
            or name.endswith((".", " "))
            or name.split(".")[0].upper() in reserved
        ):
            raise PlanError(f"Invalid Windows file name: {name!r}")


def check_parents(path: Path) -> Path:
    """Reject links and non-directories; return the nearest existing parent."""
    nearest: Path | None = None
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise PlanError(f"Symbolic link in destination or source path: {parent}")
        if parent.exists():
            if not parent.is_dir():
                raise PlanError(f"Not a directory: {parent}")
            if nearest is None:
                nearest = parent
    if nearest is None:
        raise PlanError(f"No existing parent: {path}")
    return nearest


def extension(path: Path, known: Iterable[str]) -> str:
    for suffix in sorted(known, key=len, reverse=True):
        if path.name.casefold().endswith("." + suffix.casefold()):
            return path.name[-len(suffix) - 1 :]
    return path.suffix


def normalize_extensions(values: Iterable[str]) -> tuple[str, ...]:
    result = []
    for value in values:
        if (
            not value
            or any(not part for part in value.split("."))
            or any(c.isspace() or c in "/\\\0:" for c in value)
        ):
            raise PlanError(f"Invalid extension: {value!r}")
        result.append(value.casefold())
    return tuple(result)


def validate_plan(plan: OperationPlan) -> None:
    """Check the entire plan before any changes are made."""
    try:
        sources: set[Path] = set()
        destinations: set[str] = set()
        for operation in plan.operations:
            source, destination = operation.source, operation.destination
            if (
                not source.is_absolute()
                or not destination.is_absolute()
                or ".." in source.parts
                or ".." in destination.parts
                or not source.is_relative_to(plan.source_root)
                or (
                    source != destination
                    and not destination.is_relative_to(plan.destination_root)
                )
            ):
                raise PlanError("Operation escapes the plan roots")
            check_name(destination.name)
            check_parents(source.parent)
            parent = check_parents(destination.parent)
            if os.name == "posix":
                limit = os.pathconf(parent, "PC_NAME_MAX")
                if limit > 0 and len(os.fsencode(destination.name)) > limit:
                    raise PlanError(f"File name is too long: {destination.name!r}")
            if file_state(source) != operation.state:
                raise PlanError(f"Source changed since planning: {source}")
            if source in sources:
                raise PlanError(f"Duplicate source: {source}")
            sources.add(source)
            key = name_key(str(destination))
            if key in destinations:
                raise PlanError(f"Duplicate destination: {destination}")
            destinations.add(key)
            if source == destination:
                continue
            if operation.state.device != parent.stat().st_dev:
                raise PlanError(
                    f"Cross-filesystem move is not supported: {destination}"
                )
            if destination.parent.exists():
                for existing in destination.parent.iterdir():
                    if name_key(existing.name) == name_key(destination.name):
                        raise PlanError(f"Destination already exists: {existing}")
    except OSError as exc:
        raise PlanError(str(exc)) from exc
