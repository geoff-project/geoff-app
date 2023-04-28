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

    Warning:
        The widget's delayed reaction affects even `setCurrentIndex()`
        and `setCurrentText()`. When changing the current item through
        these methods, any slot connected to `stableIndexChanged` or
        `stableTextChanged` will only be called after the given timeout.

        If you want to change the current combo box item and immediately
        propagate the change through your application, use
        `setStableIndex()` or `setStableText()` instead.

    Args:
        parent: The parent widget, if any.
        timeout: The timeout in milliseconds. The stable signals are
            emitted after a selection change if no further selection
            change happens within the timeout.
    """

    # pylint: disable = invalid-name

    stableTextChanged = QtCore.pyqtSignal(str)
    stableIndexChanged = QtCore.pyqtSignal(int)

    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        interval: int = 100,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.currentIndexChanged.connect(self._kick_off_timer)
        self._interval = interval
        self._timer = QtCore.QTimer()
        self._timer.setInterval(interval)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_stable_signal)

    def interval(self) -> int:
        """Return the timeout interval in milliseconds."""
        return self._interval

    def setInterval(self, msec: int) -> None:
        """Change the timeout interval in milliseconds."""
        self._interval = msec
        self._timer.setInterval(msec)

    def setStableIndex(self, index: int) -> None:
        """Set the current index and immediately stabilize.

        This stops any delayed reactions that might be running in the
        background and immediately emits the usual signals
        (`indexChanged`, `textChanged`, `stableIndexChanged`,
        `stableTextChanged`).
        """
        # If we call `setCurrentIndex()` without actually changing the
        # index, no signal is emitted and `self._kick_off_timer()` doesn't
        # get called, which makes everything very messy.
        current = self.currentIndex()
        if index != current:
            self._timer.setInterval(0)
            # This implicitly calls `self._kick_off_timer()`.
            self.setCurrentIndex(index)

    def setStableText(self, text: str) -> None:
        """Set the current text and immediately stabilize.

        This stops any delayed reactions that might be running in the
        background and immediately emits the usual signals
        (`indexChanged`, `textChanged`, `stableIndexChanged`,
        `stableTextChanged`).
        """
        # If we call `setCurrentText()` without actually changing the
        # index, no signal is emitted and `self._kick_off_timer()` doesn't
        # get called, which makes everything very messy.
        current = self.currentText()
        if current != text:
            self._timer.setInterval(0)
            # This implicitly calls `self._kick_off_timer()`.
            self.setCurrentText(text)

    def _kick_off_timer(self) -> None:
        self._timer.start()

    def _emit_stable_signal(self) -> None:
        # Reset the interval if `self.setStable*()` set it to zero.
        self._timer.setInterval(self._interval)
        # Only access `self.current*()` once to avoid race conditions.
        index = self.currentIndex()
        text = self.itemText(index)
        self.stableIndexChanged.emit(index)
        self.stableTextChanged.emit(text)
