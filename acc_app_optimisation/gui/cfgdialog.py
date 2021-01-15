"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5 import QtWidgets
from cernml import coi, coi_funcs

from .cfgwidget import ConfigureWidget
from .excdialog import exception_dialog

LOG = logging.getLogger(__name__)


class _BaseDialog(QtWidgets.QDialog):
    """Common logic of `PureConfigureDialog` and `ProblemConfigureDialog`.

    Args:
        target: The environment to be configured. If None is passed, no
            `ConfigureWidget` is created.
        parent: The parent widget to attach to.

    Attributes:
        _cfgform: The `ConfigureWidget` to use. `None` if no target is passed.
        _controls: The `QDialogButtonBox` to use in this dialog.
    """

    def __init__(
        self,
        target: t.Optional[coi.Configurable],
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._cfgform = None if target is None else ConfigureWidget(target)
        self._controls = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Apply
            | QtWidgets.QDialogButtonBox.Cancel
        )
        self._controls.button(QtWidgets.QDialogButtonBox.Ok).clicked.connect(
            self.on_ok_clicked
        )
        self._controls.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(
            self.on_apply_clicked
        )
        self._controls.button(QtWidgets.QDialogButtonBox.Cancel).clicked.connect(
            self.reject
        )

    def on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        if self._cfgform is not None:
            exc = self._cfgform.apply_config(return_exc=True)
            if exc is not None:
                _show_config_failed(self._cfgform.target, exc, parent=self)
                return
        self.accept()

    def on_apply_clicked(self) -> None:
        """Apply the configs."""
        if self._cfgform is not None:
            exc = self._cfgform.apply_config(return_exc=True)
            if exc is not None:
                _show_config_failed(self._cfgform.target, exc, parent=self)


class PureConfigureDialog(_BaseDialog):
    """Qt dialog that allows configuring an environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self,
        target: coi.Configurable,
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(target, parent)
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self._cfgform)
        main_layout.addWidget(self._controls)


class ProblemConfigureDialog(_BaseDialog):
    """Qt dialog that allows configuring a FunctionOptimizable.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    skeleton_points_updated = pyqtSignal(np.ndarray)

    def __init__(
        self,
        target: coi.Problem,
        skeleton_points: t.Optional[np.ndarray] = None,
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(
            target=target if isinstance(target.unwrapped, coi.Configurable) else None,
            parent=parent,
        )
        tab_widget = QtWidgets.QTabWidget()
        if self._cfgform is not None:
            tab_widget.addTab(self._cfgform, "Configuration")
        if isinstance(target.unwrapped, coi_funcs.FunctionOptimizable):
            self.points_page = SkeletonPointsWidget(skeleton_points)
            tab_widget.addTab(self.points_page, "Skeleton points")
        else:
            self.points_page = None
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self._controls)

    def on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        # TODO: Catch errors.
        if self.points_page is not None:
            points = self.points_page.read_points()
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_ok_clicked()

    def on_apply_clicked(self) -> None:
        """Apply the configs."""
        # TODO: Catch errors.
        if self.points_page is not None:
            points = self.points_page.read_points()
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_apply_clicked()


class SkeletonPointsWidget(QtWidgets.QWidget):
    """The tab page presented to set skeleton points."""

    def __init__(
        self,
        points: t.Optional[t.Iterable[float]] = None,
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        description = QtWidgets.QLabel(
            "Enter skeleton points for optimization of LSA "
            "functions here. Enter one point in time for each "
            "point. Separate points with whitespace.",
            wordWrap=True,
        )
        initial_text = " ".join(map(str, [] if points is None else points))
        self.edit = QtWidgets.QLineEdit(initial_text)
        reset = QtWidgets.QPushButton(
            "Reset",
            enabled=False,
            sizePolicy=QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
            ),
        )
        reset.clicked.connect(lambda: self.edit.setText(initial_text))
        self.edit.textChanged.connect(
            lambda text: reset.setEnabled(text != initial_text)
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(description)
        layout.addWidget(self.edit)
        layout.addWidget(reset, alignment=Qt.AlignRight)
        layout.addStretch(1)

    def read_points(self) -> np.ndarray:
        """Parse the skeleton points entered by the user."""
        text = self.edit.text()
        points = [float(point) for point in text.split()]
        return np.array(points)


def _show_config_failed(
    target: coi.Configurable,
    exc: Exception,
    parent: t.Optional[QtWidgets.QWidget],
) -> None:
    dialog = exception_dialog(
        exc,
        title="Configuration validation",
        text=f"{target} could not be configured.",
        parent=parent,
    )
    dialog.show()
