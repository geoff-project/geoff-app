#!/usr/bin/env python

import typing as t

from PyQt5 import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from ..utils.layouts import clear_children, iter_layout_widgets


class FiguresView(QtWidgets.QScrollArea):
    """Widget that shows several `FigureCanvas`es."""

    # pylint: disable = invalid-name

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        widget = QtWidgets.QWidget()
        widget.setLayout(QtWidgets.QVBoxLayout())
        self.setWidget(widget)
        self.setWidgetResizable(True)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )

    def clear(self) -> None:
        """Remove all figures from this widget."""
        clear_children(self.widget())

    def setFigures(self, figures: t.Iterable[Figure]) -> None:
        """Remove all figures and replace them with the given ones."""
        widget = self.widget()
        clear_children(widget)
        layout = widget.layout()
        for figure in figures:
            canvas = FigureCanvas(figure)
            layout.addWidget(canvas)

    def figures(self) -> t.List[Figure]:
        """Return a list of all figures currently in this widget."""
        layout = self.widget().layout()
        if layout is None:
            return []
        return [widget.figure for widget in iter_layout_widgets(layout, recursive=True)]

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(640, 480)
