# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Utility functions to understand types and value ranges."""

import typing as t

import numpy as np


def str_boolsafe(value: t.Any) -> str:
    """Like :py:func:`str()` but with special cases.

    Certain types round-trip exactly or approximately through
    :py:func:`str()`:

        >>> int(str(3))
        3
        >>> float(str(1.0))
        1.0

    However, this is not true for :py:func:`bool`. The function *almost*
    works, but is subtly wrong:

        >>> bool(str(True))
        True
        >>> bool(str(False))
        True

    This function makes a special case for booleans and returns either
    ``"checked"`` or ``""`` (the empty string). For all other types, it
    simply returns ``str(value)``.
    """
    if is_bool(value):
        return "checked" if value else ""
    return str(value)


def guess_decimals(low: float, high: float) -> int:
    """Guess how many decimals to show in a double spin box."""
    absmax = max(abs(high), abs(low))
    absmin = min(abs(high), abs(low))
    mindigits = np.ceil(-np.log10(absmin)) if absmin else 0
    maxdigits = np.ceil(-np.log10(absmax)) if absmax else 0
    return 1 + int(max(2, maxdigits, mindigits))


def is_range_huge(low: float, high: float) -> bool:
    """Return True if the range covers several orders of magnitude."""
    absmax = max(abs(high), abs(low))
    absmin = min(abs(high), abs(low))
    if absmin == 0.0:
        absmax, absmin = (absmax, 1.0) if absmax > 1.0 else (1.0, absmax)
    return absmax / absmin > 1e3


def is_int(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy int."""
    return isinstance(value, (int, np.integer))


def is_float(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy float."""
    return isinstance(value, (float, np.floating))


def is_bool(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy bool."""
    return isinstance(value, (bool, np.bool_))
