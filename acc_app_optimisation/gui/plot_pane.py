import pyqtgraph as pg
import numpy as np
from accwidgets.graph import *
from PyQt5.QtWidgets import *

from ..algos.single_opt import ConstraintsUpdateMessage


class PlotPane:
    def __init__(self, mainwindow):
        mainwindow.plotTabWidget.setTabText(0, "Objective evolution")
        mainwindow.plotTabWidget.setTabText(1, "Actor evolution")

        self.objective_plot = StaticPlotWidget()
        self.objective_plot.setBackground("w")

        self.constraints_plot = StaticPlotWidget()
        self.constraints_plot.setBackground("w")

        self.objective_constraints_layout = QVBoxLayout(mainwindow.plotPane)
        self.objective_constraints_layout.addWidget(self.objective_plot, stretch=1)

        self.actor_plot = StaticPlotWidget()
        self.actor_plot.setBackground("w")

        QVBoxLayout(mainwindow.networkfityPane).addWidget(self.actor_plot)

        self.objective_curve = pg.PlotCurveItem([0, 0], pen="b")
        self.objective_plot.addItem(self.objective_curve)

        self.actor_curves = []
        self.actor_plot.clear()
        for i in range(10):
            curve = pg.PlotCurveItem([i, i], pen=(i, 10))
            self.actor_plot.addItem(curve)
            self.actor_curves.append(curve)

    def setConstraintsCurveData(self, iterations, message: ConstraintsUpdateMessage):
        values: np.ndarray = message.values
        lb: np.ndarray = message.lower_bound
        ub: np.ndarray = message.upper_bound
        if not self.constraint_curves:
            self._setConstraintsCount(len(values.T))
        for curves, constraint_value, lb_value, ub_value in zip(
            self.constraint_curves, values.T, lb, ub
        ):
            curves.values.setData(iterations, constraint_value)
            curves.lower_bound.setData(iterations, np.ones_like(iterations) * lb_value)
            curves.upper_bound.setData(iterations, np.ones_like(iterations) * ub_value)

    def setActorsCurveData(self, iterations, actors):
        for curve, actor in zip(self.actor_curves, actors.T):
            curve.setData(iterations, actor)

    def setActorCount(self, count):
        self.actor_curves = []
        self.actor_plot.clear()
        for i in range(count):
            curve = pg.PlotCurveItem([i, i], pen=(i, count))
            self.actor_plot.addItem(curve)
            self.actor_curves.append(curve)

    def enableConstraintsPlot(self, enabled: bool):
        layout = self.objective_constraints_layout
        self.constraints_plot.setVisible(enabled)
        if enabled:
            layout.addWidget(self.constraints_plot, stretch=1)
        else:
            layout.removeWidget(self.constraints_plot)

    def clearConstraintCurves(self):
        self._setConstraintsCount(0)

    def _setConstraintsCount(self, count):
        self.constraint_curves = []
        self.constraints_plot.clear()
        if not count:
            return

        self.constraint_curves.append(
            self._makeConstraintsCurves(color=(0, count), layer=None)
        )
        for i in range(1, count):
            name = f"constraint_{i}"
            self.constraint_curves.append(
                self._makeConstraintsCurves(color=(i, count), layer=name)
            )

    def _makeConstraintsCurves(self, color, layer):
        solid_pen = QPen(pg.mkColor(color), 0.0, Qt.SolidLine)
        dashed_pen = QPen(pg.mkColor(color), 0.0, Qt.DashLine)
        if layer is not None:
            self.constraints_plot.add_layer(layer, pen=solid_pen)
        curves = ConstraintsUpdateMessage(
            values=pg.PlotCurveItem([], pen=solid_pen, layer=layer),
            lower_bound=pg.PlotCurveItem([], pen=dashed_pen, layer=layer),
            upper_bound=pg.PlotCurveItem([], pen=dashed_pen, layer=layer),
        )
        self.constraints_plot.addItem(curves.values)
        self.constraints_plot.addItem(curves.lower_bound)
        self.constraints_plot.addItem(curves.upper_bound)
        return curves
