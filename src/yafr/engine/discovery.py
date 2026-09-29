import os
import re
import stat
from collections.abc import Iterable
from pathlib import Path

from yafr.engine.errors import PlanError
from yafr.engine.models import FileState


def file_state(path: Path) -> FileState:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise PlanError(f"Not a regular file: {path}")
    return FileState(
        info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    )


def directory_root(path: str | Path) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink():
        raise PlanError(f"Source must not be a symbolic link: {path}")
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise PlanError(f"Not a directory: {root}")
    return root


def _natural_key(
    path: Path, root: Path
) -> tuple[tuple[tuple[int, str | int], ...], str]:
    name = path.relative_to(root).as_posix()
    parts = re.split(r"([0-9]+)", name.casefold())
    key = tuple((1, int(part)) if part.isdecimal() else (0, part) for part in parts)
    return key, name


def discover_files(
    source: str | Path,
    *,
    recursive: bool = False,
    include_hidden: bool = False,
    exclude: Iterable[Path] = (),
) -> tuple[Path, ...]:
    """Collect regular files in natural order without following links."""
    try:
        root = directory_root(source)
        excluded = {path.absolute() for path in exclude}
        found: list[Path] = []
        pending = [root]
        while pending:
            folder = pending.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    if path in excluded or entry.is_symlink():
                        continue
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if recursive:
                            pending.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        found.append(path)
        return tuple(sorted(found, key=lambda path: _natural_key(path, root)))
    except OSError as exc:
        raise PlanError(f"Cannot scan {source}: {exc}") from exc
