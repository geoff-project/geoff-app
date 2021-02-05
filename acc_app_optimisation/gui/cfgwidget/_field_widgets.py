"""Helpers to concisely create form widgets."""

import typing as t

import numpy as np
from cernml.coi import Config
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from . import _type_utils

UnparsedDict = t.Dict[str, str]


def make_field_widget(field: Config.Field, values: UnparsedDict) -> QWidget:
    """Given a field, pick the best widget to configure it."""
    # pylint: disable = too-many-return-statements
    if field.choices is not None:
        return combobox(field, values)
    if field.range is not None:
        low, high = field.range
        if _type_utils.is_float(field.value) and _type_utils.is_range_huge(low, high):
            widget = maybe_lineedit(field, values)
            assert widget is not None
            return widget
        return spinbox(field, values)
    if _type_utils.is_bool(field.value):
        return checkbox(field, values)
    widget = maybe_lineedit(field, values)
    if widget is not None:
        return widget
    return QLabel(str(field.value))


def combobox(field: Config.Field, values: UnparsedDict) -> QWidget:
    """Create a combo box."""
    widget = QComboBox()
    widget.addItems(str(choice) for choice in field.choices)
    widget.setCurrentText(str(field.value))
    widget.currentTextChanged.connect(make_setter(field, values))
    return widget


def maybe_lineedit(field: Config.Field, values: UnparsedDict) -> t.Optional[QWidget]:
    """Create a line edit that may contain strings, integers or floats."""
    widget = QLineEdit(str(field.value))
    if _type_utils.is_int(field.value):
        widget.setValidator(QIntValidator())
    elif _type_utils.is_float(field.value):
        widget.setValidator(QDoubleValidator())
    elif isinstance(field.value, str):
        pass
    else:
        return None
    widget.editingFinished.connect(make_setter(field, values, get=widget.text))
    return widget


def spinbox(field: Config.Field, values: UnparsedDict) -> QWidget:
    """Create either an integer or a floating-point spin box."""
    low, high = field.range
    if _type_utils.is_int(field.value):
        widget = QSpinBox()
        # Ensure that the range limits are valid integers.
        low = np.clip(np.floor(low), -(2 << 30), (2 << 30) - 1)
        high = np.clip(np.ceil(high), -(2 << 30), (2 << 30) - 1)
    elif _type_utils.is_float(field.value):
        widget = QDoubleSpinBox()
        decimals = _type_utils.guess_decimals(low, high)
        widget.setDecimals(decimals)
    else:
        raise KeyError(type(field.value))
    widget.setValue(field.value)
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    widget.setRange(low, high)
    widget.valueChanged.connect(make_setter(field, values))
    return widget


def checkbox(field: Config.Field, values: UnparsedDict) -> QWidget:
    """Create a check box."""
    widget = QCheckBox()
    widget.setChecked(field.value)
    widget.stateChanged.connect(make_setter(field, values))
    return widget


def make_setter(
    field: Config.Field,
    values: UnparsedDict,
    get: t.Optional[t.Callable[[], str]] = None,
) -> t.Callable[..., None]:
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
