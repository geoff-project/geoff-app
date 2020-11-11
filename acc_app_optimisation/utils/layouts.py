#!/usr/bin/env python
"""Utilities for dealing with QLayout."""

import typing as t
from collections import deque

from PyQt5 import QtWidgets


def iter_layout(layout: QtWidgets.QLayout) -> t.Iterator[QtWidgets.QLayoutItem]:
    """Return an iterator over all items of a layout.

    The usual iterator invalidation rules hold: Do not modify the layout
    items while the returned iterator is active.
    """
    for i in range(layout.count()):
        item = layout.itemAt(i)
        assert item is not None
        yield item


def drain_layout(layout: QtWidgets.QLayout) -> t.Iterator[QtWidgets.QLayoutItem]:
    """Return an iterator that removes items from a layout.

    The usual iterator invalidation rules hold: Do not modify the layout
    items while the returned iterator is active.
    """
    while True:
        item = layout.takeAt(0)
        if item is None:
            break
        yield item


def iter_layout_widgets(
    layout: QtWidgets.QLayout, *, recursive: bool = True
) -> t.Iterator[QtWidgets.QWidget]:
    """Return an iterator over child widgets of a layout.

    If recursive is True (the default), this also iterates over widgets
    of any child layouts. If passed and False, only top-level child
    widgets of this layout are passed.
    """
    for item in iter_layout(layout):
        if item.widget():
            yield item.widget()
        elif item.layout():
            if recursive:
                yield from iter_layout_widgets(item.layout(), recursive=True)
        else:
            pass


def clear_children(widget: QtWidgets.QWidget) -> None:
    """Remove children of a widget by draining its layout.

    This recursively iterates through the widget's layout and all child
    layouts. Each widget is removed from its parent and marked for
    deletion.
    """
    layout = widget.layout()
    if not layout:
        return
    # A queue of child layouts we still have to go through.
    layouts = deque([layout])
    while layouts:
        for item in drain_layout(layouts.popleft()):
            if item.layout():
                # Found a child layout, add it to the todo list.
                layouts.append(item.layout())
            elif item.widget():
                # This seems to be the safest way to remove a widget
                # permanently.
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()
