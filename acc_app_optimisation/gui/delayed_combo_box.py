"""Provide :class:`DelayedComboBox`."""

import typing as t

from PyQt5 import QtCore, QtWidgets

from .task import ThreadPoolTask


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
        self.last_timer = QtCore.QDeadlineTimer()
        self._timeout = timeout

    def timeout(self) -> int:
        """Return the timeout in milliseconds."""
        return self._timeout

    def setTimeout(self, msecs: int) -> None:  # pylint: disable = invalid-name
        """Change the timeout in milliseconds."""
        self._timeout = msecs

    def _kick_off_timer(self) -> None:
        # If the last timer hasn't expired yet, let it keep running.
        # This avoids creating more than one background task at a time.
        if not self.last_timer.hasExpired():
            self.last_timer.setRemainingTime(self._timeout)
            return
        # Avoid a race condition: Though the old timer is expired, the
        # worker thread might still be running (and check the timer
        # later). Create a new timer to avoid keeping the old worker
        # alive.
        self.last_timer = QtCore.QDeadlineTimer()
        # Do not use the constructor `QDeadlineTimer(msecs)`. For some
        # reason, the resulting timer is always expired, contrary to
        # documentation. Tested on PyQt 5.12.
        self.last_timer.setRemainingTime(self._timeout)

        def wait_and_emit(timer: QtCore.QDeadlineTimer) -> None:
            """Background task that eventually emits our signals."""
            # Wait until the timer expires. We can't do a proper wait,
            # since we don't have an event loop, so sleeping for the
            # expected amount of time will have to suffice. Ensure to
            # perform the has-expired check only once per iteration.
            while True:
                remaining = timer.remainingTime()
                if remaining:
                    QtCore.QThread.msleep(remaining)
                else:
                    break
            # Make sure to use the latest text/index when emitting the
            # signal. Whatever has been passed to the original signal
            # handler is likely outdated.
            self.stableTextChanged.emit(self.currentText())
            self.stableIndexChanged.emit(self.currentIndex())

        # Send the waiting task to the threadpool to avoid blocking the
        # event loop.
        pool = QtCore.QThreadPool.globalInstance()
        pool.start(ThreadPoolTask(wait_and_emit, self.last_timer))
