# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Locate distributions that provide a certain type."""
import inspect
import sys
import typing as t
from dataclasses import dataclass
from pathlib import Path

if sys.version_info < (3, 8):
    import importlib_metadata as metadata
else:
    from importlib import metadata


@dataclass(frozen=True)
class DistInfo:
    """Name and version of a distribution."""

    name: str
    version: str

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


def find_distribution(class_: type) -> t.Optional[DistInfo]:
    """Find the distribution that provides a class.

    This uses `importlib_metadata`, hence only can find distributions
    that have been installed.
    """
    file_path = get_file_path(class_)
    if file_path:
        for dist in metadata.distributions():
            if dist_provides(dist, file_path):
                return DistInfo(dist.metadata["name"], dist.metadata["version"])
    return None


def dist_provides(dist: metadata.Distribution, file_path: Path) -> bool:
    """Return True if `dist` provides the given file.

    This works even if `dist` is installed as a zip file.
    """
    install_dir = get_install_dir(dist)
    try:
        relative_path = file_path.relative_to(install_dir)
    except ValueError:
        # The paths are not relative to each other.
        return False
    if dist.files is None:
        # This may happen if the distribution, for whatever reason,
        # doesn't specify its files.
        return False
    return relative_path in dist.files


def get_install_dir(dist: metadata.Distribution) -> Path:
    """Return the directory in which a distribution has been installed."""
    # `locate_file()` joins the installation path of the distribution
    # with a relative file inside the distribution. If the second part
    # is empty, we get just the first path.
    install_dir = dist.locate_file("")
    # If the distribution is compressed, `install_dir` may be a
    # `zipp.Path`, e.g. `/path/do/dist.zip` instead of a `pathlib.Path`.
    # In that case, we need to convert via `str()`.
    if not isinstance(install_dir, Path):
        return Path(str(install_dir))
    return install_dir


def get_file_path(class_: type) -> t.Optional[Path]:
    """Get the path of the file that defines a class.

    This returns `None` if no file can be aassociated with the type.
    This happens for built-in types and those defined on the interactive
    interpreter.
    """
    # If the module is compressed, this is a path _into_ the archive
    # file, e.g. `/path/to/dist.zip/inside/the/archive.py`.
    try:
        file_path = inspect.getfile(class_)
    except (OSError, TypeError):
        return None
    return Path(file_path)
