"""Helpers to concisely create form widgets."""

import os
import typing as t
from pathlib import Path

import numpy as np
from cernml.coi import Config
from PyQt5 import QtCore, QtGui, QtWidgets

from ..file_selector import FileSelector
from . import _type_utils as _tu

UnparsedDict = t.Dict[str, str]


def make_field_widget(field: Config.Field, values: UnparsedDict) -> QtWidgets.QWidget:
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
    # Path-like fields take precedence over range and choices.
    if isinstance(field.value, os.PathLike):
        selector = make_file_selector(field.value, field.choices)
        selector.fileChanged.connect(setter)
        return selector
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
            double_spinbox = make_double_spinbox(field.value, field.range)
            double_spinbox.valueChanged.connect(setter)
            return double_spinbox
    lineedit = make_lineedit(field.value)
    lineedit.editingFinished.connect(lambda: setter(lineedit.text()))
    return lineedit


def make_file_selector(
    value: os.PathLike, choices: t.Optional[t.Iterable[str]]
) -> FileSelector:
    """Create a button that opens a file selection widget."""
    if value == Path():
        config_dir = ensure_config_dir()
        widget = FileSelector("", dialogDirectory=config_dir)
    else:
        widget = FileSelector(value)
    if choices:
        filters = list(choices)
        if any("*" in filter_ for filter_ in filters):
            widget.setNameFilters(filters)
        else:
            widget.setMimeTypeFilters(filters)
    return widget


def make_combobox(initial: str, choices: t.Iterable[str]) -> QtWidgets.QComboBox:
    """Create a combo box."""
    widget = QtWidgets.QComboBox()
    widget.addItems(choices)
    widget.setCurrentText(initial)
    return widget


def make_lineedit(value: t.Any) -> QtWidgets.QLineEdit:
    """Create a line edit."""
    widget = QtWidgets.QLineEdit(str(value))
    if _tu.is_int(value):
        widget.setValidator(QtGui.QIntValidator())
    elif _tu.is_float(value):
        widget.setValidator(QtGui.QDoubleValidator())
    else:
        pass
    return widget


def make_double_spinbox(
    value: float, range_: t.Tuple[float, float]
) -> QtWidgets.QDoubleSpinBox:
    """Create either an integer or a floating-point spin box."""
    low, high = range_
    widget = QtWidgets.QDoubleSpinBox()
    widget.setDecimals(_tu.guess_decimals(low, high))
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def make_int_spinbox(value: int, range_: t.Tuple[int, int]) -> QtWidgets.QSpinBox:
    """Create either an integer or a floating-point spin box."""
    # Ensure that the range limits are valid integers.
    low, high = range_
    low = np.clip(np.floor(low), -(2 << 30), (2 << 30) - 1)
    high = np.clip(np.ceil(high), -(2 << 30), (2 << 30) - 1)
    widget = QtWidgets.QSpinBox()
    widget.setStepType(widget.AdaptiveDecimalStepType)
    widget.setGroupSeparatorShown(True)
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def make_checkbox(checked: bool) -> QtWidgets.QCheckBox:
    """Create a check box."""
    widget = QtWidgets.QCheckBox()
    widget.setChecked(checked)
    return widget


K = t.TypeVar("K")  # pylint: disable=invalid-name
V = t.TypeVar("V")  # pylint: disable=invalid-name


def itemsetter(mapping: t.MutableMapping[K, V], key: K) -> t.Callable[[V], None]:
    """Return a callable that takes ``value`` and runs ``mapping[key] = value``."""

    def _setter(value: V) -> None:
        """Run ``{mapping}[{key}] = value``."""
        mapping[key] = value

    assert _setter.__doc__ is not None
    _setter.__doc__ = _setter.__doc__.format(**locals())
    return _setter


def ensure_config_dir() -> t.Optional[Path]:
    """Find/Create the directory for application configuration files.

    This uses the first configuration directory in the list of known
    directories. If it doesn't exist yet, it is created.
    """
    all_config_dirs = QtCore.QStandardPaths.standardLocations(
        QtCore.QStandardPaths.AppConfigLocation
    )
    if not all_config_dirs:
        return None
    config_dir = Path(all_config_dirs[0])
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
