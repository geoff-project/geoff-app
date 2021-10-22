#!/usr/bin/env python
"""Provide the `PlotManager` class"""

import logging
import typing as t

import accwidgets.graph as accgraph
import numpy as np
import pyqtgraph
from cernml import mpl_utils
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from ..utils.bounded import Bounded, BoundedArray
from .popout_mdi_area import PopinWindow, PopoutMdiArea

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


def _add_well_colored_legend(plot: accgraph.StaticPlotWidget) -> None:
    """Add a legend to the given plot with better colors."""
    legend = plot.addLegend()
    legend.bg_brush.setColor(pyqtgraph.mkColor("#DDDD"))
    legend.border_pen.setColor(pyqtgraph.mkColor("k"))
    legend.text_pen.setColor(pyqtgraph.mkColor("k"))


class PlotManager:
    """Manager to put plots into an MDI area and remove them from there.

    Args:
        mdi: The MDI window in which plots will be put.
    """

    def __init__(self, mdi: QtWidgets.QMdiArea) -> None:
        self._mdi = mdi
        pyqtgraph.setConfigOptions(foreground="k", background="w")

        self._objective_plot = _make_plot_widget_with_margins()
        self._objective_plot.setTitle("Objective function")
        self._objective_plot.setLabels(bottom="Step", left="Cost (norm. u.)")
        self._objective_plot.showGrid(x=True, y=True)
        self._constraint_names: t.Tuple[str, ...] = ()
        self._constraints_plot = _make_plot_widget_with_margins()
        self._constraints_plot.setTitle("Constraints")
        self._constraints_plot.setLabels(bottom="Step", left="Constraint (a. u.)")
        self._constraints_plot.showGrid(x=True, y=True)
        self._constraints_plot.hide()
        _add_well_colored_legend(self._constraints_plot)

        reward_episode_length_widget = QtWidgets.QWidget()
        reward_episode_length_widget.setWindowTitle("Objective and Constraints")
        layout = QtWidgets.QVBoxLayout(reward_episode_length_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._objective_plot, stretch=1)
        layout.addWidget(self._constraints_plot, stretch=1)
        self._mdi.addSubWindow(reward_episode_length_widget)

        self._actor_names: t.Tuple[str, ...] = ()
        self._actors_plot = _make_plot_widget_with_margins()
        self._actors_plot.setWindowTitle("Actors")
        self._actors_plot.setLabels(bottom="Step", left="Actor values (norm. u.)")
        self._actors_plot.showGrid(x=True, y=True)
        self._mdi.addSubWindow(self._actors_plot)
        _add_well_colored_legend(self._actors_plot)

        self._episode_length_plot = _make_plot_widget_with_margins()
        self._episode_length_plot.setTitle("Episode length")
        self._episode_length_plot.setLabels(bottom="Episode", left="Steps")
        self._episode_length_plot.showGrid(x=True, y=True)
        self._reward_plot = _make_plot_widget_with_margins()
        self._reward_plot.setTitle("Final reward")
        self._reward_plot.setLabels(bottom="Episode", left="Reward (a.u.)")
        self._reward_plot.showGrid(x=True, y=True)
        reward_episode_length_widget = QtWidgets.QWidget()
        reward_episode_length_widget.setWindowTitle("RL Training")
        layout = QtWidgets.QVBoxLayout(reward_episode_length_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._episode_length_plot, stretch=1)
        layout.addWidget(self._reward_plot, stretch=1)
        self._mdi.addSubWindow(reward_episode_length_widget)

        self._mpl_canvases: t.List[FigureCanvas] = []
        # Running ID to prevent giving out the same title to two
        # different unnamed figures.
        self._canvas_id = 0

    def redraw_mpl_figures(self, *, immediate: bool = False) -> None:
        """Issue a redraw command to all Matplotlib figures.

        Args:
            immediate: If passed and True, this function blocks until
                all figures are redrawn. The default is to only issue
                the redraw command, and to delay its execution until the
                run of the event loop. This behavior is reasonable when
                you want to avoid GUI freezes.
        """
        if immediate:
            for canvas in self._mpl_canvases:
                canvas.draw()
        else:
            for canvas in self._mpl_canvases:
                canvas.draw_idle()

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
        if not title:
            title = f"Figure {self._canvas_id}"
        subwindow = QtWidgets.QWidget()
        canvas = FigureCanvas(figure)
        toolbar = NavigationToolbar(canvas, subwindow)
        layout = QtWidgets.QVBoxLayout(subwindow)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        subwindow.setWindowTitle(title)
        self._mdi.addSubWindow(subwindow).show()
        self._mpl_canvases.append(canvas)

    def add_mpl_figures(self, figures: mpl_utils.MatplotlibFigures) -> None:
        """Add several Matplotlib figures, creating one subwindow for each.

        Args:
            figures: An iterable. Each item is either a figure to be added
                (forwarded to `add_mpl_figure(figure)`) or a tuple of
                title and figure (forwarded to `add_mpl_figure(figure,
                title)`). The ordering is such that mapping from `str`
                to figures can be passed in via `dict.items()`.
        """
        for title, figure in mpl_utils.iter_matplotlib_figures(figures):
            self.add_mpl_figure(figure, title)

    def replace_mpl_figures(self, figures: mpl_utils.MatplotlibFigures) -> None:
        """Clear and add figures, but keep existing ones.

        This is like `clear_figures()` followed by `add_figures()`, but
        it avoids removing and re-adding figures that are already in
        this manager.
        """
        # Handle `fig` and `(title, fig)` properly.
        titles_and_figures = tuple(mpl_utils.iter_matplotlib_figures(figures))
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

    def _remove_canvas_window(self, figure: FigureCanvas) -> None:
        """Remove a widget, no matter if subwindow or PopinWindow."""
        # Parent is the widget wrapping canvas and navigation toolbar.
        # Grapndparent is the subwindow/pop-in window.
        parent = figure.parent().parent()
        if isinstance(parent, PopinWindow):
            t.cast(PopoutMdiArea, self._mdi).removePopinWindow(parent)
            parent.setParent(None)  # type: ignore
            parent.deleteLater()
        elif isinstance(parent, QtWidgets.QMdiSubWindow):
            self._mdi.removeSubWindow(parent)
            parent.setParent(None)  # type: ignore
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

    def set_reward_curve_data(self, reward_lists: t.List[t.List[float]]) -> None:
        reward_curve = self._reward_curve()
        episode_length_curve = self._episode_length_curve()
        xlist = np.arange(0, len(reward_lists))
        rlist = np.array(
            [rewards[-1] if rewards else np.nan for rewards in reward_lists]
        )
        llist = np.array([len(rewards) for rewards in reward_lists])
        reward_curve.setData(xlist, rlist)
        episode_length_curve.setData(xlist, llist)

    def reset_default_plots(
        self,
        *,
        objective_name: str,
        actor_names: t.Tuple[str, ...],
        constraint_names: t.Tuple[str, ...],
    ) -> None:
        self._objective_plot.clear()
        self._actors_plot.clear()
        self._constraints_plot.clear()
        self._reward_plot.clear()
        self._episode_length_plot.clear()
        self._objective_plot.setLabel(
            axis="left",
            text=objective_name or "Objective function",
        )
        self._actor_names = actor_names
        self._constraint_names = constraint_names

    def _objective_curve(self) -> pyqtgraph.PlotDataItem:
        """The single curve inside `self._objective_plot.`"""
        curves = self._objective_plot.getPlotItem().items
        if curves:
            [objective_curve] = curves
        else:
            objective_curve = pyqtgraph.PlotDataItem(pen="b", symbol="+", symbolPen="b")
            self._objective_plot.addItem(objective_curve)
        return objective_curve

    def _actors_curves(self, num: int) -> t.Iterable[pyqtgraph.PlotDataItem]:
        """The curves inside `self._actor_curves.`

        If there are not exactly `num` curves in the actor plot, all
        curves are destroyed and `num` curves are created and returned.
        """
        axes = self._actors_plot.getPlotItem()
        if len(axes.items) != num:
            axes.clear()
            names = self._actor_names
            assert len(names) == num, f"{len(names)} == {num}"
            for i, name in enumerate(names):
                curve = pyqtgraph.PlotDataItem(
                    pen=(i, num), symbol="+", symbolPen=(i, num), name=name
                )
                axes.addItem(curve)
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
            names = self._constraint_names
            assert len(names) == num, f"{len(names)} == {num}"
            for name, (color, layer_name) in zip(names, _iter_colored_layers(num)):
                if layer_name:
                    self._constraints_plot.add_layer(layer_name, pen=color)
                curves = _make_curve_with_bounds(
                    color=color, name=name, layer=layer_name, symbol="+"
                )
                result.append(curves)
                _add_items_to_plot([curves.values, curves.lower, curves.upper], axes)
        return result

    def _reward_curve(self) -> pyqtgraph.PlotDataItem:
        """The single curve inside `self._reward_plot.`"""
        curves = self._reward_plot.getPlotItem().items
        if curves:
            [reward_curve] = curves
        else:
            reward_curve = pyqtgraph.PlotDataItem(
                pen="#00F3", symbol="o", symbolPen=None, symbolBrush="b"
            )
            self._reward_plot.addItem(reward_curve)
        return reward_curve

    def _episode_length_curve(self) -> pyqtgraph.PlotDataItem:
        """The single curve inside `self._reward_plot.`"""
        curves = self._episode_length_plot.getPlotItem().items
        if curves:
            [episode_length_curve] = curves
        else:
            episode_length_curve = pyqtgraph.PlotDataItem(
                pen="#00F3",
                symbol="o",
                symbolPen=None,
                symbolBrush="b",
            )
            self._episode_length_plot.addItem(episode_length_curve)
        return episode_length_curve


def _make_curve_with_bounds(
    color: ColorSpec,
    name: str,
    layer: t.Optional[str],
    symbol: t.Optional[str] = None,
) -> Bounded[pyqtgraph.PlotDataItem]:
    """Create three curves; one with a solid-line, two with a dashed-line pen.

    This only creates the curve items; you still need to add them to a
    plot. (and add a layer if you use any)
    """
    parsed_color: QtGui.QColor = pyqtgraph.mkColor(color)
    solid_pen = QtGui.QPen(parsed_color, 0.0, Qt.SolidLine)
    dashed_pen = QtGui.QPen(parsed_color, 0.0, Qt.DashLine)
    # Only add `name` to the values item. We don't want the upper nor
    # the lower bounds to appear in the plot's legend.
    curves = Bounded(
        values=pyqtgraph.PlotDataItem(
            pen=solid_pen, layer=layer, symbol=symbol, symbolPen=solid_pen, name=name
        ),
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
