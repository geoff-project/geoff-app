#!/usr/bin/env python
"""Tests for `acc_app_optimisation.foreign_imports`."""

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = import-outside-toplevel

import typing as t
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from acc_app_optimisation import foreign_imports


def test_import_module(mocker: MockerFixture, tmp_path: Path) -> Path:
    sys_modules = mocker.patch("sys.modules", {})
    name = "module"
    value = Mock()
    path = tmp_path / f"{name}.py"
    with path.open("w") as outfile:
        outfile.write(f"needle = {repr(str(value))}")
    module = foreign_imports.import_from_path(str(path))
    assert module.needle == str(value)
    assert module.__name__ == name
    assert module.__package__ == ""
    assert name in sys_modules


def test_import_package(mocker: MockerFixture, tmp_path: Path) -> Path:
    sys_modules = mocker.patch("sys.modules", {})
    name = "package"
    value = Mock()
    path = tmp_path / name
    path.mkdir()
    with (path / "__init__.py").open("w") as outfile:
        outfile.write(f"needle = {repr(str(value))}")
    module = foreign_imports.import_from_path(str(path))
    assert module.needle == str(value)
    assert module.__name__ == name
    assert module.__package__ == name
    assert name in sys_modules


def test_import_submodule(mocker: MockerFixture, tmp_path: Path) -> Path:
    sys_modules = mocker.patch("sys.modules", {})
    name = "package"
    value = Mock()
    path = tmp_path / name
    path.mkdir()
    (path / "__init__.py").touch()
    with (path / "first.py").open("w") as outfile:
        outfile.write(f"needle = {repr(str(value))}")
    with (path / "second.py").open("w") as outfile:
        outfile.write("from . import first")
    module = foreign_imports.import_from_path(str(path) + "::second")
    assert module.first.needle == str(value)
    assert module.first.__name__ == f"{name}.first"
    assert module.first.__package__ == name
    assert module.__name__ == f"{name}.second"
    assert module.__package__ == name
    assert name in sys_modules
    assert f"{name}.first" in sys_modules
    assert f"{name}.second" in sys_modules


def test_backup_stack(mocker: MockerFixture) -> None:
    outer = mocker.patch("sys.modules", {"outer": Mock()})
    backup_stack = foreign_imports.BackupModules()
    # Stack: []
    with pytest.raises(IndexError):
        _ = backup_stack.modules
    with backup_stack:
        inner = mocker.patch("sys.modules", {"inner": Mock()})
        # Stack: [outer]
        assert backup_stack.modules == outer
        with backup_stack:
            # Stack: [outer, inner]
            assert backup_stack.modules == inner
        # Stack: [outer]
        assert backup_stack.modules == outer
    # Stack: []
    with pytest.raises(IndexError):
        _ = backup_stack.modules


def test_backup_keep_on_success(mocker: MockerFixture) -> None:
    import sys

    outer = mocker.patch("sys.modules", {"outer": Mock()})
    backup_stack = foreign_imports.BackupModules(keep_on_success=True)
    # On failure, sys.modules is restored.
    with pytest.raises(ValueError):
        with backup_stack:
            inner = mocker.patch("sys.modules", {"inner": Mock()})
            raise ValueError()
    assert sys.modules == outer
    # On success, it remains at inner, but backup_stack still pop its
    # stack.
    with backup_stack:
        inner = mocker.patch("sys.modules", {"inner": Mock()})
    assert sys.modules == inner
    with pytest.raises(IndexError):
        _ = backup_stack.modules


def test_report_modification() -> None:
    import sys

    with foreign_imports.BackupModules() as backup:
        sys.modules = {"first": Mock(), "second": Mock(), "third": Mock()}
        with backup:
            sys.modules["first"] = Mock()
            del sys.modules["second"]
            sys.modules["fourth"] = Mock()
            changes = list(backup.iter_changes())
    assert changes == [
        (foreign_imports.ChangeKind.MODIFICATION, "first"),
        (foreign_imports.ChangeKind.REMOVAL, "second"),
        (foreign_imports.ChangeKind.ADDITION, "fourth"),
    ]


@pytest.mark.parametrize(
    "name, expected_path, expected_submodules",
    [
        ("foo", PurePosixPath("foo"), ()),
        ("foo::bar", PurePosixPath("foo"), ("bar",)),
        ("foo::bar::baz", PurePosixPath("foo"), ("bar", "baz")),
        ("foo/bar", PurePosixPath("foo/bar"), ()),
        ("foo::bar/", PurePosixPath("foo::bar"), ()),
        ("foo::bar/::bar::baz", PurePosixPath("foo::bar"), ("bar", "baz")),
        ("foo\\bar", PureWindowsPath("foo/bar"), ()),
        ("foo::bar\\", PureWindowsPath("foo::bar"), ()),
        ("foo::bar\\::bar::baz", PureWindowsPath("foo::bar"), ("bar", "baz")),
    ],
)
def test_split_import_name(
    *,
    name: str,
    expected_path: PurePath,
    expected_submodules: t.Tuple[str, ...],
) -> None:
    # pylint: disable=protected-access
    path, submodules = foreign_imports._split_import_name(
        name,
        path_class=type(expected_path),
    )
    assert path == expected_path
    assert submodules == expected_submodules
