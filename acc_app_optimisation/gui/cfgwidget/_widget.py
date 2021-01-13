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

    Attributes:
        target: The object to configure.
        config: The `Config` object returned by the target.
        current_values: A dictionary of unparsed, unvalidated values,
            one for each field.
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

    @t.overload
    def apply_config(self) -> None:
        ...

    @t.overload
    def apply_config(self, *, return_exc: bool) -> t.Optional[Exception]:
        ...

    def apply_config(self, *, return_exc: bool = False) -> t.Optional[Exception]:
        """Apply the currently chosen values to the configurable.

        Args:
            return_exc: If passed and True, this captures and returns an
                exception that happens during validation. The default is
                to let any exceptions bubble up to indicate that
                validation failed.
        """
        try:
            values = self.config.validate_all(self.current_values)
            self.target.apply_config(values)
        except Exception as exc:
            LOG.warning("configuration failed validation: %s", exc)
            if return_exc:
                return exc
            raise
        LOG.info("configuration applied: %s", values)
        return None
