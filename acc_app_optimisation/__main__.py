#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import io
import logging
import sys
import typing as t

import pjlsa
from accwidgets.log_console import LogConsoleModel
from cernml import coi
from PyQt5 import QtWidgets

from acc_app_optimisation import __version__ as VERSION


class StreamToLogger(io.TextIOBase):
    """Fake file-like stream object that redirects writes to a logger.

    Class has been taken and adapted from `Stack Overflow`_ and `Ferry Boender`_.

    .. _`Stack Overflow`: https://stackoverflow.com/a/39215961
    .. _`Ferry Boender`: https://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        super().__init__()
        self.logger = logger
        self.level = level
        self.linebuf = ""

    def write(self, buf: t.AnyStr) -> int:
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())
        return len(buf)

    def flush(self) -> None:
        pass

    def __enter__(self) -> "StreamToLogger":
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass


def init_logging(capture_stdout: bool) -> LogConsoleModel:
    """Configure the `logging` module."""
    if capture_stdout:
        sys.stdout = StreamToLogger(  # type: ignore
            logging.getLogger("stdout"),
            logging.INFO,
        )
        sys.stderr = StreamToLogger(  # type: ignore
            logging.getLogger("stderr"),
            logging.WARNING,
        )
        handlers = []
    else:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel("INFO")
        stderr_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
        handlers = [stderr_handler]
    # No level-based filtering on the root logger; we leave that to the
    # log console and to the stderr_handler.
    logging.basicConfig(level="NOTSET", handlers=handlers)
    return LogConsoleModel()


def import_all(paths: t.Iterable[str], *, builtins: bool) -> t.Optional[Exception]:
    """Import all foreign packages as well as builtin envs.

    If an exception occurs at any point, it is caught, logged, and
    returned. This allows displaying the error in the GUI later.
    """
    # pylint: disable = import-outside-toplevel
    # pylint: disable=broad-except
    from acc_app_optimisation import foreign_imports

    try:
        for path in paths:
            foreign_imports.import_from_path(path)
    except Exception as exc:
        logging.error("exception during foreign imports", exc_info=True)
        return exc
    # Tricky ordering: foreign imports may override builtins.
    try:
        if builtins:
            from acc_app_optimisation.envs import builtin_envs as _
    except Exception as exc:
        logging.error("exception during builtin imports", exc_info=True)
        return exc
    return None


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="GeOFF: Generic Optimization Framework and Frontend"
    )
    parser.add_argument(
        "foreign_imports",
        nargs="*",
        type=str,
        metavar="PATH",
        help="Path to additional modules and packages that shall be "
        "imported; zip and wheel files are treated like directories; "
        "child modules may be imported by appending them, delimited "
        "with `::`",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the application version and exit",
    )
    parser.add_argument(
        "-m",
        "--machine",
        type=str,
        metavar="NAME",
        default="SPS",
        choices=[machine.name for machine in coi.Machine],
        help="The CERN machine to select initially (default: SPS)",
    )
    parser.add_argument(
        "-s",
        "--lsa-server",
        type=str,
        metavar="NAME",
        default="gpn",
        help="The LSA server to connect to (default: gpn)",
    )
    parser.add_argument(
        "--japc-no-set",
        action="store_true",
        default=False,
        help="Disable SET actions via JAPC; this is for debugging "
        "purposes; note that trims may still be sent to LSA; "
        "consider also passing -snext",
    )
    parser.add_argument(
        "--no-capture-stdout",
        dest="capture_stdout",
        action="store_false",
        default=True,
        help="Do not capture all standard output/error; this is "
        "for debugging crashes of the application",
    )
    parser.add_argument(
        "--builtins",
        action="store_true",
        default=True,
        dest="builtins",
        help="Load several built-in optimization problems (this is the default)",
    )
    parser.add_argument(
        "--no-builtins",
        action="store_false",
        dest="builtins",
        help="Disable loading of built-in optimization problems",
    )
    return parser


def main(argv: list) -> int:
    """Main function. Pass sys.argv."""
    args = get_parser().parse_args(argv[1:])
    if args.version:
        print(f"GeOFF v{VERSION}")
        return 0
    model = init_logging(args.capture_stdout)
    lsa = pjlsa.LSAClient(server=args.lsa_server)
    with lsa.java_api():
        # pylint: disable = import-outside-toplevel
        from acc_app_optimisation import gui

        import_error = import_all(args.foreign_imports, builtins=args.builtins)
        app = QtWidgets.QApplication(argv)
        app.setApplicationName(__package__)
        window = gui.MainWindow(
            initial_machine=coi.Machine[args.machine],
            lsa=lsa,
            model=model,
            japc_no_set=args.japc_no_set,
        )
        window.setWindowTitle(
            f"GeOFF v{VERSION} (LSA {args.lsa_server.upper()}"
            f'{", NO SET" if args.japc_no_set else ""})'
        )
        window.show()
        if import_error is not None:
            error_dialog = gui.excdialog.exception_dialog(
                import_error,
                title="Foreign imports",
                text="An error occurred while importing foreign packages",
                parent=window,
            )
            error_dialog.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
