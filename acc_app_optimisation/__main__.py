#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import logging
import sys
import typing as t

from PyQt5 import QtWidgets
import pjlsa

# TODO: Make this nicer and cooperate with logging.basicConfig()
LOG = logging.getLogger(__name__)
LSA = pjlsa.LSAClient(server="next")


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="GeOFF: Generic Optimization Framework and Frontend"
    )
    parser.add_argument(
        "foreign_imports",
        nargs="*",
        type=str,
        help="Path to additional modules and packages that shall be "
        "imported; child modules may be imported by appending them, "
        "delimited by `::`",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=logging.WARNING,
        default=logging.INFO,
        dest="verbosity",
        help="Only show warnings and errors",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=logging.DEBUG,
        dest="verbosity",
        help="Show debug-level information",
    )
    return parser


def main(argv):
    """Main function. Pass sys.argv."""
    args = get_parser().parse_args(argv[1:])
    logging.basicConfig(level=args.verbosity)
    with LSA.java_api():
        from acc_app_optimisation.main_window import MainWindow
        from acc_app_optimisation import foreign_imports

        for path in args.foreign_imports:
            foreign_imports.import_from_path(path)
        app = QtWidgets.QApplication(argv)
        window = MainWindow(LSA)
        window.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
