import typing as t

import numpy as np
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from ...utils.split_words import split_words_and_spaces


class SkeletonPointsWidget(QtWidgets.QWidget):
    """The tab page presented to set skeleton points."""

    def __init__(
        self, points: np.ndarray, parent: t.Optional[QtWidgets.QWidget] = None
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

    def showEvent(self, _: QtGui.QShowEvent) -> None:  # pylint: disable = invalid-name
        """Pre-select the line edit upon becoming visible."""
        self.edit.setFocus()

    def read_points(self) -> np.ndarray:
        """Parse the skeleton points entered by the user."""
        locale = self.edit.validator().locale()
        points: t.MutableSet[float] = set()
        for word in self.edit.text().split():
            point, success = locale.toDouble(word)
            if not success:
                raise ValueError(f"could not convert string to float: {word!r}")
            points.add(point)
        return np.array(sorted(points))


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
            if state < final_state:
                final_state = state
        # Final adjustment: If the text consists of nothing _but_
        # whitespace, we just discard it.
        if all(part.isspace() for part in parts):
            parts.clear()
        return final_state, "".join(parts), pos
