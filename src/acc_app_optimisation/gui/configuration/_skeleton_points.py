# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import typing as t

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from ...utils.split_words import split_words_and_spaces


class BaseSkeletonPointsWidget(QtWidgets.QWidget):
    """Base class of `SkeletonPointsViewWidget` and `SkeletonPointsEditWidget`."""

    # pylint: disable = invalid-name

    def skeletonPoints(self) -> t.Tuple[float, ...]:
        """Parse the skeleton points entered by the user."""
        raise NotImplementedError()

    def setSkeletonPoints(self, points: t.Tuple[float, ...]) -> None:
        """Update the control to display the given points."""
        raise NotImplementedError()


class SkeletonPointsViewWidget(BaseSkeletonPointsWidget):
    """The tab page presented to view unmodifiable skeleton points."""

    def __init__(
        self,
        points: t.Tuple[float, ...],
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        description = QtWidgets.QLabel(
            "This optimization problem has signaled that it manages "
            "the skeleton points itself. You can preview them below. "
            "Note that this view only gets updated if you click Apply "
            "to save the current configuration."
        )
        description.setWordWrap(True)
        self._points = tuple(sorted(points))
        self.edit = QtWidgets.QLineEdit(self._get_points_text())
        self.edit.setReadOnly(True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(description)
        layout.addWidget(self.edit)
        layout.addStretch(1)

    def showEvent(self, _: QtGui.QShowEvent) -> None:
        """Pre-select the line edit upon becoming visible."""
        # pylint: disable = invalid-name
        self.edit.setFocus()

    def skeletonPoints(self) -> t.Tuple[float, ...]:
        """Parse the skeleton points entered by the user."""
        return self._points

    def setSkeletonPoints(self, points: t.Tuple[float, ...]) -> None:
        """Update the control to display the given points."""
        self._points = tuple(sorted(points))
        self.edit.setText(self._get_points_text())

    def _get_points_text(self) -> str:
        return " ".join(map(str, self._points))


class SkeletonPointsEditWidget(BaseSkeletonPointsWidget):
    """The tab page presented to change skeleton points."""

    # pylint: disable = invalid-name

    def __init__(
        self,
        points: t.Tuple[float, ...],
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        description = QtWidgets.QLabel(
            "Enter skeleton points for optimization of LSA "
            "functions here. Enter one point in time for each "
            "point. Separate points with whitespace.",
        )
        description.setWordWrap(True)
        initial_text = " ".join(str(point) for point in points)
        validator = WhitespaceDelimitedDoubleValidator()
        validator.setBottom(0.0)
        self.edit = QtWidgets.QLineEdit(initial_text)
        self.edit.setValidator(validator)
        reset = QtWidgets.QPushButton("Reset")
        reset.setEnabled(False)
        reset.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        reset.clicked.connect(lambda: self.edit.setText(initial_text))
        self.edit.textChanged.connect(
            lambda text: reset.setEnabled(text != initial_text)
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(description)
        layout.addWidget(self.edit)
        layout.addWidget(reset, alignment=Qt.AlignRight)
        layout.addStretch(1)

    def showEvent(self, _: QtGui.QShowEvent) -> None:
        """Pre-select the line edit upon becoming visible."""
        # pylint: disable = invalid-name
        self.edit.setFocus()

    def skeletonPoints(self) -> t.Tuple[float, ...]:
        """Parse the skeleton points entered by the user."""
        locale = self.edit.validator().locale()
        points: t.MutableSet[float] = set()
        for word in self.edit.text().split():
            point, success = locale.toDouble(word)
            if not success:
                raise ValueError(f"could not convert string to float: {word!r}")
            points.add(point)
        return tuple(sorted(points))

    def setSkeletonPoints(self, points: t.Tuple[float, ...]) -> None:
        """Update the control to display the given points."""
        self.edit.setText(" ".join(str(point) for point in points))


class WhitespaceDelimitedDoubleValidator(QtGui.QDoubleValidator):
    """A `QValidator` that accepts a list of doubles, delimited by whitespace."""

    def validate(
        self, text: str, pos: int
    ) -> t.Tuple[QtGui.QValidator.State, str, int]:
        "Implementation of `QValidator.validate()`."
        parts = []
        # Start out with the best validator state: acceptable. As we go
        # through the numbers, the state can only get worse:
        # intermediate if the input looks like we caught the user
        # mid-typing, invalid if the input is flat-out wrong.
        final_state = QtGui.QValidator.Acceptable
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
                state = QtGui.QValidator.Acceptable
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
            final_state = min(state, final_state)
        # Final adjustment: If the text consists of nothing _but_
        # whitespace, we just discard it.
        if all(part.isspace() for part in parts):
            parts.clear()
        return final_state, "".join(parts), pos
