#!/usr/bin/env python3
"""Setup script for this package."""

from pathlib import Path
from setuptools import setup, find_packages

THISDIR: Path = Path(__file__).parent.resolve()


def get_long_description() -> str:
    """Read the README into a string."""
    with (THISDIR / "README.md").open("rt") as infile:
        return infile.read().strip()


def strip_quotes(string: str) -> str:
    """Check if a string is surrounded by consistent quotes."""
    is_quoted = string[0] == string[-1] in ('"', "'")
    if not is_quoted:
        raise ValueError(f"not a string: {string}")
    return string[1:-1]


def get_version() -> str:
    """Read the version number from the repository."""
    version = None
    path = THISDIR / "acc_app_optimisation/" / "__init__.py"
    with path.open() as infile:
        for line in infile:
            before, equals, after = line.partition("=")
            if equals and before.strip() == "__version__":
                version = strip_quotes(after.strip())
    if not version:
        raise ValueError(f"no version found in {infile.name}")
    return version


setup(
    name="acc-app-optimisation",
    version=get_version(),
    python_requires=">=3.6",
    packages=find_packages(),
    install_requires=[
        "Py-BOBYQA ~= 1.2",
        "PyQt5 ~= 5.12",
        "accwidgets ~= 0.4",
        "cern-awake-env ~= 0.12.1",
        "cernml-coi ~= 0.3.2",
        "gym ~= 0.17.3",
        "numpy ~= 1.17",
        "pjlsa ~= 0.2.0",
        "pyjapc ~=  2.0",
        "pyqtgraph ~= 0.10.0",
        "qt-lsa-selector ~= 0.1.0.dev0",
        "scipy ~= 1.3",
    ],
    extras_require={
        "test": [],
    },
    zip_safe=True,
    author="Verena Kain",
    author_email="verena@kain@cern.ch",
    url="https://gitlab.cern.ch/vkain/acc-app-optimisation",
    description="GUI for generic numerical optimisation",
    long_description=get_long_description(),
    license="Other/Proprietary License",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: Other/Proprietary License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Physics",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
