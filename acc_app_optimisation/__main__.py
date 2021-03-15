#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import logging
import sys

import pjlsa
from accwidgets.log_console import LogConsoleModel
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


def init_logging() -> LogConsoleModel:
    """Configure the `logging` module."""
    sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.WARNING)
    # No level-based filtering, no output. Instead, we let the
    # LogConsole handle filtering and output for us.
    logging.basicConfig(level="NOTSET", handlers=[])
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
    model = init_logging()
    args = get_parser().parse_args(argv[1:])
    lsa = pjlsa.LSAClient(server=args.lsa_server)
    with lsa.java_api():
        # pylint: disable = import-outside-toplevel
        from acc_app_optimisation import __version__ as version
        from acc_app_optimisation import foreign_imports, gui

        for path in args.foreign_imports:
            foreign_imports.import_from_path(path)

        # Tricky ordering: foreign imports may override builtins.
        if args.builtins:
            from acc_app_optimisation.envs import builtin_envs as _

        app = QtWidgets.QApplication(argv)
        window = gui.MainWindow(lsa=lsa, model=model, japc_no_set=args.japc_no_set)
        window.setWindowTitle(
            f"GeOFF v{version} (LSA {args.lsa_server.upper()}"
            f'{", NO SET" if args.japc_no_set else ""})'
        )
        window.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
