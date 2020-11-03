import pyqtgraph as pg
from accwidgets.graph import *
import numpy as np
from PyQt5.QtWidgets import *


class PlotPane:
    def __init__(self, mainwindow):
        mainwindow.plotTabWidget.setTabText(0, "Objective evolution")
        mainwindow.plotTabWidget.setTabText(1, "Actor evolution")

        self.plot = StaticPlotWidget()
        self.plot.setBackground("w")
        layout = QVBoxLayout()
        layout.addWidget(self.plot)
        mainwindow.plotPane.setLayout(layout)

        self.actor_plot = StaticPlotWidget()
        self.actor_plot.setBackground("w")
        layout = QVBoxLayout()
        layout.addWidget(self.actor_plot)
        mainwindow.networkfityPane.setLayout(layout)

        self.curve = pg.PlotCurveItem([0, 0], pen="b")
        self.plot.addItem(self.curve)

        self.actor_curves = []
        self.actor_plot.clear()
        for i in range(10):
            curve = pg.PlotCurveItem([i, i], pen=(i, 10))
            self.actor_plot.addItem(curve)
            self.actor_curves.append(curve)

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
