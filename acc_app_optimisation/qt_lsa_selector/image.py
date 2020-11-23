from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets


class Image(QtWidgets.QLabel):
    def __init__(self, img, size=50):
        super().__init__()

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        self.pixmap = QtGui.QPixmap(img)
        self.setMinimumHeight(size)

    def paintEvent(self, event):
        size = self.size()
        painter = QtGui.QPainter(self)
        point = QtCore.QPoint(0, 0)
        scaledPix = self.pixmap.scaled(
            size,
            QtCore.Qt.KeepAspectRatio,
            transformMode=QtCore.Qt.SmoothTransformation,
        )

        # start painting the label from left upper corner
        point.setX((size.width() - scaledPix.width()) / 2)
        point.setY((size.height() - scaledPix.height()) / 2)
        painter.drawPixmap(point, scaledPix)
