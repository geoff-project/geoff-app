"""Provide :class:`DelayedComboBox`."""

import typing as t

from PyQt5 import QtCore, QtWidgets


class DelayedComboBox(QtWidgets.QComboBox):
    """A combo box with additional signals for delayed updates.

    Combo boxes are able to change their currently selected item in
    rapid succession. This happens for example when the user scrolls or
    them or uses the arrow keys while the combox has the focus.

    Each selection change emits the signals :attr:`currentTextChanged`,
    :attr:`currentIndexChanged` and :attr:`activated`. If a handler of
    these signals does an expensive computation (e.g. a network
    request), this blocks the event loop and gives the impression of a
    sluggish GUI.

    A delayed combo box provides two new signals
    (:attr:`stableTextChanged` and :attr:`stableIndexChanged`) that
    circumvent the issue. They are not emitted immediately, but only
    after a certain *timeout*. If the selection is changed again within
    the timeout, the timeout is extended and the signals are emitted
    only once: for the second change.

    This way, the user is able to scroll through the combo box at rapid
    speed and their selection only emits a signal once their selection
    has “stabilized” – hence the signal name.

    Aargs:
        parent: The parent widget, if any.
        timeout: The timeout in milliseconds. The stable signals are
            emitted after a selection change if no further selection
            change happens within the timeout.
    """

    stableTextChanged = QtCore.pyqtSignal(str)
    stableIndexChanged = QtCore.pyqtSignal(int)

    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        timeout: int = 100,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(parent, **kwargs)  # type: ignore
        self.currentIndexChanged.connect(self._kick_off_timer)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(timeout)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_stable_signal)

    def timeout(self) -> int:
        """Return the timeout in milliseconds."""
        return self._timer.interval()

    def setTimeout(self, msecs: int) -> None:  # pylint: disable = invalid-name
        """Change the timeout in milliseconds."""
        self._timer.setInterval(msecs)

    def _kick_off_timer(self) -> None:
        self._timer.start()

    def _emit_stable_signal(self) -> None:
        index = self.currentIndex()
        text = self.itemText(index)
        self.stableIndexChanged.emit(index)
        self.stableTextChanged.emit(text)
