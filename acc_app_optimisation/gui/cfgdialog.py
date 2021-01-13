"""Provide a dialog for configuring optimization problems."""

import typing as t

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QTabWidget,
)
from cernml import coi

from .cfgwidget import ConfigureWidget
from .excdialog import exception_dialog


class ConfigureDialog(QDialog):
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
        super().__init__(parent)
        self.cfg_widget = ConfigureWidget(target)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.cfg_widget)
        controls = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        controls.button(QDialogButtonBox.Ok).clicked.connect(self.on_ok_clicked)
        controls.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_clicked)
        controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        main_layout.addWidget(controls)

    def on_ok_clicked(self):
        """Apply the configs and close the window."""
        exc = self.cfg_widget.apply_config(return_exc=True)
        if exc:
            _show_config_failed(self.cfg_widget.target, exc, parent=self)
        else:
            self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        exc = self.cfg_widget.apply_config(return_exc=True)
        if exc:
            _show_config_failed(self.cfg_widget.target, exc, parent=self)


class FunctionConfigureDialog(QDialog):
    """Qt dialog that allows configuring a FunctionOptimizable.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self,
        target: coi.Configurable,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        tab_widget = QTabWidget()
        if isinstance(target, coi.Configurable):
            self.cfg_widget = ConfigureWidget(target)
            tab_widget.addTab(self.cfg_widget, "Configuration")
        else:
            self.cfg_widget = None
        self.points_widget = QLineEdit()
        tab_widget.addTab(self.points_widget, "Skeleton points")
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        controls = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        controls.button(QDialogButtonBox.Ok).clicked.connect(self.on_ok_clicked)
        controls.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_clicked)
        controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        main_layout.addWidget(controls)

    def on_ok_clicked(self):
        """Apply the configs and close the window."""
        exc = self.cfg_widget.apply_config(return_exc=True) if self.cfg_widget else None
        if exc:
            _show_config_failed(self.cfg_widget.target, exc, parent=self)
        else:
            self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        if self.cfg_widget:
            exc = self.cfg_widget.apply_config(return_exc=True)
            if exc:
                _show_config_failed(self.cfg_widget.target, exc, parent=self)


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
