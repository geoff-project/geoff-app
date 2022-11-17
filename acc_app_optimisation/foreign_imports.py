#!/usr/bin/env python
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
        self, exc_type: type, exc_value: Exception, exc_tb: TracebackType
    ) -> None:
        modules = self._modules_stack.pop()
        if exc_type or not self._keep_on_success:
            sys.modules = modules

    def iter_changes(
        self, new_modules: t.Optional[t.Dict[str, ModuleType]] = None
    ) -> t.Iterator[t.Tuple[ChangeKind, str]]:
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

    Usage:

        >>> # Import a single Python file as a module.
        >>> import_from_path("path/to/module.py")

        >>> # Import a directory as a package. The directory must
        >>> # contain an __init__.py file.
        >>> import_from_path("path/to/package")

        >>> # Import a package inside a zip or wheel file.
        >>> import_from_path("some_file.zip/internal/path/to/package")
        >>> import_from_path("my_distribution-1.0.0-py3-none-any.whl/my_module.py")

        >>> # Import a package/module from inside another package. This
        >>> # imports `package`, `package.child` and
        >>> # `package.child.grandchild`.
        >>> import_from_path("path/to/package::child::grandchild")

        >>> # If your file or directory contains a literal double colon,
        >>> # you can protect it with a trailing forward or backward
        >>> # slash.
        >>> import_from_path("strange::module.py/")
        >>> import_from_path("strange::package/")
        >>> import_from_path("strange::package/::child_module")
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
    name: str, path_class: t.Type[P]
) -> t.Tuple[P, t.Tuple[str, ...]]:
    """Extract file path and submodules from an import name."""
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
        spec.loader.exec_module(module)  # type: ignore
        return module
    # Before Python 3.10, zipimport.zipimporter does not provide
    # `exec_module()`, only the legacy `load_module()` API. Once
    # we support _only_ Python 3.10+, this will become
    # superfluous.
    return spec.loader.load_module(spec.name)


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


def _is_namespace_package(module: ModuleType) -> bool:
    """Return True if the given module represents a namespace package.

    Examples:

        >>> from importlib.util import module_from_spec
        >>> from importlib.machinery import ModuleSpec
        >>> ns_spec = ModuleSpec("nspkg", None, is_package=True)
        >>> _is_namespace_package(module_from_spec(ns_spec))
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


def _main(argv: t.Sequence[str]) -> None:
    """Main function if the module is executed on its own."""
    logging.basicConfig(level=logging.INFO)
    for arg in argv[1:]:
        import_from_path(arg)


if __name__ == "__main__":
    _main(sys.argv)
