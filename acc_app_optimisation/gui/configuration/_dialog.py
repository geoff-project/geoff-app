"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t

import numpy as np
from cernml import coi, coi_funcs
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from ..excdialog import exception_dialog
from ._skeleton_points import SkeletonPointsWidget
from ._widget import ConfigureWidget

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
        self, target: t.Optional[coi.Configurable], parent: t.Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.target = target
        self._cfgform = None if target is None else ConfigureWidget(target.get_config())
        self._controls = QDialogButtonBox(  # type: ignore
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self._controls.button(QDialogButtonBox.Ok).clicked.connect(self._on_ok_clicked)
        self._controls.button(QDialogButtonBox.Apply).clicked.connect(
            self._on_apply_clicked
        )
        self._controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)

    def _on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        # Only close the dialog if there was no error.
        if self.apply_config():
            self.accept()

    def _on_apply_clicked(self) -> None:
        """Apply the configs."""
        self.apply_config()

    def apply_config(self) -> bool:
        """Apply the currently chosen values to the configurable.

        Returns:
            True if the config has been applied successfully. False if
            an exception has been raised.
        """
        if self.target is None:
            return True
        assert self._cfgform is not None
        try:
            values = self._cfgform.current_values()
            self.target.apply_config(values)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.warning("configuration failed validation: %s", exc)
            _show_config_failed(self.target, exc, parent=self)
            return False
        LOG.info("configuration applied: %s", values)
        return True


class PureDialog(_BaseDialog):
    """Qt dialog that allows configuring an environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self, target: coi.Configurable, parent: t.Optional[QWidget] = None
    ) -> None:
        super().__init__(target, parent)
        assert self._cfgform is not None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._cfgform)
        main_layout.addWidget(self._controls)


class OptimizableDialog(_BaseDialog):
    """Qt dialog that allows configuring a FunctionOptimizable.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    skeleton_points_updated = pyqtSignal(np.ndarray)

    def __init__(
        self,
        target: t.Union[coi.Configurable, coi_funcs.FunctionOptimizable],
        skeleton_points: t.Optional[np.ndarray] = None,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        if isinstance(target.unwrapped, coi.Configurable):
            super().__init__(t.cast(coi.Configurable, target), parent)
        else:
            super().__init__(None, parent)
        self._points_page: t.Optional[SkeletonPointsWidget]
        tab_widget = QTabWidget()
        if self._cfgform is not None:
            tab_widget.addTab(self._cfgform, "Configuration")
        if isinstance(target.unwrapped, coi_funcs.FunctionOptimizable):
            self._points_page = SkeletonPointsWidget(
                skeleton_points or np.array([], dtype=float)
            )
            tab_widget.addTab(self._points_page, "Skeleton points")
        else:
            self._points_page = None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self._controls)

    def apply_config(self) -> bool:
        if self._points_page is not None:
            try:
                points = self._points_page.skeletonPoints()
            except ValueError as exc:
                _show_skeleton_points_failed(exc, parent=self)
                return False
        success = super().apply_config()
        if success:
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        return success


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


def _show_skeleton_points_failed(exc: Exception, parent: t.Optional[QWidget]) -> None:
    dialog = exception_dialog(
        exc,
        title="Configuration validation",
        text="Cannot set skeleton points",
        parent=parent,
    )
    dialog.show()
