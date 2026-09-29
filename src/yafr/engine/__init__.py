"""Plan and execute local file operations without UI dependencies."""

from yafr.engine.discovery import discover_files
from yafr.engine.errors import EngineError, PlanError
from yafr.engine.executor import execute_plan
from yafr.engine.models import (
    ExecutionReport,
    FileState,
    Operation,
    OperationPlan,
    OperationResult,
    OperationStatus,
)
from yafr.engine.renaming import plan_rename
from yafr.engine.sorting import plan_sort

__all__ = [
    "EngineError",
    "ExecutionReport",
    "FileState",
    "Operation",
    "OperationPlan",
    "OperationResult",
    "OperationStatus",
    "PlanError",
    "discover_files",
    "execute_plan",
    "plan_rename",
    "plan_sort",
]
