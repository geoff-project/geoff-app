import logging
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
    QTabWidget,
)
from PyQt5.QtGui import (
    QIntValidator,
    QDoubleValidator,
)

from cernml import coi

LOG = logging.getLogger(__name__)


class ConfigureWidget(QWidget):
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
        params_layout = QFormLayout(self)
        for field in self.config.fields():
            label = QLabel(field.label)
            widget = self._make_field_widget(field)
            if field.help is not None:
                widget.setToolTip(field.help)
            params_layout.addRow(label, widget)

    def _make_field_widget(self, field: coi.Config.Field) -> QWidget:
        """Given a field, pick the best widget to configure it."""
        # pylint: disable = too-many-return-statements
        if field.choices is not None:
            return _combobox(field, self.current_values)
        if field.range is not None:
            low, high = field.range
            if _is_float(field.value) and _is_range_huge(low, high):
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


class ConfigureDialog(QDialog):
    """Qt dialog that allows configuring an environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(self, target: coi.Configurable, parent=None):
        super().__init__(parent)
        self.cfg_widget = ConfigureWidget(target)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.cfg_widget)
        controls = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        controls.button(QDialogButtonBox.Ok).clicked.connect(self.on_ok_clicked)
        controls.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_clicked)
        controls.button(QDialogButtonBox.Cancel).clicked.connect(self.on_cancel_clicked)
        main_layout.addWidget(controls)

    def on_ok_clicked(self):
        """Apply the configs and close the window."""
        values = self.cfg_widget.config.validate_all(self.cfg_widget.current_values)
        LOG.info("Ok clicked, new config: %s", values)
        self.cfg_widget.target.apply_config(values)
        self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        values = self.cfg_widget.config.validate_all(self.cfg_widget.current_values)
        LOG.info("Apply clicked, new config: %s", values)
        self.cfg_widget.target.apply_config(values)

    def on_cancel_clicked(self):
        """Discard any changes and close the window."""
        self.reject()


class FunctionConfigureDialog(QDialog):
    """Qt dialog that allows configuring a FunctionOptimizable.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(self, target: coi.Configurable, parent=None):
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
        controls.button(QDialogButtonBox.Cancel).clicked.connect(self.on_cancel_clicked)
        main_layout.addWidget(controls)

    def on_ok_clicked(self):
        """Apply the configs and close the window."""
        if self.cfg_widget:
            values = self.cfg_widget.config.validate_all(self.cfg_widget.current_values)
            LOG.info("Ok clicked, new config: %s", values)
            self.cfg_widget.target.apply_config(values)
        self.accept()

    def on_apply_clicked(self):
        """Apply the configs."""
        if self.cfg_widget:
            values = self.cfg_widget.config.validate_all(self.cfg_widget.current_values)
            LOG.info("Apply clicked, new config: %s", values)
        self.cfg_widget.target.apply_config(values)

    def on_cancel_clicked(self):
        """Discard any changes and close the window."""
        self.reject()


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
    low, high = field.range
    if _is_int(field.value):
        widget = QSpinBox()
        # Ensure that the range limits are valid integers.
        low = np.clip(np.floor(low), -(2 << 30), (2 << 30) - 1)
        high = np.clip(np.ceil(high), -(2 << 30), (2 << 30) - 1)
    elif _is_float(field.value):
        widget = QDoubleSpinBox()
        decimals = _guess_decimals(low, high)
        widget.setDecimals(decimals)
    else:
        raise KeyError(type(field.value))
    widget.setValue(field.value)
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
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


def _guess_decimals(low: float, high: float) -> int:
    """Guess how many decimals to show in a double spin box."""
    absmax = max(abs(high), abs(low))
    absmin = min(abs(high), abs(low))
    mindigits = np.ceil(-np.log10(absmin)) if absmin else 0
    maxdigits = np.ceil(-np.log10(absmax)) if absmax else 0
    return 1 + int(max(2, maxdigits, mindigits))


def _is_range_huge(low: float, high: float) -> bool:
    """Return True if the range covers several orders of magnitude."""
    absmax = max(abs(high), abs(low))
    absmin = min(abs(high), abs(low))
    if absmin == 0.0:
        absmax, absmin = (absmax, 1.0) if absmax > 1.0 else (1.0, absmax)
    return absmax / absmin > 1e3


def _is_int(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy int."""
    return isinstance(value, (int, np.integer))


def _is_float(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy float."""
    return isinstance(value, (float, np.floating))


def _is_bool(value: t.Any) -> bool:
    """Return True if `value` is a Python or NumPy bool."""
    return isinstance(value, (bool, np.bool_))
