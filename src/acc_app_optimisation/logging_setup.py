# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Required code to get our logging setup off the ground."""

from __future__ import annotations

import contextlib
import io
import logging
import os
import tempfile
import typing as t
from logging import FileHandler, StreamHandler


class StreamToLogger(io.TextIOBase):
    """Fake file-like stream object that redirects writes to a logger.

    This class has been taken and adapted from `Stack Overflow`_ and
    `Ferry Boender`_.

    .. _`Stack Overflow`: https://stackoverflow.com/a/39215961
    .. _`Ferry Boender`: https://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        super().__init__()
        self.logger = logger
        self.level = level
        self.linebuf = ""

    def write(self, buf: str) -> int:
        num_written = len(buf)
        if self.linebuf:
            buf = self.linebuf + buf
        while buf:
            self.linebuf, newline, buf = buf.partition("\n")
            if newline:
                self.logger.log(self.level, self.linebuf.rstrip())
                self.linebuf = ""
        return num_written

    def flush(self) -> None:
        if self.linebuf:
            self.logger.log(self.level, self.linebuf.rstrip())
            self.linebuf = ""

    def __enter__(self) -> "StreamToLogger":
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass


@contextlib.contextmanager
def redirect_streams_to_logging() -> t.Iterator[None]:
    """Redirect stdout and stderr to loggers.

    This is a context manager that replaces stdout and stderr with dummy
    objects. These objects create log entries for every line that is
    printed to their respective stream. Outside of the context, the
    original stdout and stderr are restored.
    """
    stdout = t.cast(t.TextIO, StreamToLogger(logging.getLogger("stdout"), logging.INFO))
    stderr = t.cast(t.TextIO, StreamToLogger(logging.getLogger("stderr"), logging.INFO))
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        yield


def create_handler(filename: t.Union[None, str, os.PathLike]) -> StreamHandler:
    """Create a logging handler for the app.

    If *filename* is a file path, this simply creates a
    :class:`FileHandler` for this file. If *filename* is None, this
    creates a file in the temporary directory for this handler. If
    *filename* is the string ``"-"``, no file is creates and the
    returned :class:`StreamHandler` instead logs to standard error.
    """
    formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s:%(message)s")
    if filename == "-":
        handler = StreamHandler()
    elif filename is not None:
        # We need to do some hacky casts because I/O types are a mess.
        # StreamHandler(stderr) is a StreamHandler[t.TextIO], but
        # FileHandler("") is a StreamHandler[io.TextIOWrapper]. Despite
        # the compatible interface, MyPy cannot tell that the two are
        # related.
        handler = t.cast(StreamHandler, FileHandler(filename))
    else:
        # This is a bit tricky. We cannot pass a temporary filename to
        # FileHandler and let it open it due to TOC/TOU bugs. We cannot
        # use a StreamHandler because it doesn't close its file.
        # Thus, we create the temporary file ourselves and prevent the
        # FileHandler from opening it. Then, we feed the already-open
        # file to the handler and it is none the wiser. Eventually, the
        # handler will correctly close the file.
        file = tempfile.NamedTemporaryFile(  # pylint: disable=consider-using-with
            mode="w", prefix=__package__ + "_", suffix=".log", delete=False
        )
        handler = t.cast(StreamHandler, FileHandler(file.name, delay=True))
        handler.setStream(t.cast(io.TextIOWrapper, file))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    return handler
