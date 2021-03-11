#!/usr/bin/env python
"""Functionality to search and load environments."""

import typing as t

from cernml import coi
from gym.envs.registration import EnvSpec

if t.TYPE_CHECKING:
    from pyjapc import PyJapc


def iter_env_names(
    *,
    machine: t.Optional[coi.Machine] = None,
    superclass: t.Optional[t.Union[type, t.Tuple[type, ...]]] = None,
) -> t.Iterator[str]:
    """Return all environments specific to a given machine and use case."""
    assert machine is None or isinstance(machine, coi.Machine), machine
    for spec in coi.registry.all():
        if machine and _get_machine(spec) != machine:
            continue
        if superclass and not issubclass(spec.entry_point, superclass):
            continue
        yield spec.id


def make_env_by_name(name: str, make_japc: t.Callable[[], "PyJapc"]) -> coi.Problem:
    """Instantiate the environment with the given name.

    Args:
        name: The name to look up in the COI registry.
        make_japc: A factory function that is called if (and only if)
            the environment requires JAPC access. It is called without
            arguments and should return a `PyJapc` object, or raise an
            exception on error.

    Returns:
        The instantiated COI problem. Unlike when using `coi.make()`,
        the problem is never wrapped in a `TimeLimit`.
    """
    spec = coi.spec(name)
    kwargs: t.Dict[str, t.Any] = {}
    if _get_needs_japc(spec):
        kwargs["japc"] = make_japc()
    return spec.make(**kwargs)


def _get_needs_japc(spec: EnvSpec) -> bool:
    """Return machine based on an environment registry spec."""
    metadata = spec.entry_point.metadata
    return bool(metadata.get("cern.japc", False))


def _get_machine(spec: EnvSpec) -> coi.Machine:
    """Return machine based on an environment registry spec."""
    metadata = spec.entry_point.metadata
    machine = metadata.get("cern.machine", coi.Machine.NoMachine)
    return machine
