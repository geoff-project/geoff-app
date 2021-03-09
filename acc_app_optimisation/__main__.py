#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import logging
import sys

import pjlsa
from accwidgets.log_console import LogConsoleModel
from PyQt5 import QtWidgets


def init_logging() -> LogConsoleModel:
    """Configure the `logging` module."""
    basic_formatter = logging.Formatter(logging.BASIC_FORMAT)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel("INFO")
    stderr_handler.setFormatter(basic_formatter)
    logging.basicConfig(
        level="NOTSET",
        handlers=[stderr_handler],
    )
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
        "imported; child modules may be imported by appending them, "
        "delimited by `::`",
    )
    parser.add_argument(
        "-s",
        "--lsa-server",
        type=str,
        metavar="NAME",
        default="gpn",
        help="The LSA server to connect to (default: gpn)",
    )
    return parser


def main(argv) -> int:
    """Main function. Pass sys.argv."""
    model = init_logging()
    args = get_parser().parse_args(argv[1:])
    lsa = pjlsa.LSAClient(server=args.lsa_server)
    with lsa.java_api():
        # pylint: disable = import-outside-toplevel
        from acc_app_optimisation import foreign_imports, gui

        for path in args.foreign_imports:
            foreign_imports.import_from_path(path)
        app = QtWidgets.QApplication(argv)
        window = gui.MainWindow(lsa=lsa, model=model)
        window.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
