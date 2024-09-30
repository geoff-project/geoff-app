#!/usr/bin/env python

# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Import modules and packages by path."""

import collections
import functools
import importlib
import importlib.machinery
import importlib.util
import logging
import sys
import typing as t
from enum import Enum
from pathlib import Path, PurePath
from types import ModuleType, TracebackType

LOG = logging.getLogger(__name__)


class IllegalImport(ImportError):
    """An import modified the environment in a disallowed manner."""


class UselessNamespacePackage(ImportError):
    """The module ultimately imported is a namespace packages.

    Namespace packages may only be imported in order to import one of
    their submodules. The reason is twofold:

    1. This hints at a path confusion, where the user accidentally
       specified a path that does not actually contain any Python code.
       For example they may have given :path:`/path/to/project` instead
       of :path:`/path/to/project/src/package`.

    2. A namespace package on its own doesn't do anything, so this is
       almost certainly never the right thing to do.
    """


class ChangeKind(Enum):
    """Kind of change reported by `BackupModules.report_changes()`."""

    ADDITION = "imported"
    MODIFICATION = "modified"
    REMOVAL = "removed"


class BackupModules:
    """Context manager that keeps a backup of `sys.modules`.

    The backup is restored at the end of the context. If
    `keep_on_success` is passed and True, the backup is restored only if
    the context is exited through an exception.

    This context is reentrant, i.e. it may be used with several nested
    `with` blocks.
    """

    def __init__(self, keep_on_success: bool = False) -> None:
        self._modules_stack: t.List[t.Dict[str, ModuleType]] = []
        self._keep_on_success = keep_on_success

    @property
    def modules(self) -> t.Dict[str, ModuleType]:
        """The current backup of `sys.modules`."""
        return self._modules_stack[-1]

    def __enter__(self) -> "BackupModules":
        self._modules_stack.append(dict(sys.modules))
        return self

    def __exit__(
        self,
        exc_type: t.Optional[t.Type[BaseException]],
        exc_value: t.Optional[BaseException],
        exc_tb: t.Optional[TracebackType],
    ) -> None:
        modules = self._modules_stack.pop()
        if exc_type or not self._keep_on_success:
            sys.modules = modules

    def iter_changes(
        self, new_modules: t.Optional[t.Dict[str, ModuleType]] = None
    ) -> t.Iterator[t.Tuple[ChangeKind, str]]:
        """Return an iterator of all current changes to `sys.modules`.

        If `new_modules` is passed, it should be a dict to use instead
        of `sys.modules`.

        Example:
            >>> with BackupModules():
            ...     sys.modules["mod/1"] = object()
            ...     sys.modules["mod/2"] = object()
            ...     with BackupModules() as backup:
            ...         del sys.modules["mod/1"]
            ...         sys.modules["mod/2"] = object()
            ...         sys.modules["mod/3"] = object()
            ...         for kind, modname in backup.iter_changes():
            ...             print(kind.value, modname)
            removed mod/1
            modified mod/2
            imported mod/3

        Warning:
            This must be called within the context whose changes you
            want to observe, as the changes are lost outside of it:

                >>> with BackupModules() as backup:
                ...     sys.modules["mod/1"] = object()
                >>> for kind, modname in backup.iter_changes():
                ...     print(kind.value, modname)
                Traceback (most recent call last):
                ...
                ValueError: no module backups available
        """
        if not self._modules_stack:
            raise ValueError("no module backups available")
        new_modules = sys.modules if new_modules is None else new_modules
        old_modules = self._modules_stack[-1]
        for name, old_module in old_modules.items():
            new_module = new_modules.get(name, None)
            if new_module is None:
                yield ChangeKind.REMOVAL, name
            elif new_module is not old_module:
                yield ChangeKind.MODIFICATION, name
        for name in set(new_modules).difference(old_modules):
            yield ChangeKind.ADDITION, name


def import_from_path(to_be_imported: str) -> ModuleType:
    """Return the module that is imported from path.

    Warning:
        Importing Python modules and packages executes arbitrary code.
        Do not use this function unless you trust the code that you
        import.

    Args:
        to_be_imported: The file or directory to import. Attach child
            packages and modules with `::`as a delimiter.

    Returns:
        The module that has been imported.

    Raises:
        `IllegalImport`: if the import was not strictly additional. This
            is not a security check, it merely prevents accidental name
            collisions. An import is strictly additional if after the
            import, `sys.modules` contains exactly the same modules as
            before _plus_ zero or more additional ones.

    ..
        >>> # Doctest setup
        >>> patch = getfixture('monkeypatch')
        >>> patch.setattr('importlib.machinery.PathFinder', _MockImporter)

        >>> from unittest.mock import MagicMock
        >>> sys = MagicMock(name='sys', modules={})

        >>> from . import foreign_imports
        >>> patch.setattr(foreign_imports, "sys", sys)
        >>> del foreign_imports, patch, MagicMock

    Examples:
        >>> # Import a single Python file as a module.
        >>> import_from_path("path/to/module.py")
        <module 'module' from 'path/to/module.py'>

        >>> # Import a directory as a package. The directory must
        >>> # contain an __init__.py file.
        >>> import_from_path("path/to/package")
        <module 'package' from 'path/to/package/__init__.py'>

        >>> # Import a package inside a zip or wheel file.
        >>> import_from_path("some_file.zip/internal/path/to/package")
        <module 'package' from 'some_file.zip/internal/path/to/package/__init__.py'>
        >>> import_from_path("my_distribution-1.0.0-py3-none-any.whl/my_module.py")
        <module 'my_module' from 'my_distribution-1.0.0-py3-none-any.whl/my_module.py'>

        >>> # Import a package/module from inside another package. This
        >>> # imports `package`, `package.child` and
        >>> # `package.child.grandchild`.
        >>> import_from_path("path/to/package::child::baby")
        <module 'package.child.baby' from 'path/to/package/child/baby.py'>

        >>> # If your file or directory contains a literal double colon,
        >>> # you can protect it with a trailing forward or backward
        >>> # slash.
        >>> import_from_path("strange::module.py/")
        <module 'strange::module' from './strange::module.py'>
        >>> import_from_path("strange::package/")
        <module 'strange::package' from './strange::package/__init__.py'>
        >>> import_from_path("strange::package/::module")
        <module 'strange::package.module' from './strange::package/module.py'>
    """
    path, child_segments = _split_import_name(to_be_imported, Path)
    spec = _find_root_spec(path)
    with BackupModules(keep_on_success=True) as backup:
        if child_segments:
            LOG.debug("descendant chain: %s", list(child_segments))
        module = functools.reduce(
            _search_and_import_child,
            child_segments,
            _import_module_from_spec(spec),
        )
        if _is_namespace_package(module):
            raise UselessNamespacePackage(
                f"no __init__.py found, please check the path: {to_be_imported}"
            )
        _assert_only_additions(backup)
    return module


P = t.TypeVar("P", bound=PurePath)  # pylint: disable=invalid-name


def _split_import_name(
    path_and_modules: str, path_class: t.Type[P]
) -> t.Tuple[P, t.Tuple[str, ...]]:
    """Extract file path and submodules from an import name."""
    reverse_segments = []
    while True:
        rest, double_colons, module_name = path_and_modules.rpartition("::")
        if not double_colons or "/" in module_name or "\\" in module_name:
            break
        reverse_segments.append(module_name)
        path_and_modules = rest
    return path_class(path_and_modules), tuple(reversed(reverse_segments))


def _find_root_spec(path: Path) -> importlib.machinery.ModuleSpec:
    """Find a spec that tells us how to import from a path.

    Raises:
        ModuleNotFoundError if nothing can be imported from the path.
            This is e.g. the case if `path` points at a non-Python file
            or a directory without `__init__.py`.
    """
    name = path.stem
    search_dir = path.parent
    LOG.info('searching for root package "%s" in path "%s"', name, search_dir)
    spec = importlib.machinery.PathFinder.find_spec(name, path=[str(search_dir)])
    if not spec:
        raise ModuleNotFoundError(path)
    return spec


def _import_module_from_spec(spec: importlib.machinery.ModuleSpec) -> ModuleType:
    """Import a module based on its spec."""
    if spec.name in sys.modules:
        LOG.info("skipping: %s (already imported)", spec.name)
        return sys.modules[spec.name]
    if spec.loader is None:
        # Namespace package. Import it here and check later that the
        # leaf module is a real one. This prevents path confusion like
        # using `/path/to/project` instead of
        # `/path/to/project/src/package`.
        LOG.info("importing: %s (namespace package)", spec.name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        return module
    LOG.info("importing: %s", spec.name)
    if hasattr(spec.loader, "exec_module"):
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    # Before Python 3.10, zipimport.zipimporter does not provide
    # `exec_module()`, only the legacy `load_module()` API. Once
    # we support _only_ Python 3.10+, this will become
    # superfluous.
    return spec.loader.load_module(spec.name)  # pragma: no cover


def _search_and_import_child(parent: ModuleType, child_name: str) -> ModuleType:
    """Search a child module in a parent package and import it."""
    parent_spec = parent.__spec__
    assert parent_spec is not None
    assert not child_name.startswith(".")
    absolute_name = f"{parent_spec.name}.{child_name}"
    paths = parent_spec.submodule_search_locations or []
    LOG.debug("searching descendant %r in %r", absolute_name, paths)
    spec = importlib.machinery.PathFinder.find_spec(absolute_name, paths)
    if spec is None:
        raise ModuleNotFoundError(absolute_name)
    return _import_module_from_spec(spec)


def _is_namespace_package(module: ModuleType) -> bool:
    """Return True if the given module represents a namespace package.

    Examples:
        >>> from importlib.util import module_from_spec
        >>> from importlib.machinery import ModuleSpec
        >>> _is_namespace_package(__import__("cernml"))
        True
        >>> _is_namespace_package(__import__("importlib"))
        False
        >>> _is_namespace_package(__import__("sys"))
        False
    """
    # For namespace packages, __file__ isn't set or is set to None.
    # We also need to check __path__ because built-in modules don't have
    # __file__ set either.
    return hasattr(module, "__path__") and getattr(module, "__file__", None) is None


def _assert_only_additions(backup: BackupModules) -> None:
    """Assert that an import has been strictly additional.

    This should be called at the end of the context managed by *backup*.

    Example:
        >>> modules = sys.modules.copy()
        >>> patch = getfixture("monkeypatch")
        >>> patch.setattr(sys, 'modules', modules)
        >>> with BackupModules() as backup:
        ...     sys.modules.clear()
        ...     _assert_only_additions(backup)
        Traceback (most recent call last):
        ...
        IllegalImport: ...
    """
    changes: t.Dict[ChangeKind, t.List[str]] = collections.defaultdict(list)
    for kind, name in backup.iter_changes():
        changes[kind].append(name)
    # First remove additions, then check if there are any other changes.
    additions = changes.pop(ChangeKind.ADDITION, [])
    if changes:
        raise IllegalImport(
            ", ".join(
                f"{kind.value} modules: {names}" for kind, names in changes.items()
            )
        )
    LOG.info("imported modules:")
    for name in additions:
        LOG.info("    %s", name)


class _MockImporter(
    importlib.abc.MetaPathFinder, importlib.abc.Loader
):  # pragma: no cover
    """Mock meta path finder+loader for `import_from_path()` doctest."""

    def __repr__(self) -> str:
        return self.__class__.__name__ + "()"

    @classmethod
    def find_spec(
        cls,
        name: str,
        path: t.Optional[t.Sequence[str]],
        target: t.Optional[ModuleType] = None,
    ) -> importlib.machinery.ModuleSpec:
        LOG.debug("mocking import of %r from %r", name, target)
        assert path is not None
        [dirpath] = path
        del path
        fullname, name = name, name.rpartition(".")[2]
        if "." not in fullname:
            LOG.debug("mocking top-level import, clearing sys.modules")
            assert not isinstance(sys, ModuleType), "expected sys to be mocked"
            sys.modules.clear()
        is_package = any(map(name.endswith, ["package", "child"]))
        dirpath = f"{dirpath}/{name}"
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=cls(),
            origin=f"{dirpath}/__init__.py" if is_package else f"{dirpath}.py",
        )
        spec.has_location = True
        spec.submodule_search_locations = [dirpath] if is_package else None
        LOG.debug("mock: %s", spec)
        return spec

    @classmethod
    def create_module(
        cls,
        spec: importlib.machinery.ModuleSpec,  # noqa: ARG003
    ) -> None:
        return None

    @classmethod
    def exec_module(cls, module: ModuleType) -> None:
        pass


def _main(argv: t.Sequence[str]) -> None:  # pragma: no cover
    """Main function if the module is executed on its own."""
    logging.basicConfig(level=logging.INFO)
    for arg in argv[1:]:
        import_from_path(arg)


if __name__ == "__main__":
    _main(sys.argv)
