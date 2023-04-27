"""Handling of skeleton points for FunctionOptimizable."""

import typing as t

from cernml.coi import FunctionOptimizable
from ...utils.coerce_float import coerce_float_tuple

SkeletonPoints = t.NewType("SkeletonPoints", t.Tuple[float, ...])
"""Helper to ensure we don't forget to call `gather_skeleton_points()`."""

class NoSkeletonPoints(Exception):
    """There are no skeleton points at which to optimize functions."""


def gather_skeleton_points(
    opt: FunctionOptimizable, user_selection: t.Tuple[float, ...]
) -> SkeletonPoints:
    """Unify the skeleton points to use.

    Args:
        opt: The optimization problem. If it defines a method
            `override_skeleton_points()` that doesn't return `None`, the
            return value is assumed to be a list of skeleton points. In
            this case, these are used and *user_selection* is ignored.
        user_selection: The skeleton points chosen by the user in the
            configuration dialog. These are used if *opt* does not
            specify an override, which is the default behavior.

    Returns:
        A newtype wrapper around the tuple of skeleton points. The
        wrapper helps the type checker ensure that the unification has
        not been forgotten.
    """
    override = opt.override_skeleton_points()
    if override is None:
        if not user_selection:
            raise NoSkeletonPoints(
                f"no skeleton points selected and problem did not "
                f"provide its own: {opt.unwrapped}"
            )
        # opt does not override skeleton points, use user-provided ones.
        return SkeletonPoints(user_selection)
    given_points = coerce_float_tuple(override)
    if not given_points:
        raise NoSkeletonPoints(
            f"problem wanted to provide skeleton points, but gave "
            f"zero of them: {opt.unwrapped}"
        )
    # opt overrides skeleton points, ignore user selection.
    return SkeletonPoints(given_points)
