#!/usr/bin/env python
"""Utilities that help debug Qt issues."""

from typing import Any, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget

Printer = Callable[[str], Any]


def print_parent_chain(widget: QWidget, printer: Printer = print) -> None:
    """Print a widget and all its parents.

    By default, `print` is used to output the parent chain, but any
    function that accepts a single string may be passed as the
    `printer`.
    """
    depth = 0
    while widget is not None:
        printer(f"{depth*' '}{widget!s}")
        widget = widget.parent()
        depth += 1


def print_window_type(widget: QWidget, printer: Printer = print) -> None:
    """Print all window types and hints of a widget.

    By default, `print` is used to output the parent chain, but any
    function that accepts a single string may be passed as the
    `printer`.
    """
    flags = widget.windowFlags()
    print(f"{widget}: 0x{int(flags):x}")
    for name, value in vars(Qt).items():
        if isinstance(value, Qt.WindowType):
            if flags & value:
                printer(f"    {name}")
