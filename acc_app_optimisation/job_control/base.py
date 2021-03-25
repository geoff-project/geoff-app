import abc
import typing as t

from PyQt5 import QtCore


class JobCancelled(Exception):
    """The caller has cancelled this job and it should exit cleanly."""


class CannotBuildJob(Exception):
    """A job cannot be constructed due to missing arguments."""


class JobBuilder(abc.ABC):
    """Anything that can put together a background job.

    Background jobs are things that run while the GUI keeps updating.
    Examples are:

    - numerical optimization;
    - training an RL agent;
    - executing an RL agent.

    Putting together such a job requires to keep track of some state:
    the optimization problem to use, the optimizer, their configuration,
    etc. A JobBuilder tracks this state and, when the user clicks
    "Start", bundles it all into a single object that can be submitted
    to a threadpool.
    """

    @abc.abstractmethod
    def build_job(self) -> "Job":
        """Build a :py:class:`Job` ready for submission.

        Raises:
            CannotBuildJob: If any necessary argument is missing.
        """
        raise NotImplementedError()


class CancellationToken:
    """Communication channel to request job cancellation.

    This type is used to communicate from a job caller to the job that
    the job should exit as soon as possible. Jobs can do so either by
    regularly checking :py:attr:`cancelled` or calling
    :py:meth:`raise_if_cancelled` in their execution loop.

    Usage:

        >>> import time
        >>> def func(token: CancellationToken) -> None:
        ...     while True:
        ...         # Regularly check if we should exit.
        ...         token.raise_if_cancelled()
        ...         # Long-running job ...
        ...         time.sleep(0.1)
        >>> job = make_job(func)
        >>> pool = QtCore.QThreadPool.globalInstance()
        >>> pool.activeThreadCount()
        0
        >>> pool.start(job)
        >>> pool.activeThreadCount()
        1
        >>> job.cancel()
        >>> pool.waitForDone()
        >>> pool.activeThreadCount()
        0
    """

    __slots__ = ["_cancelled"]

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Request the job to exit."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """True if the job should exit."""
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        """Raise an exception if the job should exit.

        Raises:
            JobCancelled: If :py:attr:`cancelled` is True.
        """
        if self._cancelled:
            raise JobCancelled("job cancelled by user")


class Job(QtCore.QRunnable):
    """Extension of :py:class:`QRunnable` with cancellation.

    This simply extends the :py:class:`QRunnable` interface with the
    ability to send *cancellation requests* via a
    :py:class:`CancellationToken`. See its documentation for a usage
    example.

    Attributes:
        token: The cancellation token used to communicate cancellation
            requests. It should only be used within :py:meth:`run()`. To
            send a cancellation request, use :py:meth:`cancel()`
            instead.
    """

    __slots__ = ["token"]

    def __init__(self) -> None:
        super().__init__()
        self.cancellation_token = CancellationToken()

    def cancel(self) -> None:
        """Send a cancellation request to the job."""
        self.cancellation_token.cancel()
