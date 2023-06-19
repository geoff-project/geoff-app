# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Functionality to search and load environments."""

import typing as t

from cernml import coi
from gym.envs.registration import EnvSpec

if t.TYPE_CHECKING:
    # pylint: disable = ungrouped-imports, unused-import, import-error
    from cernml.coi import cancellation
    from pyjapc import PyJapc


BUILTIN_ENVS = [
    "cern_awake_env.machine",
    "cern_awake_env.simulation",
    "cern_isolde_offline_env",
    "cern_leir_transfer_line_env",
    "cern_sps_splitter_opt_env",
    "cern_sps_tune_env",
    "cern_sps_zs_alignment_env",
    "linac3_lebt_tuning",
    "psb_extr_and_recomb_optim.optimizer",
    "sps_blowup",
]


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
    def cancellable(self) -> bool:
        return bool(self._metadata["cern.cancellable"])

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


def make_env_by_name(
    name: str,
    make_japc: t.Callable[[], "PyJapc"],
    token: "cancellation.Token",
) -> coi.Problem:
    """Instantiate the environment with the given name.

    Args:
        name: The name to look up in the COI registry.
        make_japc: A factory function that is called if (and only if)
            the environment requires JAPC access. It is called without
            arguments and should return a `PyJapc` object, or raise an
            exception on error.
        token: A cancellation token to pass to the environment if it is
            cancellable. If it isn't cancellable, the token is ignored.

    Returns:
        The instantiated COI problem. Unlike when using `coi.make()`,
        the problem is never wrapped in a `TimeLimit`.
    """
    spec = coi.spec(name)
    metadata = Metadata(spec)
    kwargs: t.Dict[str, t.Any] = {}
    if metadata.needs_japc:
        kwargs["japc"] = make_japc()
    if metadata.cancellable:
        kwargs["cancellation_token"] = token
    return spec.make(**kwargs)
