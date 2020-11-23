import typing

import pyjapc
from pjlsa import pjlsa
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QFrame,
    QWidget,
    QTableView,
    QAbstractItemView,
    QGraphicsDropShadowEffect,
    QDockWidget,
    QLabel,
    QVBoxLayout,
)

from .image import Image
from .lsa_model import LsaSelectorModel


class LsaSelectorWidget(QDockWidget):
    selectionChanged: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        parent: typing.Optional[QWidget] = ...,
        lsa: pjlsa.LSAClient = ...,
        japc: pyjapc.PyJapc = ...,
        accelerator: str = "sps",
        application_title=None,
        application_logo=None,
        as_dock=True,
    ) -> None:
        super().__init__(parent)

        if application_title is not None:
            title = QLabel(application_title)
            title.setLineWidth(1)
            title.setFrameShape(QFrame.Panel)
            title.setFrameShadow(QFrame.Raised)
            title.setFont(QFont("Roboto", 10, QFont.Bold))
            title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        if application_logo is not None:
            image = Image(application_logo, 150)

        label = QLabel("LSA Cycles")
        label.setLineWidth(1)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Raised)
        label.setFont(QFont("Roboto", 10, QFont.Bold))
        label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self.view = QTableView()
        self.view.setModel(LsaSelectorModel(lsa, japc, accelerator))
        self.view.setShowGrid(False)
        self.view.verticalHeader().hide()
        self.view.horizontalHeader().hide()
        self.view.resizeColumnsToContents()
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setFrameShape(QFrame.Panel)
        self.view.setFrameShadow(QFrame.Sunken)
        self.view.selectionModel().currentChanged.connect(
            lambda x: self.selectionChanged.emit(self.view.model().getItem(x)[0]),
        )
        self.view.setCurrentIndex(self.view.model().index(0, 0))
        for i in range(self.view.model().rowCount()):
            self.view.setRowHeight(i, 10)

        glow = QGraphicsDropShadowEffect()
        glow.setOffset(0, 0)
        glow.setBlurRadius(8)
        glow.setColor(QColor("black"))
        self.view.setGraphicsEffect(glow)

        # Assemble widget
        self.setWidget(QWidget())
        self.widget().setLayout(QVBoxLayout())
        if application_title is not None:
            self.widget().layout().addWidget(title)
        if application_logo is not None:
            self.widget().layout().addWidget(image)
        self.widget().layout().addWidget(label)
        self.widget().layout().addWidget(self.view)
        if as_dock:
            self.setFeatures(
                QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable,
            )
        else:
            self.setFeatures(QDockWidget.NoDockWidgetFeatures)

    def getContext(self):
        return self.view.model().context

    def getUser(self):
        return self.view.model().user

    def getPyJapcObject(self):
        return self.view.model().pyjapc

    def setAccelerator(self, acc_name: str):
        self.view.model().setAccelerator(acc_name)
        # Since the row count likely changed, we need to update the scroll
        # bars. The scroll bars would also change without this call, but only
        # after a visible delay.
        self.view.updateGeometries()
