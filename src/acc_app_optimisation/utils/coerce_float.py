# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Simple helper functions to deal with NumPy floats."""

import typing as t

Floating = t.TypeVar("Floating", bound=t.SupportsFloat)


def coerce_float_tuple(collection: t.Collection[Floating]) -> t.Tuple[float, ...]:
    """Coerce a collection of floating-point values to a tuple of floats."""
    return tuple(coerce_float(num) for num in collection)


def coerce_float(number: t.SupportsFloat) -> float:
    """Turn float-like numbers into floats.

    This coerces all subclasses of `numpy.floating`, `float`, `int` and
    `fractions.Fraction` into `Float`. It uses `object.__float__()` but
    avoids the `float()` built-in function, thus rejects e.g. `str`.

    Examples:

        >>> type(coerce_float(1))
        <type float>
        >>> type(coerce_float(1.0))
        <type float>
        >>> import numpy as np
        >>> type(coerce_float(np.single(1.0)))
        <type float>
        >>> from fractions import Fraction
        >>> type(coerce_float(Fraction(22, 7)))
        <type float>
        >>> type(coerce_float('1.0'))
        Traceback (most recent call last):
        ...
        AttributeError:
    """
    # `float()` accepts strings even though they don't have a
    # `__float__()` method. We don't want to accept strings, so we use
    # the latter.
    type_ = type(number)
    try:
        return type_.__float__(number)  # pylint: disable=unnecessary-dunder-call
    except TypeError:
        raise AttributeError(
            f"type object {type.__name__!r} has no attribute {'__float__'!r}"
        ) from None
