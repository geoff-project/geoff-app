# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Utilities that help debug Qt issues."""

import typing as t

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QWidget

Printer = t.Callable[[str], t.Any]


def print_parent_chain(widget: QObject, printer: Printer = print) -> None:
    """Print a QObject and all its parents.

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
            if flags & value:  # type: ignore
                printer(f"    {name}")
