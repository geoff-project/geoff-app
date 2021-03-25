#!/usr/bin/env python
"""Functionality to search and load environments."""

import typing as t
from dataclasses import dataclass

from cernml import coi
from gym.envs.registration import EnvSpec

if t.TYPE_CHECKING:
    from pyjapc import PyJapc


class Metadata:
    """Dataclass that reads problem metadata with fallback.

    This ensures that we use the right fallbacks and don't make any typos.
    """

    def __init__(
        self, metadata_holder: t.Union[coi.Problem, t.Type[coi.Problem], EnvSpec]
    ) -> None:
        self._metadata = dict(coi.Problem.metadata)
        if isinstance(metadata_holder, EnvSpec):
            self._metadata.update(metadata_holder.entry_point.metadata)
        else:
            self._metadata.update(metadata_holder.metadata)

    @property
    def needs_japc(self) -> bool:
        return bool(self._metadata["cern.japc"])

    @property
    def machine(self) -> coi.Machine:
        return self._metadata["cern.machine"]

    @property
    def render_modes(self) -> t.Collection[str]:
        return frozenset(self._metadata["render.modes"])


def iter_env_names(
    *,
    machine: t.Optional[coi.Machine] = None,
    superclass: t.Optional[t.Union[type, t.Tuple[type, ...]]] = None,
) -> t.Iterator[str]:
    """Return all environments specific to a given machine and use case."""
    assert machine is None or isinstance(machine, coi.Machine), machine
    for spec in coi.registry.all():
        if machine and Metadata(spec).machine != machine:
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
    if Metadata(spec).needs_japc:
        kwargs["japc"] = make_japc()
    return spec.make(**kwargs)
