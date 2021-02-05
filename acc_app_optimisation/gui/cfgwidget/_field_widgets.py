"""Helpers to concisely create form widgets."""

import typing as t

import numpy as np
from cernml.coi import Config
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from . import _type_utils as _tu

UnparsedDict = t.Dict[str, str]


def make_field_widget(field: Config.Field, values: UnparsedDict) -> QWidget:
    """Given a field, pick the best widget to configure it."""
    # pylint: disable = too-many-return-statements
    setter = itemsetter(values, field.dest)
    # Boolean fields always ignore range and choices.
    if _tu.is_bool(field.value):
        checkbox = make_checkbox(bool(field.value))
        # `_state` is an integer with non-obvious semantics. Ignore it
        # and use the obvious `isChecked` instead.
        checkbox.stateChanged.connect(
            lambda _state: setter(_tu.str_boolsafe(checkbox.isChecked()))
        )
        return checkbox
    if field.choices is not None:
        combobox = make_combobox(str(field.value), map(str, field.choices))
        combobox.currentTextChanged.connect(setter)
        return combobox
    if field.range is not None:
        # Only make a spin box under when it makes sense. Otherwise,
        # fall through to the line edit case.
        if _tu.is_int(field.value):
            spinbox = make_int_spinbox(field.value, field.range)
            spinbox.valueChanged.connect(setter)
            return spinbox
        if _tu.is_float(field.value) and not _tu.is_range_huge(*field.range):
            spinbox = make_double_spinbox(field.value, field.range)
            spinbox.valueChanged.connect(setter)
            return spinbox
    lineedit = make_lineedit(field.value)
    lineedit.editingFinished.connect(lambda: setter(lineedit.text()))
    return lineedit


def make_combobox(initial: str, choices: t.Iterable[str]) -> QComboBox:
    """Create a combo box."""
    widget = QComboBox()
    widget.addItems(choices)
    widget.setCurrentText(initial)
    return widget


def make_lineedit(value: t.Any) -> QLineEdit:
    """Create a line edit."""
    widget = QLineEdit(str(value))
    if _tu.is_int(value):
        widget.setValidator(QIntValidator())
    elif _tu.is_float(value):
        widget.setValidator(QDoubleValidator())
    else:
        pass
    return widget


def make_double_spinbox(value: float, range_: t.Tuple[float, float]) -> QDoubleSpinBox:
    """Create either an integer or a floating-point spin box."""
    low, high = range_
    widget = QDoubleSpinBox()
    widget.setDecimals(_tu.guess_decimals(low, high))
    widget.setValue(value)
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    widget.setRange(low, high)
    return widget


def make_int_spinbox(value: int, range_: t.Tuple[int, int]) -> QSpinBox:
    """Create either an integer or a floating-point spin box."""
    # Ensure that the range limits are valid integers.
    low, high = range_
    low = np.clip(np.floor(low), -(2 << 30), (2 << 30) - 1)
    high = np.clip(np.ceil(high), -(2 << 30), (2 << 30) - 1)
    widget = QSpinBox()
    widget.setValue(value)
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    widget.setRange(low, high)
    return widget


def make_checkbox(checked: bool) -> QCheckBox:
    """Create a check box."""
    widget = QCheckBox()
    widget.setChecked(checked)
    return widget


K = t.TypeVar("K")  # pylint: disable=invalid-name
V = t.TypeVar("V")  # pylint: disable=invalid-name


def itemsetter(mapping: t.MutableMapping[K, V], key: K) -> t.Callable[[V], None]:
    """Return a callable that takes ``values`` and runs ``mapping[key] = value``."""

    def _setter(value: V) -> None:
        """Run ``{mapping}[{key}] = value``."""
        mapping[key] = value

    assert _setter.__doc__ is not None
    _setter.__doc__ = _setter.__doc__.format(**locals())
    return _setter
