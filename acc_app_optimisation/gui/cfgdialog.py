"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (
    QValidator,
    QDoubleValidator,
)
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QTabWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from cernml import coi, coi_funcs

from .cfgwidget import ConfigureWidget
from .excdialog import exception_dialog
from ..utils.split_words import split_words_and_spaces

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
        self, target: coi.Configurable, parent: t.Optional[QWidget] = None
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
        tab_widget = QTabWidget()
        if self._cfgform is not None:
            tab_widget.addTab(self._cfgform, "Configuration")
        if isinstance(target.unwrapped, coi_funcs.FunctionOptimizable):
            self.points_page = SkeletonPointsWidget(skeleton_points)
            tab_widget.addTab(self.points_page, "Skeleton points")
        else:
            self.points_page = None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self._controls)

    def on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        if self.points_page is not None:
            try:
                points = self.points_page.read_points()
            except ValueError as exc:
                _show_skeleton_points_failed(exc, parent=self)
                return
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_ok_clicked()

    def on_apply_clicked(self) -> None:
        """Apply the configs."""
        if self.points_page is not None:
            try:
                points = self.points_page.read_points()
            except ValueError as exc:
                _show_skeleton_points_failed(exc, parent=self)
                return
            LOG.info("new skeleton points: %s", points)
            self.skeleton_points_updated.emit(points)
        super().on_apply_clicked()


class SkeletonPointsWidget(QWidget):
    """The tab page presented to set skeleton points."""

    def __init__(
        self,
        points: t.Optional[t.Iterable[float]] = None,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        description = QLabel(
            "Enter skeleton points for optimization of LSA "
            "functions here. Enter one point in time for each "
            "point. Separate points with whitespace.",
            wordWrap=True,
        )
        initial_text = " ".join(map(str, [] if points is None else points))
        self.edit = QLineEdit(initial_text)
        self.edit.setValidator(WhitespaceDelimitedDoubleValidator(bottom=0.0))
        reset = QPushButton(
            "Reset",
            enabled=False,
            sizePolicy=QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed),
            clicked=lambda: self.edit.setText(initial_text),
        )
        self.edit.textChanged.connect(
            lambda text: reset.setEnabled(text != initial_text)
        )
        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addWidget(self.edit)
        layout.addWidget(reset, alignment=Qt.AlignRight)
        layout.addStretch(1)

    def read_points(self) -> np.ndarray:
        """Parse the skeleton points entered by the user."""
        locale = self.edit.validator().locale()
        points = set()
        for word in self.edit.text().split():
            point, success = locale.toDouble(word)
            if not success:
                raise ValueError(f"could not convert string to float: {word!r}")
            points.add(point)
        return np.array(sorted(points))


class WhitespaceDelimitedDoubleValidator(QDoubleValidator):
    """A `QValidator` that accepts a list of doubles, delimited by whitespace."""

    def validate(self, text: str, pos: int) -> t.Tuple[QValidator.State, str, int]:
        "Implementation of `QValidator.validate()`."
        parts = []
        # Start out with the best validator state: acceptable. As we go
        # through the numbers, the state can only get worse:
        # intermediate if the input looks like we caught the user
        # mid-typing, invalid if the input is flat-out wrong.
        final_state = QValidator.Acceptable
        # Tokenize the input, split it into pure whitespace and pure
        # floats.
        for token in split_words_and_spaces(text):
            if token.isspace():
                # Whitespace: If the cursor is behind this, we adjust
                # its position. If the cursor is before this, it cannot
                # be affected.
                part = " "
                if pos > token.begin:
                    pos += len(" ") - len(token.text)
                state = QValidator.Acceptable
            elif token.begin <= pos < token.end:
                # Word, cursor inside the word: take validator's
                # position changes into account.
                rel_pos = pos - token.begin
                state, part, rel_pos = super().validate(token.text, rel_pos)
                pos = token.begin + rel_pos
            else:
                # Word, cursor outside the word: Only adjust cursor
                # position if it is behind this word. If it is before,
                # this word cannot change its position.
                state, part, _ = super().validate(token.text, 0)
                if pos > token.begin:
                    pos += len(part) - len(token.text)
            parts.append(part)
            if state < final_state:
                final_state = state
        # Final adjustment: If we have leading or trailing whitespace,
        # OR an empty string, we're Intermediate at best, never
        # Acceptable.
        if not parts or parts[0].isspace() or parts[-1].isspace():
            if final_state == QValidator.Acceptable:
                final_state = QValidator.Intermediate
        return final_state, "".join(parts), pos


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
