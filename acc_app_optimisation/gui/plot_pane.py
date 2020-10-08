import pyqtgraph as pg
from accwidgets.graph import *
import numpy as np
from PyQt5.QtWidgets import *


class PlotPane():

    def __init__(self, mainwindow):
        mainwindow.plotTabWidget.setTabText(0, "Objective evolution")
        mainwindow.plotTabWidget.setTabText(1, "Actor evolution")



        self.plot = StaticPlotWidget()
        self.plot.setBackground('w')

        data = np.zeros(2)
        self.curve = pg.PlotCurveItem(data, pen="b")
        self.plot.addItem(self.curve)


        layout = QVBoxLayout()
        layout.addWidget(self.plot)
        mainwindow.plotPane.setLayout(layout)



