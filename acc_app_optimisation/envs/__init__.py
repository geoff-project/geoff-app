#!/usr/bin/env python
"""Functionality to search and load environments."""

import typing as t

from cernml import coi

if t.TYPE_CHECKING:
    from pyjapc import PyJapc

from . import builtin_envs


def get_env_names_by_machine(machine: coi.Machine) -> t.List[str]:
    """Return all environments specific to a given machine."""
    assert isinstance(machine, coi.Machine), machine
    return [spec.id for spec in coi.registry.all() if _get_machine(spec) == machine]


def make_env_by_name(name: str, make_japc: t.Callable[[], "PyJapc"]) -> coi.Problem:
    """Instantiate the environment with the given name.

    Args:
        name: The name to look up in the COI registry.
        make_japc: A factory function that is called if (and only if)
            the environment requires JAPC access. It is called without
            arguments and should return a `PyJapc` object, or raise an
            exception on error.
    """
    spec = coi.registry.spec(name)
    needs_japc = spec.entry_point.metadata.get("cern.japc", False)
    if needs_japc:
        return coi.make(name, japc=make_japc())
    return coi.make(name)


def _get_machine(spec) -> coi.Machine:
    """Return machine based on an environment registry spec."""
    metadata = spec.entry_point.metadata
    machine = metadata.get("cern.machine", coi.Machine.NoMachine)
    return machine
