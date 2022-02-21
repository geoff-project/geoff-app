"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t
from types import SimpleNamespace

import gym
import numpy as np
from cernml import coi
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from ..excdialog import exception_dialog
from ._skeleton_points import SkeletonPointsWidget
from ._widget import ConfigureWidget

LOG = logging.getLogger(__name__)


class _BaseDialog(QDialog):
    """Common logic of `PureConfigureDialog` and `ProblemConfigureDialog`.

    Args:
        target: The environment to be configured. If None is passed, no
            `ConfigureWidget` is created.
        parent: The parent widget to attach to.

    Attributes:
        _cfgform: The `ConfigureWidget` to use. `None` if no target is passed.
        _controls: The `QDialogButtonBox` to use in this dialog.
    """

    config_applied = pyqtSignal()

    def __init__(
        self, target: t.Optional[coi.Configurable], parent: t.Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.target = target
        self._cfgform = None if target is None else ConfigureWidget(target.get_config())
        self._controls = QDialogButtonBox(  # type: ignore
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self._controls.button(QDialogButtonBox.Ok).clicked.connect(self._on_ok_clicked)
        self._controls.button(QDialogButtonBox.Apply).clicked.connect(
            self._on_apply_clicked
        )
        self._controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        if target is not None:
            self.setWindowTitle(f"Configuring {_get_configurable_name(target)} …")
        else:
            self.setWindowTitle("Configuring …")

    def _on_ok_clicked(self) -> None:
        """Apply the configs and close the window."""
        # Only close the dialog if there was no error.
        if self.apply_config():
            self.config_applied.emit()
            self.accept()

    def _on_apply_clicked(self) -> None:
        """Apply the configs."""
        if self.apply_config():
            self.config_applied.emit()

    def apply_config(self) -> bool:
        """Apply the currently chosen values to the configurable.

        Returns:
            True if the config has been applied successfully. False if
            an exception has been raised.
        """
        if self.target is None:
            return True
        assert self._cfgform is not None
        try:
            values = self._cfgform.current_values()
            self.target.apply_config(values)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.warning("configuration failed validation: %s", exc)
            _show_config_failed(self.target, exc, parent=self)
            return False
        LOG.info("configuration applied: %s", values)
        return True


class PureDialog(_BaseDialog):
    """Qt dialog that allows configuring a `coi.Configurable`.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self, target: coi.Configurable, parent: t.Optional[QWidget] = None
    ) -> None:
        super().__init__(target, parent)
        assert self._cfgform is not None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._cfgform)
        main_layout.addWidget(self._controls)


class OptimizableDialog(_BaseDialog):
    """Qt dialog that allows configuring a `FunctionOptimizable`.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self,
        target: t.Union[coi.SingleOptimizable, coi.FunctionOptimizable],
        skeleton_points: t.Optional[np.ndarray] = None,
        parent: t.Optional[QWidget] = None,
    ) -> None:
        if isinstance(target.unwrapped, coi.Configurable):
            super().__init__(t.cast(coi.Configurable, target), parent)
        else:
            super().__init__(None, parent)
            self.setWindowTitle(f"Configuring {_get_configurable_name(target)} …")
        self._points_page: t.Optional[SkeletonPointsWidget]
        tab_widget = QTabWidget()
        if self._cfgform is not None:
            tab_widget.addTab(self._cfgform, "Configuration")
        self._skeleton_points: t.Optional[np.ndarray]
        if isinstance(target.unwrapped, coi.FunctionOptimizable):
            if skeleton_points is not None:
                self._skeleton_points = np.array(skeleton_points, dtype=float)
            else:
                self._skeleton_points = np.array([], dtype=float)
            self._points_page = SkeletonPointsWidget(self._skeleton_points)
            tab_widget.addTab(self._points_page, "Skeleton points")
        else:
            self._points_page = None
            self._skeleton_points = None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self._controls)

    def skeletonPoints(self) -> t.Optional[np.ndarray]:  # pylint: disable=invalid-name
        return self._skeleton_points

    def setSkeletonPoints(  # pylint: disable=invalid-name
        self, points: np.ndarray
    ) -> None:
        if self._points_page is not None:
            self._skeleton_points = points
            self._points_page.setSkeletonPoints(points)
        else:
            raise TypeError(
                f"cannot set skeleton points, {self.target} is not FunctionOptimizable"
            )

    def apply_config(self) -> bool:
        if self._points_page is not None:
            try:
                self._skeleton_points = self._points_page.skeletonPoints()
            except ValueError as exc:
                _show_skeleton_points_failed(exc, parent=self)
                return False
        return super().apply_config()


class EnvDialog(_BaseDialog):
    """Qt dialog that allows configuring an RL environment.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.
    """

    def __init__(
        self, env: gym.Env, time_limit: int, parent: t.Optional[QWidget] = None
    ) -> None:
        self._configurable = ConfigTimeLimit(env, time_limit)
        super().__init__(self._configurable, parent)
        assert self._cfgform is not None
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._cfgform)
        main_layout.addWidget(self._controls)

    def timeLimit(self) -> int:  # pylint: disable=invalid-name
        return self._configurable.value


class ConfigTimeLimit(gym.Wrapper, coi.Configurable):
    def __init__(self, env: gym.Env, initial_limit: t.Optional[int] = None) -> None:
        super().__init__(env)
        spec = getattr(self, "spec", None)
        self.default_value = getattr(spec, "max_episode_steps", 0)
        self.value = initial_limit if initial_limit is not None else self.default_value

    def get_config(self) -> coi.Config:
        if isinstance(self.env, coi.Configurable):
            config = self.env.get_config()
        else:
            config = coi.Config()
        config.add(
            "TimeLimit_max_episode_steps",
            self.value,
            range=(0, np.inf),
            default=self.default_value,
            label="Time limit",
            help="Maximum number of steps per episode; set to 0 to disable time limit",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.value = values.TimeLimit_max_episode_steps
        if isinstance(self.env, coi.Configurable):
            self.env.apply_config(values)


def _show_config_failed(
    target: coi.Configurable, exc: Exception, parent: t.Optional[QWidget]
) -> None:
    dialog = exception_dialog(
        exc,
        title="Configuration validation",
        text=f"{target} could not be configured.",
        parent=parent,
    )
    dialog.show()


def _show_skeleton_points_failed(exc: Exception, parent: t.Optional[QWidget]) -> None:
    dialog = exception_dialog(
        exc,
        title="Configuration validation",
        text="Cannot set skeleton points",
        parent=parent,
    )
    dialog.show()


def _get_configurable_name(configurable: t.Any) -> str:
    spec = getattr(configurable, "spec", None)
    if spec is not None:
        return spec.id
    unwrapped = getattr(configurable, "unwrapped", None)
    if unwrapped is not None:
        return type(unwrapped).__name__
    return type(configurable).__name__
