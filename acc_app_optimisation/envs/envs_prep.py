import typing as t

import cern_awake_env.simulation
import cern_awake_env.machine

from cernml import coi
from pyjapc import PyJapc


def get_env_names_by_machine(machine: coi.Machine) -> t.List[str]:
    assert isinstance(machine, coi.Machine), machine
    return [spec.id for spec in coi.registry.all() if _get_machine(spec) == machine]


def make_env_by_name(name: str, japc: PyJapc) -> coi.Problem:
    spec = coi.registry.spec(name)
    needs_japc = spec.entry_point.metadata.get("cern.japc", False)
    if needs_japc:
        return coi.make(name, japc=japc)
    return coi.make(name)


def _get_machine(spec) -> coi.Machine:
    metadata = spec.entry_point.metadata
    machine = metadata.get("cern.machine", coi.Machine.NoMachine)
    return machine
