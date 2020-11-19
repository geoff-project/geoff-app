import pyqtgraph as pg
from accwidgets.graph import *
import numpy as np
from PyQt5.QtWidgets import *


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

    def setConstraintsCurveData(self, iterations, constraint_values):
        if not self.constraint_curves:
            self._setConstraintsCount(len(constraint_values.T))
        for curve, constraint_value in zip(self.constraint_curves, constraint_values.T):
            curve.setData(iterations, constraint_value)

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
        curve = pg.PlotCurveItem([], pen=(0, count))
        self.constraints_plot.addItem(curve)
        self.constraint_curves.append(curve)
        for i in range(1, count):
            name = f"constraint_{i}"
            self.constraints_plot.add_layer(name, pen=(i, count))
            curve = pg.PlotCurveItem([], pen=(i, count))
            self.constraints_plot.addItem(curve, layer=name)
            self.constraint_curves.append(curve)
