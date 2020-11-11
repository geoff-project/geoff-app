import sys
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
            if field.help is not None:
                widget.setToolTip(field.help)
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
        print(values, file=sys.stderr)
        self.target.apply_config(values)
        self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        values = self.config.validate_all(self.current_values)
        print(values, file=sys.stderr)
        self.target.apply_config(values)

    def on_cancel_clicked(self):
        """Discard any changes and close the window."""
        self.reject()

    def _make_field_widget(self, field: coi.Config.Field) -> QWidget:
        """Given a field, pick the best widget to configure it."""
        # pylint: disable = too-many-return-statements
        if field.choices is not None:
            return _combobox(field, self.current_values)
        if field.range is not None:
            low, high = field.range
            if _is_float(field.value) and abs(high) / abs(low) > 1000.0:
                widget = _maybe_lineedit(field, self.current_values)
                assert widget is not None
                return widget
            return _spinbox(field, self.current_values)
        if _is_bool(field.value):
            return _checkbox(field, self.current_values)
        widget = _maybe_lineedit(field, self.current_values)
        if widget is not None:
            return widget
        return QLabel(str(field.value))


def _checkbox(field: coi.Config.Field, values: t.Dict[str, str]) -> QWidget:
    """Create a check box."""
    widget = QCheckBox()
    widget.setChecked(field.value)
    widget.stateChanged.connect(_make_setter(field, values))
    return widget


def _combobox(field: coi.Config.Field, values: t.Dict[str, str]) -> QWidget:
    """Create a combo box."""
    widget = QComboBox()
    widget.addItems(str(choice) for choice in field.choices)
    widget.setCurrentText(str(field.value))
    widget.currentTextChanged.connect(_make_setter(field, values))
    return widget


def _maybe_lineedit(
    field: coi.Config.Field, values: t.Dict[str, str]
) -> t.Optional[QWidget]:
    """Create a line edit that may contain strings, integers or floats."""
    widget = QLineEdit(str(field.value))
    if _is_int(field.value):
        widget.setValidator(QIntValidator())
    elif _is_float(field.value):
        widget.setValidator(QDoubleValidator())
    elif isinstance(field.value, str):
        pass
    else:
        return None
    widget.editingFinished.connect(_make_setter(field, values, get=widget.text))
    return widget


def _spinbox(field: coi.Config.Field, values: t.Dict[str, str]) -> QWidget:
    """Create either an integer or a floating-point spin box."""
    if _is_int(field.value):
        widget = QSpinBox()
    elif _is_float(field.value):
        widget = QDoubleSpinBox()
    else:
        raise KeyError(type(field.value))
    widget.setValue(field.value)
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    low, high = field.range
    decimals = 1 + max(2, np.ceil(-np.log10(low)), np.ceil(-np.log10(high)))
    widget.setDecimals(decimals)
    widget.setRange(low, high)
    widget.valueChanged.connect(_make_setter(field, values))
    return widget


def _make_setter(
    field: coi.Config.Field,
    values: t.Dict[str, str],
    get: t.Optional[t.Callable[[], str]] = None,
):
    """Return a callback that can be used to update a field's value."""
    if isinstance(field.value, (bool, np.bool_)):
        map_value = lambda v: "checked" if v else ""
    else:
        map_value = str

    if get is not None:

        def _setter():
            values[field.dest] = map_value(get())

    else:

        def _setter(value):
            values[field.dest] = map_value(value)

    return _setter


def _is_int(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy int."""
    return isinstance(value, (int, np.integer))


def _is_float(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy float."""
    return isinstance(value, (float, np.floating))


def _is_bool(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy bool."""
    return isinstance(value, (bool, np.bool_))
