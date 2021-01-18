#!/usr/bin/env python
"""Provide the `PlotManager` class"""

import logging
import typing as t

import accwidgets.graph as accgraph
import numpy as np
import pyqtgraph
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from cernml.coi.utils import iter_matplotlib_figures
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from .popout_mdi_area import PopinWindow, PopoutMdiArea
from ..utils.bounded import Bounded, BoundedArray


LOG = logging.getLogger(__name__)


ColorSpec = t.Union[
    str,  # one of: r, g, b, c, m, y, k, w
    str,  # "RGB"
    str,  # "RGBA"
    str,  # "RRGGBB"
    str,  # "RRGGBBAA"
    int,  # see `pyqtgraph.intColor()`
    t.Tuple[int, int],  # see `pyqtgraph.intColor()`
    t.Tuple[int, int, int],  # R, G, B; integers 0-255
    t.Tuple[int, int, int, int],  # R, G, B, A; integers 0-255
    QtGui.QColor,
]
FigureSpec = t.Union[Figure, t.Tuple[str, Figure]]
FigureCollection = t.Union[t.Iterable[FigureSpec], t.Mapping[str, Figure]]


def _add_items_to_plot(
    curves: t.Iterable[pyqtgraph.PlotDataItem],
    plot: t.Union[pyqtgraph.PlotItem, pyqtgraph.PlotWidget],
) -> None:
    """Convenience function to add multiple items to a plot."""
    for curve in curves:
        plot.addItem(curve)


def _make_plot_widget_with_margins() -> accgraph.StaticPlotWidget:
    """Trivial helper to add some margins to our plots."""
    widget = accgraph.StaticPlotWidget()
    widget.plotItem.setContentsMargins(15, 15, 15, 15)
    return widget


class PlotManager:
    """Manager to put plots into an MDI area and remove them from there.

    Args:
        mdi: The MDI window in which plots will be put.
    """

    def __init__(self, mdi: QtWidgets.QMdiArea) -> None:
        self._mdi = mdi
        pyqtgraph.setConfigOptions(foreground="k", background="w")

        self._objective_plot = _make_plot_widget_with_margins()
        self._objective_plot.setTitle("Objective")
        self._constraints_plot = _make_plot_widget_with_margins()
        self._constraints_plot.setTitle("Constraints")
        self._constraints_plot.hide()
        objective_constraints_widget = QtWidgets.QWidget()
        objective_constraints_widget.setWindowTitle("Objective and Constraints")
        layout = QtWidgets.QVBoxLayout(objective_constraints_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._objective_plot, stretch=1)
        layout.addWidget(self._constraints_plot, stretch=1)
        self._mdi.addSubWindow(objective_constraints_widget)

        self._actors_plot = _make_plot_widget_with_margins()
        self._actors_plot.setWindowTitle("Actors")
        self._mdi.addSubWindow(self._actors_plot)

        self._mpl_canvases: t.List[FigureCanvas] = []
        # Running ID to prevent giving out the same title to two
        # different unnamed figures.
        self._canvas_id = 0

    def iter_mpl_figures(self) -> t.Iterator[Figure]:
        """Return the list of Matplotlib figures already being managed."""
        return (canvas.figure for canvas in self._mpl_canvases)

    def add_mpl_figure(self, figure: Figure, title: str = "") -> None:
        """Add a Matplotlib figure to the list of subwindows.

        Args:
            figure: The figure to add to this manager. This must not be
                managed by PyPlot.
            title: The window title for the figure. If the empty string
                (or any other False-y value), a title is generated
                automatically.
        """
        if figure in self.iter_mpl_figures():
            LOG.warning("figure %s already managed, not adding again", figure)
            return
        # Increment in any case -- this prevents awkward name lists like
        # this: ["Figure 1", "Named Figure", "Figure 2"].
        self._canvas_id += 1
        canvas = FigureCanvas(figure)
        if not title:
            title = f"Figure {self._canvas_id}"
        canvas.setWindowTitle(title)
        self._mpl_canvases.append(canvas)
        subwindow = self._mdi.addSubWindow(canvas)
        subwindow.show()

    def add_mpl_figures(self, figures: FigureCollection) -> None:
        """Add several Matplotlib figures, creating one subwindow for each.

        Args:
            figures: An iterable. Each item is either a figure to be added
                (forwarded to `add_mpl_figure(figure)`) or a tuple of
                title and figure (forwarded to `add_mpl_figure(figure,
                title)`). The ordering is such that mapping from `str`
                to figures can be passed in via `dict.items()`.
        """
        for title, figure in iter_matplotlib_figures(figures):
            self.add_mpl_figure(figure, title)

    def replace_mpl_figures(self, figures: FigureCollection) -> None:
        """Clear and add figures, but keep existing ones.

        This is like `clear_figures()` followed by `add_figures()`, but
        it avoids removing and re-adding figures that are already in
        this manager.
        """
        # Handle `fig` and `(title, fig)` properly.
        titles_and_figures = tuple(iter_matplotlib_figures(figures))
        # Remove stale figures be making a new list without them -- the
        # GC will take care of the rest.
        self._clear_mpl_figures_except(fig for _, fig in titles_and_figures)
        # If _all_ figures are gone, we know that it's safe to reuse
        # IDs again.
        if not self._mpl_canvases:
            self._canvas_id = 0
        # Remove from the argument all windows that have already been
        # added to avoid pointless warnings.
        common_figures = frozenset(self.iter_mpl_figures())
        self.add_mpl_figures(
            (t, f) for (t, f) in titles_and_figures if f not in common_figures
        )

    def clear_mpl_figures(self) -> None:
        """Remove all Matplotlib figures from this manager."""
        for canvas in self._mpl_canvases:
            self._remove_canvas_window(canvas)
        self._mpl_canvases.clear()
        # Since we know that all figures are gone, it is save to reuse
        # IDs again.
        self._canvas_id = 0

    def _clear_mpl_figures_except(self, figures: t.Iterable[Figure]) -> None:
        """Remove all canvases except those whose figures are passed."""
        figures = frozenset(figures)
        remaining_canvases = []
        for canvas in self._mpl_canvases:
            if canvas.figure in figures:
                remaining_canvases.append(canvas)
            else:
                self._remove_canvas_window(canvas)
        self._mpl_canvases = remaining_canvases

    def _remove_canvas_window(self, figure: QtWidgets.QWidget) -> None:
        """Remove a widget, no matter if subwindow or PopinWindow."""
        parent = figure.parent()
        if isinstance(parent, PopinWindow):
            t.cast(PopoutMdiArea, self._mdi).removePopinWindow(parent)
            parent.setParent(None)
            parent.deleteLater()
        elif isinstance(parent, QtWidgets.QMdiSubWindow):
            self._mdi.removeSubWindow(parent)
            parent.setParent(None)
            parent.deleteLater()
        else:
            raise TypeError("unknown plot parent: " + repr(parent))

    def set_constraints_plot_visible(self, enabled: bool = True) -> None:
        """Show or hide the constraints plot."""
        if enabled:
            self._constraints_plot.show()
        else:
            self._constraints_plot.hide()

    def set_objective_curve_data(self, xlist: np.ndarray, ylist: np.ndarray) -> None:
        """Update the objective curve with new data.

        Args:
            xlist: A 1D NumPy array with `N` X coordinates.
            ylist: A 1D NumPy array with `N` Y coordinates.
        """
        _assert_ndim(1, xlist, ylist)
        curve = self._objective_curve()
        curve.setData(xlist, ylist)

    def set_actors_curve_data(self, xlist: np.ndarray, ylist: np.ndarray) -> None:
        """Update the actor curves with new data.

        Args:
            xlist: A 1D NumPy array with `N` X coordinates.
            ylist: A 2D NumPy array of shape `(N, A)`, where `N` is the
                number of points and `A` is the number of actors to
                plot.
        """
        _assert_ndim(1, xlist)
        _assert_ndim(2, ylist)
        _assert_same_length(xlist, ylist)
        curves_data = np.transpose(ylist)
        curves = self._actors_curves(len(curves_data))
        for curve, curve_ylist in zip(curves, curves_data):
            curve.setData(xlist, curve_ylist)

    def set_constraints_curve_data(
        self,
        xlist: np.ndarray,
        ylist: BoundedArray,
    ) -> None:
        """Update the constraints curves with new data.

        Args:
            xlist: A 1D NumPy array with `N` X coordinates.
            ylist: A `BoundedArray` containing three arrays:
                values: A 2D NumPy array of shape `(N, C)`, where `N` is
                    the number of points and `C` is the number of
                    constraints to plot.
                lower: A 1D NumMpy array with `C` lower bounds.
                upper: A 1D NumMpy array with `C` upper bounds.
        """
        _assert_ndim(1, xlist, ylist.lower, ylist.upper)
        _assert_ndim(2, ylist.values)
        _assert_same_length(xlist, ylist.values)
        constraints_data = np.transpose(ylist.values)
        _assert_same_length(constraints_data, ylist.lower, ylist.upper)
        constraints = self._constraints_curves(len(constraints_data))
        for constraint, values, lower_value, upper_value in zip(
            constraints, constraints_data, ylist.lower, ylist.upper
        ):
            constraint.values.setData(xlist, values)
            constraint.lower.setData(xlist, np.ones_like(values) * lower_value)
            constraint.upper.setData(xlist, np.ones_like(values) * upper_value)

    def _objective_curve(self) -> pyqtgraph.PlotDataItem:
        """The single curve inside `self._objective_plot.`"""
        curves = self._objective_plot.getPlotItem().items
        if curves:
            [objective_curve] = curves
        else:
            objective_curve = pyqtgraph.PlotDataItem(pen="b")
            self._objective_plot.addItem(objective_curve)
        return objective_curve

    def _actors_curves(self, num: int) -> t.Iterable[pyqtgraph.PlotDataItem]:
        """The curves inside `self._actor_curves.`

        If there are not exactly `num` curves in the actor plot, all
        curves are destroyed and `num` curves are created and returned.
        """
        axes = self._actors_plot.getPlotItem()
        if len(axes.items) != num:
            self._actors_plot.clear()
            for i in range(num):
                curve = pyqtgraph.PlotDataItem(pen=(i, num))
                self._actors_plot.addItem(curve)
        return list(axes.items)

    def _constraints_curves(
        self, num: int
    ) -> t.Iterable[Bounded[pyqtgraph.PlotDataItem]]:
        """The curves inside `self._constraints_curves.`

        If there are not exactly `num` bounded curves in the constraints
        plot, all curves are destroyed and `num` bounded curves are
        created and returned.
        """
        result = []
        axes = self._constraints_plot.getPlotItem()
        if len(axes.items) == 3 * num:
            # Reorganize the flat list of curves into chunks of 3.
            for i in range(num):
                chunk = axes.items[3 * i : 3 * i + 3]
                assert len(chunk) == 3, chunk
                result.append(Bounded(*chunk))
        else:
            self._constraints_plot.clear()
            for color, layer_name in _iter_colored_layers(num):
                if layer_name:
                    self._constraints_plot.add_layer(layer_name, pen=color)
                curves = _make_curve_with_bounds(color=color, layer=layer_name)
                result.append(curves)
                _add_items_to_plot(curves, axes)
        return result


def _make_curve_with_bounds(
    color: ColorSpec,
    layer: t.Optional[str],
) -> Bounded[pyqtgraph.PlotDataItem]:
    """Create three curves; one with a solid-line, two with a dashed-line pen.

    This only creates the curve items; you still need to add them to a
    plot. (and add a layer if you use any)
    """
    color = pyqtgraph.mkColor(color)
    solid_pen = QtGui.QPen(color, 0.0, Qt.SolidLine)
    dashed_pen = QtGui.QPen(color, 0.0, Qt.DashLine)
    curves = Bounded(
        values=pyqtgraph.PlotDataItem(pen=solid_pen, layer=layer),
        lower=pyqtgraph.PlotDataItem(pen=dashed_pen, layer=layer),
        upper=pyqtgraph.PlotDataItem(pen=dashed_pen, layer=layer),
    )
    return curves


def _iter_colored_layers(count: int) -> t.Iterator[t.Tuple[ColorSpec, t.Optional[str]]]:
    """Return an iterator over colors and layer names.

    The iterator's first layer always is `None`, meaning that the main
    axis is used. Further layers are unique layer names that can be
    passed to `accwidgets.graph.StaticPlotWidget.add_layer()`.

    Example:

        >>> for color, name in _iter_colored_layers(3):
        ...     print(color, '--', name)
        (0, 3) -- None
        (1, 3) -- layer_1
        (2, 3) -- layer_2
    """
    yield ((0, count), None)
    for i in range(1, count):
        name = f"layer_{i}"
        yield ((i, count), name)


def _assert_same_length(first: np.ndarray, *others: np.ndarray) -> None:
    """Assert that the first dimension of all given arrays has the same length."""
    expected = len(first)
    assert set(len(other) for other in others) == {
        expected
    }, f"arrays have inequal first dimension: {list(map(len, [first, *others]))}"


def _assert_ndim(ndim: int, *arrays: np.ndarray) -> None:
    """Assert that the given arrays have a given number of dimensions."""
    assert all(
        np.ndim(arr) == ndim for arr in arrays
    ), f"arrays don't all have {ndim} dimension(s): {list(map(np.ndim, arrays))}"
