import abc
import typing as t

from PyQt5 import QtCore


class Job(QtCore.QRunnable):
    """Abstract base class of background jobs that can be cancelled."""

    def cancel(self) -> None:
        """Cancel optimization at the next step."""
        raise NotImplementedError()


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
    def build_job(self) -> Job:
        raise NotImplementedError()
