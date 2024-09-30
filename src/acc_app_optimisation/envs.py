# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Functionality to search and load environments."""

import typing as t
from logging import getLogger

from cernml import coi
from gym.envs.registration import EnvSpec

try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata  # type: ignore

if t.TYPE_CHECKING:
    # pylint: disable = ungrouped-imports, unused-import, import-error
    from cernml.coi import cancellation
    from cernml.optimizers import Optimizer
    from pyjapc import PyJapc


LOG = getLogger(__name__)

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


def get_custom_optimizers(spec: EnvSpec) -> t.Mapping[str, "Optimizer"]:
    """Return all custom optimizers provided for the environment.

    This takes all endpoints into account: both the interface on the
    environment itself and entry-points.
    """
    optimizers = {}
    if issubclass(spec.entry_point, coi.CustomOptimizerProvider):
        optimizers.update(spec.entry_point.get_optimizers())
    entry_points = _get_entry_points(group="cernml.custom_optimizers", name=spec.id)
    duplicate_names = set()
    for ep in entry_points:
        provider = ep.load()
        if issubclass(provider, coi.CustomOptimizerProvider):
            next_batch = provider.get_optimizers()
        elif callable(provider):
            next_batch = provider()
        else:
            LOG.warning("cannot retrieve optimizers from loaded entry point: %s", ep)
            continue
        duplicate_names.update(optimizers.keys() & next_batch.keys())
        optimizers.update(next_batch)
    if duplicate_names:
        LOG.warning(
            "duplicate names of custom optimizers loaded for %s: %r",
            spec.id,
            duplicate_names,
        )
    return optimizers


def get_custom_policies(
    spec: EnvSpec,
) -> t.Dict[str, t.Optional[coi.CustomPolicyProvider]]:
    """Return all custom RL policies provided for the environment.

    This takes all endpoints into account: both the interface on the
    environment itself and entry-points.

    The return value is a dict mapping from policy name to the provider
    *instance* it originated from. Given a policy name, you *often* can
    load the policy like this:

        policies[name].load_policy(name)

    However, the dict value may be None if the policy provider is the
    env itself. This is because the env is not instantiated yet at the
    time when this function runs.
    """
    policies = {}
    env_class = spec.entry_point
    if issubclass(env_class, coi.CustomPolicyProvider):
        policies.update(dict.fromkeys(env_class.get_policy_names(), None))
    entry_points = _get_entry_points(group="cernml.custom_policies", name=spec.id)
    duplicate_names = set()
    for ep in entry_points:
        provider_class = ep.load()
        if not callable(provider_class):
            LOG.warning("cernml.custom_policies entry point must be callable: %s", ep)
            continue
        provider = provider_class()
        if not isinstance(provider, coi.CustomPolicyProvider):
            LOG.warning(
                "cernml.custom_policies entry point must be a subclass "
                "of CustomPolicyProvider: %s",
                ep,
            )
            continue
        next_batch = provider.get_policy_names()
        duplicate_names.update(set(policies) & set(next_batch))
        for name in next_batch:
            policies[name] = provider
    if duplicate_names:
        LOG.warning(
            "duplicate names of custom policies loaded for %s: %r",
            spec.id,
            duplicate_names,
        )
    return policies


def _get_entry_points(
    *, group: str, name: str
) -> tuple[importlib_metadata.EntryPoint, ...]:
    """Shim around old versions of `importlib.metadata.entry_points()`."""
    all_entry_points = importlib_metadata.entry_points()
    if hasattr(all_entry_points, "select"):
        return tuple(all_entry_points.select(group=group, name=name))
    # Deprecated API:
    return tuple(ep for ep in all_entry_points.get(group, ()) if ep.name == name)
