"""Utility functions to understand types and value ranges."""

import typing as t

import numpy as np


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
