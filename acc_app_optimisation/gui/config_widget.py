import typing as t

import numpy as np
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QCheckBox,
)
from PyQt5.QtGui import (
    QIntValidator,
    QDoubleValidator,
)

from cernml import coi


class ConfigureDialog(QDialog):
    """Qt dialog that allows configuring an environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(self, target: coi.Configurable, parent=None):
        super().__init__(parent)
        self.target = target
        self.config = self.target.get_config()
        self.current_values = {
            field.dest: field.value for field in self.config.fields()
        }
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        params = QWidget()
        main_layout.addWidget(params)
        params_layout = QFormLayout()
        params.setLayout(params_layout)
        for field in self.config.fields():
            label = QLabel(field.label)
            widget = self._make_field_widget(field)
            params_layout.addRow(label, widget)
        controls = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        controls.button(QDialogButtonBox.Ok).clicked.connect(self.on_ok_clicked)
        controls.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_clicked)
        controls.button(QDialogButtonBox.Cancel).clicked.connect(self.on_cancel_clicked)
        main_layout.addWidget(controls)

    def on_ok_clicked(self):
        """Apply the configs and close the window."""
        values = self.config.validate_all(self.current_values)
        print(values)
        self.target.apply_config(values)
        self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        values = self.config.validate_all(self.current_values)
        print(values)
        self.target.apply_config(values)

    def on_cancel_clicked(self):
        """Discard any changes and close the window."""
        self.reject()

    def _make_field_widget(self, field: coi.Config.Field) -> QWidget:
        """Given a field, pick the best widget to configure it."""
        # pylint: disable = too-many-return-statements
        if field.choices is not None:
            widget = QComboBox()
            widget.addItems(str(choice) for choice in field.choices)
            widget.setCurrentText(str(field.value))
            widget.currentTextChanged.connect(self._make_setter(field))
            return widget
        if field.range is not None:
            # low, high = field.range
            # if isinstance(field.value, (int, np.integer)):
            #     widget = QSpinBox()
            # elif isinstance(field.value, (float, np.floating)):
            #     widget = QDoubleSpinBox()
            # else:
            #     raise KeyError(type(field.value))
            # widget.setValue(field.value)
            # widget.setRange(low, high)
            # widget.valueChanged.connect(self._make_setter(field))
            widget = QLineEdit(str(field.value))
            widget.setValidator(QDoubleValidator())
            widget.editingFinished.connect(self._make_setter(field, get=widget.text))
            return widget
        if isinstance(field.value, (bool, np.bool_)):
            widget = QCheckBox()
            widget.setChecked(field.value)
            widget.stateChanged.connect(self._make_setter(field))
            return widget
        if isinstance(field.value, (int, np.integer)):
            widget = QLineEdit(str(field.value))
            widget.setValidator(QIntValidator())
            widget.editingFinished.connect(self._make_setter(field, get=widget.text))
            return widget
        if isinstance(field.value, (float, np.floating)):
            widget = QLineEdit(str(field.value))
            widget.setValidator(QDoubleValidator())
            widget.editingFinished.connect(self._make_setter(field, get=widget.text))
            return widget
        if isinstance(field.value, str):
            widget = QLineEdit(str(field.value))
            widget.editingFinished.connect(self._make_setter(field, get=widget.text))
            return widget
        return QLabel(str(field.value))

    def _make_setter(
        self,
        field: coi.Config.Field,
        get: t.Optional[t.Callable[[], str]] = None,
    ):
        """Return a callback that can be used to update a field's value."""

        def _setter(value=None):
            if get is not None:
                value = get()
            if isinstance(field.value, (bool, np.bool_)):
                value = "checked" if value else ""
            else:
                value = str(value)
            self.current_values[field.dest] = value

        return _setter
