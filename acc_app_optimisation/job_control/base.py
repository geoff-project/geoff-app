import abc
import typing as t

from cernml import coi
from PyQt5 import QtCore


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


class Job(QtCore.QRunnable):
    """Extension of :py:class:`QRunnable` with cancellation.

    This simply extends the :py:class:`QRunnable` interface with the
    ability to send *cancellation requests*.

    Attributes:
        token: The cancellation token used to communicate cancellation
            requests. It should only be used within :py:meth:`run()`. To
            send a cancellation request, use :py:meth:`cancel()`
            instead.
    """

    def __init__(self, token_source: coi.CancellationTokenSource) -> None:
        super().__init__()
        self._token_source = token_source

    def cancel(self) -> None:
        """Send a cancellation request to the job."""
        self._token_source.cancel()
