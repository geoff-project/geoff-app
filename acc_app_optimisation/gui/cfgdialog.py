"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t

import numpy as np
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTabWidget,
)
from cernml import coi, coi_funcs

from .cfgwidget import ConfigureWidget
from .excdialog import exception_dialog

LOG = logging.getLogger(__name__)


class _BaseDialog(QDialog):
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
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._cfgform = None if target is None else ConfigureWidget(target)
        self._controls = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self._controls.button(QDialogButtonBox.Ok).clicked.connect(self.on_ok_clicked)
        self._controls.button(QDialogButtonBox.Apply).clicked.connect(
            self.on_apply_clicked
        )
        self._controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)

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
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(target, parent)
        main_layout = QVBoxLayout(self)
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
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            target=target if isinstance(target.unwrapped, coi.Configurable) else None,
            parent=parent,
        )
        self._points = (
            QLineEdit(
                " ".join(map(str, skeleton_points))
                if skeleton_points is not None
                else ""
            )
            if isinstance(target.unwrapped, coi_funcs.FunctionOptimizable)
            else None
        )
        tab_widget = QTabWidget()
        if self._cfgform is not None:
            tab_widget.addTab(self._cfgform, "Configuration")
        if self._points is not None:
            points_page = QWidget()
            layout = QVBoxLayout(points_page)
            layout.addWidget(
                QLabel(
                    "Enter skeleton points for optimization of LSA\n"
                    "functions here. Enter one point in time for each\n"
                    "point. Separate points with whitespace."
                )
            )
            layout.addWidget(self._points)
            tab_widget.addTab(points_page, "Skeleton points")
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self._controls)

    def _read_points_from_widget(self) -> np.ndarray:
        text = self._points.text()
        points = [float(point) for point in text.split()]
        return np.array(points)

    def on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        # TODO: Catch errors.
        if self._points is not None:
            points = self._read_points_from_widget()
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_ok_clicked()

    def on_apply_clicked(self) -> None:
        """Apply the configs."""
        # TODO: Catch errors.
        if self._points is not None:
            points = self._read_points_from_widget()
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_apply_clicked()


def _show_config_failed(
    target: coi.Configurable, exc: Exception, parent: t.Optional[QWidget]
) -> None:
    dialog = exception_dialog(
        exc,
        title="Configuration validation",
        text=f"{target} could not be configured.",
        parent=parent,
    )
    dialog.show()
