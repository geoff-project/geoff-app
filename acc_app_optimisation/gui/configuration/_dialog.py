"""Provide a dialog for configuring optimization problems."""

import logging
import typing as t

import gym
import numpy as np
from cernml import coi
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from ...utils.disabled_updates import disabled_updates
from ...utils.coerce_float import coerce_float_tuple
from ...utils.typecheck import AnyOptimizable, is_configurable, is_function_optimizable
from ..excdialog import exception_dialog
from ._skeleton_points import (
    BaseSkeletonPointsWidget,
    SkeletonPointsEditWidget,
    SkeletonPointsViewWidget,
)
from ._widget import ConfigureWidget

LOG = logging.getLogger(__name__)


class _BaseDialog(QDialog):
    """Common logic of `PureConfigureDialog` and `ProblemConfigureDialog`.

    Args:
        target: The environment to be configured.
        parent: The parent widget to attach to.

    Attributes:
        _cfgform: The `ConfigureWidget` to use. `None` if no target is passed.
        _controls: The `QDialogButtonBox` to use in this dialog.
    """

    config_applied = pyqtSignal()

    def __init__(self, target: t.Any, parent: t.Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configuring {_get_configurable_name(target)} …")
        self.target = target
        self._cfgform = (
            ConfigureWidget(target.get_config()) if is_configurable(target) else None
        )
        self._controls = QDialogButtonBox(  # type: ignore
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self._controls.button(QDialogButtonBox.Ok).clicked.connect(self._on_ok_clicked)
        self._controls.button(QDialogButtonBox.Apply).clicked.connect(
            self._on_apply_clicked
        )
        self._controls.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)

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
        if self._cfgform is None:
            return True
        assert is_configurable(self.target), self.target
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

    # pylint: disable = invalid-name

    def __init__(
        self,
        target: AnyOptimizable,
        skeleton_points: t.Tuple[float, ...] = (),
        parent: t.Optional[QWidget] = None,
    ) -> None:
        super().__init__(target, parent)
        self._points_page: t.Optional[BaseSkeletonPointsWidget]
        self._tab_widget = QTabWidget()
        if self._cfgform is not None:
            self._tab_widget.addTab(self._cfgform, "Configuration")
        if is_function_optimizable(target):
            points_override = target.override_skeleton_points()
            if points_override is not None:
                self._skeleton_points = coerce_float_tuple(points_override)
                self._points_page = SkeletonPointsViewWidget(self._skeleton_points)
            else:
                self._skeleton_points = skeleton_points
                self._points_page = SkeletonPointsEditWidget(self._skeleton_points)
            self._tab_widget.addTab(self._points_page, "Skeleton points")
        else:
            self._points_page = None
            self._skeleton_points = ()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._tab_widget)
        main_layout.addWidget(self._controls)

    def skeletonPoints(self) -> t.Tuple[float, ...]:
        return self._skeleton_points

    def setSkeletonPoints(self, points: t.Tuple[float, ...]) -> None:
        if self._points_page is not None:
            self._skeleton_points = points
            self._points_page.setSkeletonPoints(points)
        else:
            raise TypeError(
                f"cannot set skeleton points, {self.target} is not FunctionOptimizable"
            )

    def apply_config(self) -> bool:
        if isinstance(self._points_page, SkeletonPointsViewWidget):
            assert is_function_optimizable(self.target), self.target
            # Skeleton points page is read-only -- update it.
            # But only if the configs were updated successfully.
            success = super().apply_config()
            points_override = self.target.override_skeleton_points()
            if points_override is None:
                self._replace_skeleton_points_widget(
                    SkeletonPointsEditWidget(self._skeleton_points)
                )
            else:
                self._points_page.setSkeletonPoints(coerce_float_tuple(points_override))
            return success
        if isinstance(self._points_page, SkeletonPointsEditWidget):
            assert is_function_optimizable(self.target), self.target
            # Skeleton points page is editable -- read its values.
            # If that succeeds, continue with regular configs.
            try:
                self._skeleton_points = self._points_page.skeletonPoints()
            except ValueError as exc:
                _show_skeleton_points_failed(exc, parent=self)
                return False
            success = super().apply_config()
            points_override = self.target.override_skeleton_points()
            if points_override is not None:
                self._skeleton_points = coerce_float_tuple(points_override)
                self._replace_skeleton_points_widget(
                    SkeletonPointsViewWidget(self._skeleton_points)
                )
            return success
        # There is no skeleton points page. Just delegate to configs.
        assert self._points_page is None
        return super().apply_config()

    def _replace_skeleton_points_widget(self, new: BaseSkeletonPointsWidget) -> None:
        assert self._points_page is not None
        with disabled_updates(self._tab_widget) as tabs:
            current_index = tabs.currentIndex()
            points_tab_index = tabs.indexOf(self._points_page)
            tabs.removeTab(points_tab_index)
            new_index = tabs.insertTab(points_tab_index, new, "Skeleton points")
            if current_index == points_tab_index:
                tabs.setCurrentIndex(new_index)


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
        if is_configurable(self.env):
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

    def apply_config(self, values: coi.ConfigValues) -> None:
        self.value = values.TimeLimit_max_episode_steps
        if is_configurable(self.env):
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
