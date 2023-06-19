# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

from __future__ import annotations

import abc
import contextlib
import sys
import traceback
import typing as t

from cernml.coi import cancellation
from PyQt5 import QtCore

if t.TYPE_CHECKING:
    # pylint: disable = unused-import
    from logging import Logger


class BenignCancelledError(cancellation.CancelledError):
    """Cancellation error that we raise, not the optimization problem."""


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
    def build_job(self) -> Job:
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

    def __init__(self, token_source: cancellation.TokenSource) -> None:
        super().__init__()
        self._token_source = token_source

    def cancel(self) -> None:
        """Send a cancellation request to the job."""
        self._token_source.cancel()


@contextlib.contextmanager
def catching_exceptions(
    name: str,
    logger: Logger,
    *,
    token_source: cancellation.TokenSource,
    on_success: t.Callable[[], None],
    on_cancel: t.Callable[[], None],
    on_exception: t.Callable[[traceback.TracebackException], None],
) -> t.Iterator[None]:
    """Context manager that turns exceptions into callbacks.

    This is used by jobs to catch *all* exceptions and emit them via Qt
    signals instead. This is necessary because exiting a thread via
    exception takes down the entire application.

    This also takes care of most of the token source lifecycle
    management for us.

    Args:
        name: A string identifying the process happening in this
            context. This appears  only in logging messages.
        logger: The logger where the outcome (success, cancellation,
            exception) should be logged.
        token_source: A token source that should be reset if possible.
        on_success: Called if the context is exited without exception.
        on_cancel: Called if the context is exited via
            :exc:`~cancellation.CancelledError`.
        on_exception: Called if the context is left through *any* other
            exception. The argument is a
            :exc:`~traceback.TracebackException` with as much
            information as possible without including local variables.
    """
    # pylint: disable = bare-except
    try:
        yield
        logger.info(f"finished {name}")
        on_success()
        # Catch weird race conditions: If we successfully run through and a
        # cancellation arrives _just_ after, we automatically complete it.
        if token_source.token.cancellation_requested:
            token_source.token.complete_cancellation()
            token_source.reset_cancellation()
    except BenignCancelledError:
        logger.info(f"cancelled {name} successfully!")
        token_source.token.complete_cancellation()
        token_source.reset_cancellation()
        on_cancel()
    except cancellation.CancelledError:
        if token_source.can_reset_cancellation:
            logger.info(f"cancelled {name} successfully")
            token_source.reset_cancellation()
        else:
            logger.warning(
                "the optimizable never called "
                "`cancellation_token.complete_canellation()`"
            )
            logger.warning(
                "this means we can't be sure it's still in a good state to be re-used"
            )
            logger.warning(
                "if this is an issue, please contact the maintainer about it"
            )
            logger.warning(f"cancelled {name} incompletely!")
        on_cancel()
    except:
        logger.error(f"aborted {name}", exc_info=True)
        on_exception(traceback.TracebackException(*sys.exc_info()))
