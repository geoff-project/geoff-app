# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Hooks into the cernml-coi-utils to modify LSA trims globally."""

from __future__ import annotations

import dataclasses
import functools
import sys
import typing as t
from pathlib import Path
import gymnasium as gym
from cernml import coi, lsa_utils

from .distlocate import DistInfo, find_distribution, get_file_path

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class BadStateTransition(Exception):
    """A nonsensical state transition was requested."""


@dataclasses.dataclass(frozen=True)
class ProblemInfo:
    """Description of the problem that the user currently uses.

    This type mostly exists for string formatting. An important property
    is that the default instance produces the empty string:

        >>> str(ProblemInfo())
        ''

    Attributes:
        name: The registered name of the optimization problem.
        source: The :term:`distribution package` or module path from
            which the problem was loaded.
    """

    name: str = ""
    source: t.Optional[t.Union[DistInfo, Path]] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        source = find_source(self.name) if self.name else None
        super().__setattr__("source", source)

    def __str__(self) -> str:
        return f"{self.name} from {self.source}" if self.source else str(self.name)


@dataclasses.dataclass(frozen=True)
class LimitedInt:
    """Wrapper around an integer that may have a limit.

    This is used to implement the number of steps per numerical
    optimization, steps per RL episode, and RL episodes per training or
    execution run.

    If a maximum is not known, *max* should be `None`.

    Note that step and episode indices are one-based. A *value* of zero
    is invalid on purpose.
    """

    value: int
    max: t.Optional[int] = None

    def __str__(self) -> str:
        return f"{self.value}/{self.max}" if self.max is not None else str(self.value)

    def incremented(self) -> Self:
        """Return an instance with :samp:`{value} + 1`."""
        return dataclasses.replace(self, value=self.value + 1)


@dataclasses.dataclass(frozen=True)
class State:
    """State object that describes the context in which a trim happens.

    The main purpose is to carry metadata through the lifecycle and
    provide user-friendly string formatting.

    .. currentmodule:: cernml.coi

    This type roughtly describes the typical lifecycle of a `Problem`
    instance. At the moment, it covers three different classes:
    `SingleOptimizable`, `FunctionOptimizable` and `~gym.Env`.

    Don't instantiate this class directly. Use one of the subclasses
    instead.
    """

    def __str__(self) -> str:
        return f"{self.name}{self._cycle_time_suffix}"

    @property
    def name(self) -> str:
        """A user-friendly form of the state class.

        The default simply lower-cases the class name. Override this
        property if the name contains internal capital letters.
        """
        return type(self).__name__.lower()

    @property
    def _cycle_time_suffix(self) -> str:
        time: t.Optional[float] = getattr(self, "cycle_time", None)
        return "" if time is None else f", t={time:.1g}ms"

    @property
    def indicates_transient_trims(self) -> bool:
        """True if trims in this state are considered transient.

        Override this property to return False if appropriate.
        """
        return True


@dataclasses.dataclass(frozen=True)
class Constructing(State):
    """The problem is running its initializer."""


@dataclasses.dataclass(frozen=True)
class Configuring(State):
    """The problem is applying a config change."""


@dataclasses.dataclass(frozen=True)
class StartingOptimization(State):
    """The problem is fetching the initial state.

    .. currentmodule:: cernml.coi

    For `SingleOptimizable`, this corresponds to running the
    `~SingleOptimizable.get_initial_params()` method.

    For `FunctionOptimizable`, this corresponds to *each* call
    to `~FunctionOptimizable.get_initial_params()`. Set *cycle_time* in
    this case.

    For `gym.Env`, see `StartingEpisode` instead.
    """

    cycle_time: t.Optional[float] = None

    @property
    def name(self) -> str:
        return "starting optimization"


@dataclasses.dataclass(frozen=True)
class StartingEpisode(State):
    """The problem is fetching the initial state.

    For `gym.Env`, this corresponds to the `~gym.Env.reset()` call. For
    other problems, see `StartingOptimization` instead.

    The *episode* is the one-based episode index, with a maximum set if
    the number of episodes is limited.

    The *max_step_per_episode* and *total_step* are only used to carry
    metadata between episodes. They do not appear in the string
    representation.
    """

    episode: LimitedInt
    max_step_per_episode: t.Optional[int] = None
    total_step: t.Optional[LimitedInt] = None

    @property
    def name(self) -> str:
        return "starting episode"

    def __str__(self) -> str:
        return f"{self.name} {self.episode}{self._cycle_time_suffix}"


@dataclasses.dataclass(frozen=True)
class Optimizing(State):
    """The problem is running through the optimization process.

    This is used during `~SingleOptimizable.compute_single_objective()`,
    `~FunctionOptimizable.compute_function_objective()` and
    `~gym.Env.step()`

    This is *not* for RL training. See `RlTraining` in that case
    instead.

    The *step* is the one-based index of this function evaluation.
    For `FunctionOptimizable`, it is relative to the current
    *cycle_time*. For `gym.Env`, it is relative to the current *episode*.

    The *episode* is the one-based episode index during RL optimization.
    During optimization, the number of episodes is typically limited, so
    the maximum should be set. For numerical optimization, this should
    be `None`.

    The *total_step* is the one-based step index across all skeleton
    points (for `FunctionOptimizable`) or across all episodes (for
    `~gym.Env`). It should only be limited if the total number of steps
    is restricted. There is no point in setting its limit to
    ``{number_of_episodes}*step.max``. For `SingleOptimizable`, it is
    `None`.

    The *cycle_time* is the current skeleton point. For
    `SingleOptimizable` and `~gym.Env`, this should be `None`.
    """

    step: LimitedInt
    episode: t.Optional[LimitedInt] = None
    total_step: t.Optional[LimitedInt] = None
    cycle_time: t.Optional[float] = None

    def __str__(self) -> str:
        return "".join(
            [
                f"episode {self.episode}, " if self.episode is not None else "",
                f"step {self.step}",
                f" ({self.total_step} over-all)" if self.total_step is not None else "",
                self._cycle_time_suffix,
            ]
        )

    def incremented_step(self) -> Self:
        """Increment ``step.value`` and return the new instance."""
        return dataclasses.replace(
            self,
            step=self.step.incremented(),
            total_step=self.total_step and self.total_step.incremented(),
        )

    def finalized(self) -> "FinalStep":
        """Return a `FinalStep` as would follow this state.

        Raises:
            BadStateTransition: if *episode* is not `None`. This is only
                the case during RL optimization, which doesn't have a
                final step.
        """
        # CAREFUL: The step value does not change when we switch to
        # `FinalStep`, as per their docs. If total_step is not None, it
        # increases, however; again, this follows from the `FinalStep`
        # docs.
        new = FinalStep(
            step=self.step,
            total_step=self.total_step and self.total_step.incremented(),
            cycle_time=self.cycle_time,
        )
        if self.episode is not None:
            raise BadStateTransition(f"{self!r} -> {new!r}")
        return new


@dataclasses.dataclass(frozen=True)
class RlTraining(State):
    """The problem is running through RL training.

    This is used for `~gym.Env.step()` when training an agent. In other
    cases, see `Optimizing`.

    The *step* and its maximum are counted per episode. Counting starts
    at 1.

    The *total_step* and its maximum are counted across all episodes and
    don't include resets. Counting starts at 1.

    The *episode* is the one-based episode index, as increased by
    `StartingEpisode`. It should not be modified during an episode. The
    maximum is usually `None`, but may be set if one is known.
    """

    step: LimitedInt
    total_step: LimitedInt
    episode: LimitedInt

    @property
    def name(self) -> str:
        return "training"

    def __str__(self) -> str:
        return (
            f"{self.name} episode {self.episode}, step {self.step} "
            f"({self.total_step} over-all){self._cycle_time_suffix}"
        )

    def incremented_step(self) -> Self:
        """Return a copy with *step* and *total_step* incremented."""
        return dataclasses.replace(
            self,
            step=self.step.incremented(),
            total_step=self.total_step.incremented(),
        )

    def restarted(self) -> StartingEpisode:
        """Increment *episode* and return a new `StartingEpisode`."""
        return StartingEpisode(
            episode=self.episode.incremented(),
            max_step_per_episode=self.step.max,
            total_step=self.total_step,
        )


@dataclasses.dataclass(frozen=True)
class FinalStep(State):
    """The problem is applying the result of numerical optimization.

    Numerical optimization often looks like this:

    .. code-block:: python

        def objective(x):
            send_settings(x)
            return receive_objective()

        xres = solve(objective, x0)
        send_settings(xres)
        receive_objective()

    You can see that after the optimization problem is solved, the
    objective function is evaluated once more at the estimated
    optimal point. This final evaluation is the state described by
    this object.

    The *step* parameter is the last value of `Optimizing`. Do not
    increase it after the last step. It is counted for the current
    *cycle_time*. Its maximum should be carried through between
    different cycle times.

    The *total_step* parameter is the number of steps across all
    skeleton points. Unlike *step*, it should be incremented for this
    step. For `SingleOptimizable`, this is `None`.

    The *cycle_time* is the current skeleton point. For
    `SingleOptimizable`, this should be `None`.
    """

    step: LimitedInt
    total_step: t.Optional[LimitedInt] = None
    cycle_time: t.Optional[float] = None

    @property
    def name(self) -> str:
        return "finishing"

    def __str__(self) -> str:
        return "".join(
            [
                f"{self.name} after {self.step} steps",
                f" ({self.total_step} over-all)" if self.total_step is not None else "",
                self._cycle_time_suffix,
            ]
        )

    @property
    def indicates_transient_trims(self) -> bool:
        return False


@dataclasses.dataclass(frozen=True)
class Resetting(State):
    """The problem is being set manually to a previous state.

    This is typically used to reset this problem back to *x₀*. The
    *step* parameter may be any index in case a different previous
    state is chosen.

    The *cycle_time* is the current skeleton point. For
    `SingleOptimizable`, this should be `None`.
    """

    original_step: int = 1
    cycle_time: t.Optional[float] = None

    def __str__(self) -> str:
        return f"{self.name} to step {self.original_step}{self._cycle_time_suffix}"

    @property
    def indicates_transient_trims(self) -> bool:
        return False


@dataclasses.dataclass(frozen=True)
class Closing(State):
    """The problem is being shut down.

    This refers to the `Problem.close()` method.
    """


class GeoffHooks(lsa_utils.Hooks):
    """Hooks for the LSA utilities used by this program.

    There should be only one instance of this type, installed globally
    during program startup. Call the :samp:`update_{*}()` methods
    whenever something about the optimization problem changes.

    Args:
        app_name: The application name, put in every trim description.
        app_version: The application version, put in every trim
            description.

    Attributes:
        app_info: Combination of the arguments.
        problem: The name and source of the optimization problem
            currently loaded. If nothing is loaded, ``problem.name`` is
            the empty string.
        problem_state: `State` object describing the phase of the lifecycle
            of the optimization problem. Also contains e.g. iteration
            index of the optimization procedure. `None` if nothing is
            being optimized at the moment. This may hypothetically have
            a value even if ``problem.name`` is empty.
    """

    def __init__(self, app_name: str, app_version: str) -> None:
        super().__init__()
        self.app_info = DistInfo(app_name, app_version)
        self.problem = ProblemInfo()
        self.problem_state: t.Optional[State] = None

    def update_problem(self, name: str) -> None:
        """Pick a new optimization problem and reset the state.

        The *name* is the key passed to `cernml.coi.make()`. Calling
        this function also resets all other state variables. If no
        problem at all is loaded, pass the empty string.
        """
        self.update_problem_state(None, problem=name)

    def update_problem_state(
        self,
        state: t.Optional[State],
        *,
        problem: t.Optional[str] = None,
    ) -> None:
        """Change the state of the current optimization problem.

        If it possible for multiple problems to exist concurrently (e.g.
        one loaded in the numerical-optimization tab, one loaded in the
        RL training tab), you should also pass *problem* as the name of
        the problem you refer to. This ensures that the metadata
        injected into trim descriptions is coherent. If *problem* is
        already the current problem of this object, it is not updated.
        """
        if problem is not None and problem != self.problem.name:
            self.problem = ProblemInfo(problem)
        self.problem_state = state

    def _format_extra_info(self) -> str:
        parts = [
            self.problem_state,
            self.problem,
            self.app_info and f"part of {self.app_info}",
        ]
        # Exclude None and empty strings.
        return ", ".join(str(part) for part in parts if part)

    def trim_description(self, desc: t.Optional[str]) -> str:
        extra_info = self._format_extra_info()
        prefix = desc if desc is not None else super().trim_description(desc)
        if prefix and extra_info:
            return f"{prefix}; {extra_info}"
        return prefix or extra_info

    def trim_transient(self, transient: t.Optional[bool]) -> bool:
        if transient is None and self.problem_state:
            return self.problem_state.indicates_transient_trims
        return super().trim_transient(transient)


@functools.cache
def find_source(problem_name: str) -> t.Optional[t.Union[DistInfo, Path]]:
    """Find the source of an optimization problem or return `None`.

    If the problem comes from an installed package, its name and version
    are returned. If it comes from a dynamically loaded module, the
    module's file path is returned.

    Since this function does considerable amounts of linear searching,
    it caches all results. So looking up the same problem name twice
    will only search it once.
    """
    try:
        spec = coi.spec(problem_name)
    except gym.error.Error:
        return None  # Name wasn't found, should be impossible.
    entry_point = spec.entry_point
    return find_distribution(entry_point) or get_file_path(entry_point) or None
