#!/usr/bin/env python
"""Provided the `Bounded` dataclass."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from numpy import ndarray

T = TypeVar("T")  # pylint: disable=invalid-name


@dataclass(frozen=True)
class Bounded(Generic[T]):
    """A dataclass with a nominal value, upper and lower bounds.


    Usage:

        >>> c: Bounded[str]
        >>> c = Bounded(values='V', lower='L', upper='U')
        >>> c.values, c.lower, c.upper
        ('V', 'L', 'U')
    """

    values: T
    lower: T
    upper: T


class BoundedArray(Bounded[ndarray]):  # pylint: disable = too-few-public-methods
    """Non-generic subclass of `Bounded`.

    In contrast to `Bounded`, this class can be transmitted via PyQt
    signals.
    """
