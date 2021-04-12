#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import logging
import sys

import pjlsa
from accwidgets.log_console import LogConsoleModel
from cernml import coi
from PyQt5 import QtWidgets


class StreamToLogger:
    """Fake file-like stream object that redirects writes to a logger.

    Class has been taken and adapted from `Stack Overflow`_ and `Ferry Boender`_.

    .. _`Stack Overflow`: https://stackoverflow.com/a/39215961
    .. _`Ferry Boender`: https://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger = logger
        self.level = level
        self.linebuf = ""

    def write(self, buf: str) -> None:
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self) -> None:
        pass


def init_logging(capture_stdout: bool) -> LogConsoleModel:
    """Configure the `logging` module."""
    if capture_stdout:
        sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
        sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.WARNING)
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
    model = init_logging(args.capture_stdout)
    lsa = pjlsa.LSAClient(server=args.lsa_server)
    with lsa.java_api():
        # pylint: disable = import-outside-toplevel
        from acc_app_optimisation import __version__ as version
        from acc_app_optimisation import foreign_imports, gui

        foreign_imports.import_all(args.foreign_imports)

        # Tricky ordering: foreign imports may override builtins.
        if args.builtins:
            from acc_app_optimisation.envs import builtin_envs as _

        app = QtWidgets.QApplication(argv)
        window = gui.MainWindow(
            initial_machine=coi.Machine[args.machine],
            lsa=lsa,
            model=model,
            japc_no_set=args.japc_no_set,
        )
        window.setWindowTitle(
            f"GeOFF v{version} (LSA {args.lsa_server.upper()}"
            f'{", NO SET" if args.japc_no_set else ""})'
        )
        window.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
