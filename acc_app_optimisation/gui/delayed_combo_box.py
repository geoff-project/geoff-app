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
        timeout: int = 100,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.currentIndexChanged.connect(self._kick_off_timer)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(timeout)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_stable_signal)
        # Use this to block the timer from being started when
        # setStable*() is called. In case of multi-threaded access, this
        # is an integer instead of a boolean flag. Yes, this is
        # paranoid.
        self._timer_skip_count = 0

    def timeout(self) -> int:
        """Return the timeout in milliseconds."""
        return self._timer.interval()

    def setTimeout(self, msecs: int) -> None:
        """Change the timeout in milliseconds."""
        self._timer.setInterval(msecs)

    def setStableIndex(self, index: int) -> None:
        """Set the current index and immediately stabilize.

        This stops any delayed reactions that might be running in the
        background and immediately emits the usual signals
        (`indexChanged`, `textChanged`, `stableIndexChanged`,
        `stableTextChanged`).
        """
        self._timer.stop()
        self._timer_skip_count += 1
        self.setCurrentIndex(index)
        self._emit_stable_signal()

    def setStableText(self, text: str) -> None:
        """Set the current text and immediately stabilize.

        This stops any delayed reactions that might be running in the
        background and immediately emits the usual signals
        (`indexChanged`, `textChanged`, `stableIndexChanged`,
        `stableTextChanged`).
        """
        self._timer.stop()
        self._timer_skip_count += 1
        self.setCurrentText(text)
        self._emit_stable_signal()

    def _kick_off_timer(self) -> None:
        if self._timer_skip_count:
            self._timer_skip_count -= 1
        else:
            self._timer.start()

    def _emit_stable_signal(self) -> None:
        index = self.currentIndex()
        text = self.itemText(index)
        self.stableIndexChanged.emit(index)
        self.stableTextChanged.emit(text)
