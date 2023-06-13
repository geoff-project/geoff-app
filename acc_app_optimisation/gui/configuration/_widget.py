# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""The actual config widget."""

import logging
import typing as t
from types import SimpleNamespace

from cernml import coi
from PyQt5.QtWidgets import QFormLayout, QLabel, QWidget

from ._field_widgets import make_field_widget
from ._type_utils import str_boolsafe

LOG = logging.getLogger(__name__)


class ConfigureWidget(QWidget):
    """Qt dialog that allows configuring an environment.

    Args:
        config: A `Config` object describing this widget.
        parent: The parent widget to attach to.
    """

    def __init__(
        self,
        config: coi.Config,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._current_values = {
            field.dest: str_boolsafe(field.value) for field in self._config.fields()
        }
        params_layout = QFormLayout(self)
        for field in self._config.fields():
            label = QLabel(field.label)
            widget = make_field_widget(field, self._current_values)
            if field.help is not None:
                widget.setToolTip(field.help)
            params_layout.addRow(label, widget)

    def config(self) -> coi.Config:
        """Return the config that created this widget."""
        return self._config

    def current_values(self) -> SimpleNamespace:
        """Validate the current values and return them as a namespace.

        Note that this performs only the first step of validation! You
        still have to pass these values to
        `coi.Configurable.apply_config()`, which may fail.

        Raises:
            coi.BadConfig: if the values currently in the widget fail
                validation.
        """
        return self._config.validate_all(self._current_values)
