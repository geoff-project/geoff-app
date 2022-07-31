#!/usr/bin/env python
"""Main entry point of this package."""

from __future__ import annotations

import argparse
import logging
import sys
import typing as t

import importlib_metadata
import pjlsa
from accwidgets.log_console import LogConsoleModel
from cernml import coi
from PyQt5 import QtWidgets

from . import foreign_imports, logging_setup

if t.TYPE_CHECKING:
    # pylint: disable = unused-import, ungrouped-imports
    import os


def init_logging(
    log_to_file: bool, filename: t.Union[None, str, os.PathLike]
) -> LogConsoleModel:
    """Configure the `logging` module."""
    if log_to_file:
        handler = logging_setup.create_handler(filename)
        print("Logging to", handler.stream.name, file=sys.stderr)
        handlers = [handler]
    else:
        handlers = []
    # No level-based filtering on the root logger; we leave that to the
    # log console and to the stderr_handler.
    logging.basicConfig(level="NOTSET", handlers=handlers)
    return LogConsoleModel()


def import_all(paths: t.Iterable[str], *, builtins: bool) -> t.Optional[Exception]:
    """Import all foreign packages as well as builtin envs.

    If an exception occurs at any point, it is caught, logged, and
    returned. This allows displaying the error in the GUI later.
    """
    # pylint: disable = broad-except
    # pylint: disable = import-outside-toplevel
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
    logger = parser.add_mutually_exclusive_group()
    logger.add_argument(
        "--enable-logging",
        dest="log_to_file",
        action="store_true",
        default=True,
        help="In addition to the app's logging console, also log "
        "events to a file on disk (this is the default)",
    )
    logger.add_argument(
        "--disable-logging",
        dest="log_to_file",
        action="store_false",
        help="Disable on-disk logging",
    )
    logger.add_argument(
        "--log-file",
        type=str,
        help="Location for on-disk logging; by default, a new file "
        'is created under /tmp; pass "-" to log to stderr',
    )
    return parser


def main(argv: list) -> int:
    """Main function. Pass sys.argv."""
    args = get_parser().parse_args(argv[1:])
    if args.version:
        print(f"GeOFF v{importlib_metadata.version(__package__)}")
        return 0
    model = init_logging(log_to_file=args.log_to_file, filename=args.log_file)
    with logging_setup.redirect_streams_to_logging():
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
