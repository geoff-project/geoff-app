#!/usr/bin/env python
"""Import modules and packages by path."""

import importlib
import itertools
import logging
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, TracebackType
from typing import Dict, Iterator, Optional, Tuple

LOG = logging.getLogger(__name__)


class IllegalImport(ImportError):
    """An import modified the environment in a disallowed manner."""


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
        self._modules_stack = []
        self._keep_on_success = keep_on_success

    @property
    def modules(self) -> Dict[str, ModuleType]:
        """The current backup of `sys.modules`."""
        return self._modules_stack[-1]

    def __enter__(self) -> "BackupModules":
        self._modules_stack.append(dict(sys.modules))
        return self

    def __exit__(
        self, exc_type: type, exc_value: Exception, traceback: TracebackType
    ) -> None:
        modules = self._modules_stack.pop()
        if exc_type or not self._keep_on_success:
            sys.modules = modules

    def iter_changes(
        self, new_modules: Optional[Dict[str, ModuleType]] = None
    ) -> Iterator[Tuple[ChangeKind, str]]:
        """Return an iterator of all changes to `sys.modules`.

        If `new_modules` is passed, it should be a dict to use instead
        of `sys.modules`.
        """
        if new_modules is None:
            new_modules = sys.modules
        old_modules = self._modules_stack[-1]
        for name, old_module in old_modules.items():
            new_module = new_modules.get(name, None)
            if new_module is None:
                yield ChangeKind.REMOVAL, name
            if new_module is not old_module:
                yield ChangeKind.MODIFICATION, name
        for name in set(new_modules).difference(old_modules):
            yield ChangeKind.ADDITION, name


def import_from_path(path: Path) -> ModuleType:
    """Return the module that is imported from path.

    WARNING: Importing Python modules and packages executes arbitrary
    code. Do not use this function unless you trust the code that you
    import.

    Args:
        path: The file or directory to import. If `path` points to a
            single Python file, it is imported as a module. If it points
            to a directory, the directory is imported as a package.

    Returns:
        The module that has been imported.

    Raises:
        IllegalImport if the import was not strictly additional. This is
            not a security check, it merely prevents accidental name
            collisions. An import is strictly additional if after the
            import, `sys.modules` contains exactly the same modules as
            before _plus_ zero or more additional ones.
    """
    spec = _find_spec(path)
    module = importlib.util.module_from_spec(spec)
    with BackupModules(keep_on_success=True) as backup:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _assert_only_additions(backup)
    return module


def _find_spec(path: Path) -> importlib.machinery.ModuleSpec:
    """Find a spec that tells us how to import from a path.

    Raises:
        ModuleNotFoundError if nothing can be imported from the path.
            This is e.g. the case if `path` points at a non-Python file
            or a directory without `__init__.py`.
    """
    name = path.stem
    search_dir = path.parent
    LOG.info("Importing package %s from path %s", name, search_dir)
    spec = importlib.machinery.PathFinder.find_spec(path.stem, path=[str(search_dir)])
    if not spec:
        raise ModuleNotFoundError(path)
    return spec


def _assert_only_additions(backup: BackupModules) -> None:
    """Assert that an import has been strictly additional."""
    changes = sorted(backup.iter_changes())
    # This is like `{ADDITION: […], MODIFICATION: […], REMOVAL: […]}`.
    changes = {
        kind: list(names)
        for kind, names in itertools.groupby(changes, key=lambda kind, _name: kind)
    }
    # First remove additions, then check if there are any other changes.
    additions = changes.pop(ChangeKind.ADDITION, [])
    if changes:
        raise IllegalImport(
            ", ".join(
                f"{change_kind.value} modules: {names}"
                for change_kind, names in changes.items()
            )
        )
    LOG.info("Imported modules:")
    for name in additions:
        LOG.info("    %s", name)
