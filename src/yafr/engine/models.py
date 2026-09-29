from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True)
class FileState:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True)
class Operation:
    source: Path
    destination: Path
    state: FileState


@dataclass(frozen=True)
class OperationPlan:
    source_root: Path
    destination_root: Path
    operations: tuple[Operation, ...]


class OperationStatus(StrEnum):
    PREVIEW = "preview"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class OperationResult:
    operation: Operation
    status: OperationStatus
    reason: str | None = None


@dataclass(frozen=True)
class ExecutionReport:
    results: tuple[OperationResult, ...]
    interrupted: bool = False

    @property
    def successful(self) -> bool:
        return not self.interrupted and all(
            result.status not in {OperationStatus.FAILED, OperationStatus.NOT_STARTED}
            for result in self.results
        )
