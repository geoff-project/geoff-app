#!/usr/bin/env python

# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Main entry point of this package."""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
import typing as t

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata  # type: ignore

import pjlsa
from accwidgets.log_console import LogConsoleModel
from cernml import coi
from PyQt5 import QtWidgets

from . import foreign_imports, logging_setup

if t.TYPE_CHECKING:
    # pylint: disable = unused-import, ungrouped-imports
    import os

    from acc_app_optimisation.gui.excdialog import ExceptionQueue
    from acc_app_optimisation.translate import InitialSelection


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
    # log console and to `handler`.
    logging.basicConfig(level="NOTSET", handlers=handlers)
    logging.captureWarnings(True)
    return LogConsoleModel()


def import_all(
    paths: t.Iterable[str], errors: ExceptionQueue, *, builtins: bool, keep_going: bool
) -> None:
    """Import all foreign packages as well as builtin envs.

    If *builtins* is True, built-in envs are loaded, otherwise not.
    Built-in envs are always loaded after foreign ones.

    If *keep_going* is True, all packages are attempted to be loaded,
    even if one raises an exception. If *keep_going* is False, this
    function returns on the first raised exception.

    In any case, all exceptions are appended to *errors* instead of
    being raised.
    """
    # pylint: disable = import-outside-toplevel
    message_template = (
        "could not load {kind} plugin"
        if keep_going
        else "aborted import sequence due to {kind} plugin"
    )
    plugin_kind = "external"
    for path in paths:
        try:
            foreign_imports.import_from_path(path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            errors.append(exc, message_template.format(kind=plugin_kind))
            if not keep_going:
                return
    # Tricky ordering: foreign imports may override builtins.
    plugin_kind = "built-in"
    if builtins:
        from acc_app_optimisation.envs import BUILTIN_ENVS

        for env in BUILTIN_ENVS:
            try:
                importlib.import_module(env)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(exc, message_template.format(kind=plugin_kind))
                if not keep_going:
                    return


def get_initial_selection(
    args: argparse.Namespace, errors: ExceptionQueue
) -> InitialSelection:
    # pylint: disable = import-outside-toplevel
    from acc_app_optimisation.translate import InitialSelection

    try:
        return InitialSelection(args.machine, args.user, args.lsa_server)
    except ValueError as exc:
        try:
            selection = InitialSelection(None, None, args.lsa_server)
        except ValueError as second_exc:
            # Log both exceptions as one error.
            second_exc.__suppress_context__ = False
            second_exc.__context__ = exc
            errors.append(second_exc, "LSA server could not be selected")
            # This never raises an exception:
            return InitialSelection(None, None, None)
        errors.append(exc, "machine or user could not be pre-selected")
        return selection


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
        type=str.upper,
        metavar="NAME",
        choices=[machine.name for machine in coi.Machine],
        help="The CERN machine to select initially; (default: "
        "deduced from --user if passed, otherwise NO_MACHINE)",
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str.upper,
        metavar="NAME",
        help="The timing user to select initially; if not passed, none is selected",
    )
    parser.add_argument(
        "-s",
        "--lsa-server",
        type=str.lower,
        metavar="NAME",
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
    parser.add_argument(
        "-k",
        "--keep-going",
        action="store_true",
        help="Continue importing built-in and foreign optimization "
        "problems, even if one of them fails",
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
        print(f"GeOFF v{metadata.version(__package__)}")
        return 0
    model = init_logging(log_to_file=args.log_to_file, filename=args.log_file)
    with logging_setup.redirect_streams_to_logging():
        # pylint: disable = import-outside-toplevel
        from acc_app_optimisation import gui

        errors = gui.excdialog.ExceptionQueue(title="Error during initialization")
        selection = get_initial_selection(args, errors)
        lsa = pjlsa.LSAClient(server=selection.lsa_server)
        with lsa.java_api():
            try:
                import_all(
                    args.foreign_imports,
                    errors,
                    builtins=args.builtins,
                    keep_going=args.keep_going,
                )
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc, "not all plugins could be loaded")
            # Do this *after* LSA!
            japc = selection.get_japc(no_set=args.japc_no_set)
            app = QtWidgets.QApplication(argv)
            app.setApplicationName(__package__)
            window = gui.MainWindow(japc=japc, lsa=lsa, model=model)
            window.setWindowTitle(
                f"GeOFF v{window.appVersion} "
                f"(LSA {selection.lsa_server.upper()}"
                f"{', NO SET' if args.japc_no_set else ''})"
            )
            try:
                window.make_initial_selection(selection)
            except ValueError as exc:
                errors.append(exc, "user could not be pre-selected")
            window.show()
            errors.show_all(parent=window)
            return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
