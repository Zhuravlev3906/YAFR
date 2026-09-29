import ctypes
import errno
import os
import sys
from pathlib import Path

from yafr.engine.errors import EngineError
from yafr.engine.models import (
    ExecutionReport,
    OperationPlan,
    OperationResult,
    OperationStatus,
)
from yafr.engine.planning import check_parents, validate_plan

_RENAME_EXCL = 4
_RENAME_NOREPLACE = 1
_AT_FDCWD = -100


def _move_no_replace(source: Path, destination: Path) -> None:
    """Use native exclusive rename; never fall back to overwriting rename."""
    if sys.platform == "win32":
        os.rename(source, destination)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(destination), _RENAME_EXCL)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            _AT_FDCWD,
            os.fsencode(source),
            _AT_FDCWD,
            os.fsencode(destination),
            _RENAME_NOREPLACE,
        )
    else:
        raise OSError(errno.ENOTSUP, "Exclusive rename is not supported")
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def execute_plan(plan: OperationPlan, *, apply: bool = False) -> ExecutionReport:
    """Validate first, then preview or execute. Stop on the first failure."""
    validate_plan(plan)
    results: list[OperationResult] = []
    stopped = False
    interrupted = False
    for operation in plan.operations:
        if stopped:
            results.append(OperationResult(operation, OperationStatus.NOT_STARTED))
            continue
        if operation.source == operation.destination:
            results.append(
                OperationResult(
                    operation,
                    OperationStatus.SKIPPED,
                    "Already in place or no matching group",
                )
            )
            continue
        if not apply:
            results.append(OperationResult(operation, OperationStatus.PREVIEW))
            continue
        try:
            single = OperationPlan(
                plan.source_root, plan.destination_root, (operation,)
            )
            validate_plan(single)
            check_parents(operation.destination.parent)
            operation.destination.parent.mkdir(parents=True, exist_ok=True)
            validate_plan(single)
            _move_no_replace(operation.source, operation.destination)
        except (OSError, EngineError) as exc:
            results.append(OperationResult(operation, OperationStatus.FAILED, str(exc)))
            stopped = True
        except KeyboardInterrupt:
            results.append(
                OperationResult(
                    operation,
                    OperationStatus.FAILED,
                    "Interrupted; inspect source and destination before retrying",
                )
            )
            stopped = interrupted = True
        else:
            results.append(OperationResult(operation, OperationStatus.COMPLETED))
    return ExecutionReport(tuple(results), interrupted)
