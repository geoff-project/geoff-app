#!/usr/bin/env python
"""Provided the `Bounded` named tuple."""

from typing import Generic, Iterator, Tuple, TypeVar

from numpy import ndarray

T = TypeVar("T")  # pylint: disable=invalid-name


class Bounded(Generic[T]):
    """A named 3-tuple with a nominal value, upper and lower bounds.

    This supports tuple unpacking:

        >>> c: BoundedCurve[str]
        >>> c = BoundedCurve(values='V', lower='L', upper='U')
        >>> v, l, u = c
        >>> v, l, u
        ('V', 'L', 'U')
    """

    # TODO: Turn into a namedtuple in Python 3.7.
    # pylint: disable = too-few-public-methods
    values: T
    lower: T
    upper: T

    def __init__(self, values: T, lower: T, upper: T) -> None:
        self.values = values
        self.lower = lower
        self.upper = upper

    def __repr__(self) -> str:
        return "{name}(values={values!r}, lower={lower!r}, upper={upper!r})".format(
            name=type(self).__name__,
            values=self.values,
            lower=self.lower,
            upper=self.upper,
        )

    def __iter__(self) -> Iterator[T]:
        return iter(self._as_tuple())

    def _as_tuple(self) -> Tuple[T, T, T]:
        """Return the values as a tuple; order: values, lower, upper."""
        return (self.values, self.lower, self.upper)


class BoundedArray(Bounded[ndarray]):  # pylint: disable = too-few-public-methods
    """Non-genegic subclass of `Bounded`.

    In contrast to `Bounded`, this class can be transmitted via PyQt
    signals.
    """
