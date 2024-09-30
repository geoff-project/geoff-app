# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = import-outside-toplevel
# pylint: disable = redefined-outer-name

"""Tests for `acc_app_optimisation.foreign_imports`."""

import sys
import typing as t
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from types import ModuleType
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from acc_app_optimisation import foreign_imports


@dataclass
class FakePackage:
    name: str
    needle: str
    path: Path


@pytest.fixture
def sys_modules(mocker: MockerFixture) -> t.Iterator[t.Dict[str, str]]:
    yield mocker.patch("sys.modules", {})


@pytest.fixture
def fake_module(tmp_path: Path) -> t.Iterator[FakePackage]:
    name = "module"
    needle = str(Mock)
    path = tmp_path / f"{name}.py"
    with path.open("w") as outfile:
        outfile.write(f"needle = {repr(needle)}")
    yield FakePackage(name, needle, path)


@pytest.fixture
def fake_package(tmp_path: Path) -> t.Iterator[FakePackage]:
    name = "package"
    needle = str(Mock(name="fake_package"))
    path = tmp_path / name
    path.mkdir()
    with (path / "__init__.py").open("w") as outfile:
        outfile.write(f"needle = {repr(needle)}")
    yield FakePackage(name, needle, path)


@pytest.fixture
def fake_big_package(tmp_path: Path) -> t.Iterator[FakePackage]:
    name = "package"
    needle = str(Mock(name="fake_big_package"))
    path = tmp_path / name
    path.mkdir()
    (path / "__init__.py").touch()
    with (path / "first.py").open("w") as outfile:
        outfile.write(f"needle = {repr(needle)}")
    with (path / "second.py").open("w") as outfile:
        outfile.write("from . import first")
    yield FakePackage(name, needle, path)


@pytest.fixture
def fake_namespace_package(tmp_path: Path) -> t.Iterator[FakePackage]:
    name = "package"
    needle = str(Mock(name="fake_namespace_package"))
    path = tmp_path / name
    path.mkdir()
    with (path / "first.py").open("w") as outfile:
        outfile.write(f"needle = {repr(needle)}")
    with (path / "second.py").open("w") as outfile:
        outfile.write("from . import first")
    yield FakePackage(name, needle, path)


def test_import_module(
    sys_modules: t.Dict[str, ModuleType], fake_module: FakePackage
) -> None:
    module: t.Any = foreign_imports.import_from_path(str(fake_module.path))
    assert module.needle == fake_module.needle
    assert module.__name__ == fake_module.name
    assert module.__package__ == ""
    assert fake_module.name in sys_modules


def test_double_import(
    sys_modules: t.Dict[str, ModuleType], fake_module: FakePackage
) -> None:
    first: t.Any = foreign_imports.import_from_path(str(fake_module.path))
    second: t.Any = foreign_imports.import_from_path(str(fake_module.path))
    assert first is second


def test_import_package(
    sys_modules: t.Dict[str, ModuleType], fake_package: FakePackage
) -> None:
    module: t.Any = foreign_imports.import_from_path(str(fake_package.path))
    assert module.needle == fake_package.needle
    assert module.__name__ == fake_package.name
    assert module.__package__ == fake_package.name
    assert fake_package.name in sys_modules


def test_import_submodule(
    sys_modules: t.Dict[str, ModuleType], fake_big_package: FakePackage
) -> None:
    module: t.Any = foreign_imports.import_from_path(
        str(fake_big_package.path) + "::second"
    )
    assert module.first.needle == fake_big_package.needle
    assert module.first.__name__ == f"{fake_big_package.name}.first"
    assert module.first.__package__ == fake_big_package.name
    assert module.__name__ == f"{fake_big_package.name}.second"
    assert module.__package__ == fake_big_package.name
    assert fake_big_package.name in sys_modules
    assert f"{fake_big_package.name}.first" in sys_modules
    assert f"{fake_big_package.name}.second" in sys_modules


def test_import_in_namespace_package(
    sys_modules: t.Dict[str, ModuleType], fake_namespace_package: FakePackage
) -> None:
    sys_modules["sys"] = sys
    module: t.Any = foreign_imports.import_from_path(
        str(fake_namespace_package.path) + "::second"
    )
    assert module.first.needle == fake_namespace_package.needle
    assert module.first.__name__ == f"{fake_namespace_package.name}.first"
    assert module.first.__package__ == fake_namespace_package.name
    assert module.__name__ == f"{fake_namespace_package.name}.second"
    assert module.__package__ == fake_namespace_package.name
    assert fake_namespace_package.name in sys_modules
    assert f"{fake_namespace_package.name}.first" in sys_modules
    assert f"{fake_namespace_package.name}.second" in sys_modules
    namespace = sys_modules[fake_namespace_package.name]
    assert namespace.__spec__ is not None
    assert not namespace.__spec__.has_location


def test_import_bare_namespace_package(
    sys_modules: t.Dict[str, ModuleType], fake_namespace_package: FakePackage
) -> None:
    sys_modules["sys"] = sys
    with pytest.raises(foreign_imports.UselessNamespacePackage):
        foreign_imports.import_from_path(str(fake_namespace_package.path))


def test_backup_stack(sys_modules: t.Dict[str, ModuleType]) -> None:
    outer = {"outer": Mock()}
    sys_modules.update(outer)
    backup_stack = foreign_imports.BackupModules()
    # Stack: []
    with pytest.raises(IndexError):
        _ = backup_stack.modules
    with backup_stack:
        inner = {"inner": Mock()}
        sys_modules.clear()
        sys_modules.update(inner)
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


def test_backup_keep_on_success(sys_modules: t.Dict[str, ModuleType]) -> None:
    backup_stack = foreign_imports.BackupModules(keep_on_success=True)
    # On failure, sys.modules is restored.
    outer = {"outer": Mock()}
    sys_modules.update(outer)
    with pytest.raises(ValueError):
        with backup_stack:
            sys.modules.clear()
            raise ValueError()
    assert sys.modules == outer
    # On success, it remains at inner, but backup_stack still pop its
    # stack.
    with backup_stack:
        sys.modules.update(inner=Mock())
        inner = sys.modules.copy()
    assert sys.modules == inner
    with pytest.raises(IndexError):
        _ = backup_stack.modules


def test_report_modification(sys_modules: t.Dict[str, ModuleType]) -> None:
    with foreign_imports.BackupModules() as backup:
        sys_modules.update(first=Mock(), second=Mock(), third=Mock())
        with backup:
            sys_modules["first"] = Mock()
            del sys_modules["second"]
            sys_modules["fourth"] = Mock()
            changes = list(backup.iter_changes())
    assert changes == [
        (foreign_imports.ChangeKind.MODIFICATION, "first"),
        (foreign_imports.ChangeKind.REMOVAL, "second"),
        (foreign_imports.ChangeKind.ADDITION, "fourth"),
    ]


def test_root_module_not_found(
    sys_modules: t.Dict[str, ModuleType], fake_module: FakePackage
) -> None:
    with pytest.raises(ModuleNotFoundError, match="none\\.py$"):
        foreign_imports.import_from_path(str(fake_module.path / "none.py"))


def test_child_module_not_found(
    sys_modules: t.Dict[str, ModuleType], fake_module: FakePackage
) -> None:
    with pytest.raises(ModuleNotFoundError, match="^module.child$"):
        foreign_imports.import_from_path(str(fake_module.path) + "::child")


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
