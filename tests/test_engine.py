import errno
from pathlib import Path
from unittest.mock import patch

import pytest

from yafr.engine import (
    OperationStatus,
    PlanError,
    discover_files,
    execute_plan,
    plan_rename,
    plan_sort,
)
from yafr.engine.executor import _move_no_replace


def make_files(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")


def test_discovery_order_hidden_and_recursion(tmp_path: Path) -> None:
    make_files(tmp_path, "file10.jpg", "file2.jpg", ".hidden", "sub/a", ".cache/b")
    assert [p.name for p in discover_files(tmp_path)] == ["file2.jpg", "file10.jpg"]
    assert len(discover_files(tmp_path, recursive=True)) == 3
    assert len(discover_files(tmp_path, recursive=True, include_hidden=True)) == 5


def test_discovery_excludes_paths_and_links(tmp_path: Path) -> None:
    make_files(tmp_path, "a", "sub/b")
    (tmp_path / "link").symlink_to(tmp_path / "a")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert discover_files(tmp_path, recursive=True, exclude=[tmp_path / "sub"]) == (
        tmp_path / "a",
    )


def test_rename_plan_and_execution_preserve_content(tmp_path: Path) -> None:
    make_files(tmp_path, "episode10.MKV", "episode2.MKV", "notes.txt")
    plan = plan_rename(
        tmp_path, pattern="S{season:02d}E{episode:02d}", season=2, extensions=["mkv"]
    )
    assert [op.destination.name for op in plan.operations] == [
        "S02E01.MKV",
        "S02E02.MKV",
    ]
    assert all(r.status == OperationStatus.PREVIEW for r in execute_plan(plan).results)
    assert (tmp_path / "episode2.MKV").exists()
    report = execute_plan(plan, apply=True)
    assert report.successful
    assert all(r.status == OperationStatus.COMPLETED for r in report.results)
    assert (tmp_path / "S02E01.MKV").read_text() == "episode2.MKV"
    assert (tmp_path / "S02E02.MKV").read_text() == "episode10.MKV"
    assert (tmp_path / "notes.txt").read_text() == "notes.txt"
    assert not (tmp_path / "episode2.MKV").exists()


def test_compound_extensions_and_global_counter(tmp_path: Path) -> None:
    make_files(tmp_path, "a.tar.GZ", "sub/b.tar.gz")
    plan = plan_rename(tmp_path, start=5, recursive=True, known_extensions=["tar.gz"])
    assert [
        op.destination.relative_to(tmp_path).as_posix() for op in plan.operations
    ] == ["5.tar.GZ", "sub/6.tar.gz"]


def test_sort_preview_apply_and_repeat(tmp_path: Path) -> None:
    make_files(tmp_path, "a.JPG", "b.tar.gz", "README", "notes.txt")
    groups = {"images": ["jpg"], "archives": ["gz", "tar.gz"]}
    plan = plan_sort(tmp_path, groups=groups, fallback="other")
    execute_plan(plan)
    assert not (tmp_path / "images").exists()
    assert execute_plan(plan, apply=True).successful
    assert (tmp_path / "images/a.JPG").read_text() == "a.JPG"
    assert (tmp_path / "archives/b.tar.gz").read_text() == "b.tar.gz"
    assert (tmp_path / "other/README").read_text() == "README"
    assert (
        plan_sort(tmp_path, groups=groups, fallback="other", recursive=True).operations
        == ()
    )


def test_sort_external_output_and_unmatched_files(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    make_files(source, "a.jpg", "unknown.bin")
    plan = plan_sort(source, groups={"images": ["jpg"]}, output=output)
    report = execute_plan(plan, apply=True)
    assert report.successful
    assert [r.status for r in report.results] == [
        OperationStatus.COMPLETED,
        OperationStatus.SKIPPED,
    ]
    assert (source / "unknown.bin").exists()
    assert (output / "images/a.jpg").exists()


def test_empty_selection_and_noop(tmp_path: Path) -> None:
    assert execute_plan(plan_rename(tmp_path), apply=True).successful
    make_files(tmp_path, "1.jpg")
    report = execute_plan(plan_rename(tmp_path), apply=True)
    assert report.results[0].status == OperationStatus.SKIPPED
    assert plan_rename(tmp_path, extensions=[]).operations == ()


@pytest.mark.parametrize(
    "pattern",
    ["", "../{n}", "{unknown}", "{n.real}", "{n!r}", "{n:{season}}", "{n:0999d}", "{n"],
)
def test_invalid_patterns_fail_even_for_empty_directory(
    tmp_path: Path, pattern: str
) -> None:
    with pytest.raises(PlanError):
        plan_rename(tmp_path, pattern=pattern)


@pytest.mark.parametrize("number", [0, -1, True])
def test_invalid_numbers(tmp_path: Path, number: int) -> None:
    with pytest.raises(PlanError):
        plan_rename(tmp_path, start=number)


def test_duplicate_destinations_fail_without_changes(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg", "b.jpg")
    with pytest.raises(PlanError):
        plan_rename(tmp_path, pattern="same")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.jpg", "b.jpg"]


def test_occupied_target_and_cycles_are_rejected(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg", "2.jpg")
    with pytest.raises(PlanError):
        plan_rename(tmp_path)
    assert (tmp_path / "2.jpg").read_text() == "2.jpg"


def test_case_only_rename_is_rejected(tmp_path: Path) -> None:
    make_files(tmp_path, "Photo.jpg")
    with pytest.raises(PlanError):
        plan_rename(tmp_path, pattern="photo")


def test_sort_conflicts_across_subdirectories(tmp_path: Path) -> None:
    make_files(tmp_path, "one/a.jpg", "two/a.jpg")
    with pytest.raises(PlanError):
        plan_sort(tmp_path, groups={"images": ["jpg"]}, recursive=True)
    assert not (tmp_path / "images").exists()


def test_destination_link_is_rejected(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg")
    (tmp_path / "images").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PlanError):
        plan_sort(tmp_path, groups={"images": ["jpg"]})


@pytest.mark.parametrize("change", ["modify", "remove", "target"])
def test_stale_plan_fails_before_any_move(tmp_path: Path, change: str) -> None:
    make_files(tmp_path, "a.jpg", "b.jpg")
    plan = plan_rename(tmp_path)
    if change == "modify":
        (tmp_path / "b.jpg").write_text("changed")
    elif change == "remove":
        (tmp_path / "b.jpg").unlink()
    else:
        (tmp_path / "2.jpg").write_text("other file")
    with pytest.raises(PlanError):
        execute_plan(plan, apply=True)
    assert (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "1.jpg").exists()


def test_native_move_never_overwrites(tmp_path: Path) -> None:
    make_files(tmp_path, "source", "destination")
    with pytest.raises(OSError):
        _move_no_replace(tmp_path / "source", tmp_path / "destination")
    assert (tmp_path / "source").read_text() == "source"
    assert (tmp_path / "destination").read_text() == "destination"


def test_target_created_during_execution_is_preserved(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg")
    plan = plan_rename(tmp_path)

    def race(source: Path, destination: Path) -> None:
        destination.write_text("other file")
        _move_no_replace(source, destination)

    with patch("yafr.engine.executor._move_no_replace", side_effect=race):
        report = execute_plan(plan, apply=True)
    assert not report.successful
    assert (tmp_path / "1.jpg").read_text() == "other file"
    assert (tmp_path / "a.jpg").exists()


def test_failure_reports_partial_execution(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg", "b.jpg", "c.jpg")
    plan = plan_rename(tmp_path)

    def move(source: Path, destination: Path) -> None:
        if source.name == "b.jpg":
            raise PermissionError("Access denied")
        _move_no_replace(source, destination)

    with patch("yafr.engine.executor._move_no_replace", side_effect=move):
        report = execute_plan(plan, apply=True)
    assert [r.status for r in report.results] == [
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.NOT_STARTED,
    ]
    assert "Access denied" in (report.results[1].reason or "")
    assert not report.successful
    assert (tmp_path / "1.jpg").read_text() == "a.jpg"
    assert (tmp_path / "b.jpg").exists()
    assert (tmp_path / "c.jpg").exists()


def test_cross_device_error_preserves_source(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg")
    plan = plan_rename(tmp_path)
    with patch(
        "yafr.engine.executor._move_no_replace",
        side_effect=OSError(errno.EXDEV, "Cross-device move"),
    ):
        report = execute_plan(plan, apply=True)
    assert not report.successful
    assert (tmp_path / "a.jpg").exists()


def test_interruption_returns_report(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg", "b.jpg")
    with patch("yafr.engine.executor._move_no_replace", side_effect=KeyboardInterrupt):
        report = execute_plan(plan_rename(tmp_path), apply=True)
    assert report.interrupted
    assert not report.successful
    assert report.results[1].status == OperationStatus.NOT_STARTED


@pytest.mark.parametrize(
    "groups",
    [
        {"../outside": ["jpg"]},
        {"a": ["jpg"], "b": ["JPG"]},
        {"a": [".jpg"]},
        {"A": ["jpg"], "a": ["png"]},
    ],
)
def test_invalid_sort_rules(tmp_path: Path, groups: dict[str, list[str]]) -> None:
    with pytest.raises(PlanError):
        plan_sort(tmp_path, groups=groups)


def test_sort_skips_config_and_existing_group_directories(tmp_path: Path) -> None:
    make_files(tmp_path, "config.toml", "a.jpg", "images/old.jpg")
    plan = plan_sort(
        tmp_path,
        groups={"images": ["jpg"]},
        fallback="other",
        recursive=True,
        exclude=[tmp_path / "config.toml"],
    )
    assert len(plan.operations) == 1
    assert plan.operations[0].source.name == "a.jpg"


def test_source_cannot_be_destination_group(tmp_path: Path) -> None:
    source = tmp_path / "images"
    source.mkdir()
    with pytest.raises(PlanError):
        plan_sort(source, output=tmp_path, groups={"images": ["jpg"]})


def test_plan_cannot_escape_destination_root(tmp_path: Path) -> None:
    from dataclasses import replace

    make_files(tmp_path, "a.jpg")
    plan = plan_rename(tmp_path)
    operation = replace(plan.operations[0], destination=tmp_path.parent / "escape.jpg")
    with pytest.raises(PlanError):
        execute_plan(replace(plan, operations=(operation,)), apply=True)
    assert (tmp_path / "a.jpg").exists()


def test_replaced_source_symlink_is_rejected(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg", "other.txt")
    plan = plan_rename(tmp_path, extensions=["jpg"])
    (tmp_path / "a.jpg").unlink()
    (tmp_path / "a.jpg").symlink_to(tmp_path / "other.txt")
    with pytest.raises(PlanError):
        execute_plan(plan, apply=True)
    assert (tmp_path / "other.txt").read_text() == "other.txt"


def test_unsupported_exclusive_rename_preserves_source(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg")
    with patch("yafr.engine.executor.sys.platform", "unsupported"):
        report = execute_plan(plan_rename(tmp_path), apply=True)
    assert report.results[0].status == OperationStatus.FAILED
    assert (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "1.jpg").exists()


def test_long_name_is_rejected_during_planning(tmp_path: Path) -> None:
    make_files(tmp_path, "a.jpg")
    with pytest.raises(PlanError):
        plan_rename(tmp_path, pattern="x" * 300)
