"""The actual config widget."""

import logging
import typing as t

from PyQt5.QtWidgets import (
    QFormLayout,
    QLabel,
    QWidget,
)
from cernml import coi

from ._field_widgets import UnparsedDict, make_field_widget

LOG = logging.getLogger(__name__)


class ConfigureWidget(QWidget):
    """Qt dialog that allows configuring an environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    target: coi.Configurable
    config: coi.Config
    current_values: UnparsedDict

    def __init__(
        self,
        target: coi.Configurable,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.target = target
        self.config = self.target.get_config()
        self.current_values = {
            field.dest: str(field.value) for field in self.config.fields()
        }
        params_layout = QFormLayout(self)
        for field in self.config.fields():
            label = QLabel(field.label)
            widget = make_field_widget(field, self.current_values)
            if field.help is not None:
                widget.setToolTip(field.help)
            params_layout.addRow(label, widget)

    def apply_configs(self) -> None:
        """Apply the currently chosen values to the configurable."""
        values = self.config.validate_all(self.current_values)
        self.target.apply_config(values)
        LOG.info("applied configuration: %s", values)
