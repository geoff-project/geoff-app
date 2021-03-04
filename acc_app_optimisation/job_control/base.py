import abc
import typing as t

from PyQt5 import QtCore


class Job(QtCore.QRunnable):
    """Abstract base class of things that can be started, stopped and reset."""

    can_reset: t.ClassVar[bool] = False

    def reset(self) -> None:
        """Evaluate the environment at x_0."""
        raise NotImplementedError()

    def cancel(self) -> None:
        """Cancel optimization at the next step."""
        raise NotImplementedError()


class JobFactory(abc.ABC):
    """Anything that can ultimately create a job.

    The factory should not launch the job itself. This is typically done
    by the caller by virtue of submitting it (as a QRunnable) to a
    threadpool.
    """

    @abc.abstractmethod
    def build_job(self) -> Job:
        raise NotImplementedError()
