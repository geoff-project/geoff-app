#!/usr/bin/env python
"""Import modules and packages by path."""

import collections
import functools
import importlib
import logging
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, TracebackType
from typing import Dict, Iterator, Optional, Tuple, Type

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


def import_from_path(to_be_imported: str) -> ModuleType:
    """Return the module that is imported from path.

    WARNING: Importing Python modules and packages executes arbitrary
    code. Do not use this function unless you trust the code that you
    import.

    Usage:

        >>> # Import a single Python file as a module.
        >>> import_from_path("path/to/module.py")  # doctest: +SKIP

        >>> # Import a directory as a package. The directory must
        >>> # contain an __init__.py file.
        >>> import_from_path("path/to/package")  # doctest: +SKIP

        >>> # Import a package/module from inside another package. This
        >>> # imports `package`, `package.child` and
        >>> # `package.child.grandchild`.
        >>> import_from_path("path/to/package::child::grandchild")  # doctest: +SKIP

        >>> # If your file or directory contains a literal double colon,
        >>> # you can protect it with a trailing forward or backward
        >>> # slash.
        >>> import_from_path("strange::module.py/")  # doctest: +SKIP
        >>> import_from_path("strange::package/")  # doctest: +SKIP
        >>> import_from_path("strange::package/::child_module")  # doctest: +SKIP

    Args:
        path: The file or directory to import. Attach child packages and
            modules with `::`as a delimiter.

    Returns:
        The module that has been imported.

    Raises:
        IllegalImport if the import was not strictly additional. This is
            not a security check, it merely prevents accidental name
            collisions. An import is strictly additional if after the
            import, `sys.modules` contains exactly the same modules as
            before _plus_ zero or more additional ones.
    """
    path, child_segments = _split_import_name(to_be_imported)
    spec = _find_root_spec(path)
    with BackupModules(keep_on_success=True) as backup:
        if child_segments:
            LOG.debug("descendant chain: %s", list(child_segments))
        module = functools.reduce(
            _search_and_import_child,
            child_segments,
            _import_module_from_spec(spec),
        )
        _assert_only_additions(backup)
    return module


def _split_import_name(
    name: str, path_class: Type[Path] = Path
) -> Tuple[Path, Tuple[str]]:
    r"""Extract file path and submodules from an import name.

    Usage:
        >>> from pathlib import PurePosixPath, PureWindowsPath
        >>> split_import_name('foo', path_class=PurePosixPath)
        (PurePosixPath('foo'), ())
        >>> split_import_name('foo::bar', path_class=PurePosixPath)
        (PurePosixPath('foo'), ('bar',))
        >>> split_import_name('foo::bar::baz', path_class=PurePosixPath)
        (PurePosixPath('foo'), ('bar', 'baz'))
        >>> split_import_name('foo/bar', path_class=PurePosixPath)
        (PurePosixPath('foo/bar'), ())
        >>> split_import_name('foo::bar/', path_class=PurePosixPath)
        (PurePosixPath('foo::bar'), ())
        >>> split_import_name('foo::bar/::bar::baz', path_class=PurePosixPath)
        (PurePosixPath('foo::bar'), ('bar', 'baz'))
        >>> split_import_name('foo\\bar', path_class=PureWindowsPath)
        (PureWindowsPath('foo/bar'), ())
        >>> split_import_name('foo::bar\\', path_class=PureWindowsPath)
        (PureWindowsPath('foo::bar'), ())
        >>> split_import_name('foo::bar\\::bar::baz', path_class=PureWindowsPath)
        (PureWindowsPath('foo::bar'), ('bar', 'baz'))
    """
    child_segments = []
    while True:
        before, sep, after = name.rpartition("::")
        if not sep or "/" in after or "\\" in after:
            break
        child_segments.append(after)
        name = before
    child_segments.reverse()
    return path_class(name), tuple(child_segments)


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
    spec = importlib.machinery.PathFinder.find_spec(path.stem, path=[str(search_dir)])
    if not spec:
        raise ModuleNotFoundError(path)
    return spec


def _import_module_from_spec(spec: importlib.machinery.ModuleSpec) -> ModuleType:
    """Import a module based on its spec."""
    if spec.name in sys.modules:
        LOG.info("skipping: %s (already imported)", spec.name)
        module = sys.modules[spec.name]
    else:
        LOG.info("importing: %s", spec.name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


def _search_and_import_child(parent: ModuleType, child_name: str) -> ModuleType:
    """Search a child module in a parent package and import it."""
    # If the name isn't already relative, make it so.
    if not child_name.startswith("."):
        child_name = "." + child_name
    absolute_name = f"{parent.__name__}{child_name}"
    LOG.debug('searching descendant "%s"', absolute_name)
    spec = importlib.util.find_spec(child_name, parent.__name__)
    if not spec:
        raise ModuleNotFoundError(absolute_name)
    return _import_module_from_spec(spec)


def _assert_only_additions(backup: BackupModules) -> None:
    """Assert that an import has been strictly additional."""
    # This produces a dict of the shape:
    # `{ADDITION: […], MODIFICATION: […], REMOVAL: […]}`.
    changes = collections.defaultdict(list)
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


def _main(argv):
    """Main function if the module is executed on its own."""
    logging.basicConfig(level=logging.INFO)
    for arg in argv[1:]:
        import_from_path(arg)


if __name__ == "__main__":
    _main(sys.argv)
