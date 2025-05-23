# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import contextlib
import typing as t
from logging import getLogger

import pyjapc
from accwidgets.lsa_selector import (
    AbstractLsaSelectorContext,
    LsaSelector,
    LsaSelectorAccelerator,
    LsaSelectorModel,
)
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets

from .. import translate
from .delayed_combo_box import DelayedComboBox
from .num_opt_tab import NumOptTab
from .rl_exec_tab import RlExecTab

if t.TYPE_CHECKING:
    # pylint: disable = import-error, ungrouped-imports, unused-import
    import pjlsa
    import pyrbac

    from ..lsa_utils_hooks import GeoffHooks
    from .plot_manager import PlotManager

LOG = getLogger(__name__)


class ControlPane(QtWidgets.QWidget):
    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        japc: pyjapc.PyJapc,
        lsa: "pjlsa.LSAClient",
        lsa_hooks: "GeoffHooks",
        plot_manager: "PlotManager",
    ) -> None:
        super().__init__(parent)
        # Set up internal attributes.
        self._japc = japc
        self._last_lsa_selection: t.Dict[str, str] = {}
        self._finalizers = contextlib.ExitStack()
        # Build the GUI.
        large = QtGui.QFont()
        large.setPointSize(12)
        machine_label = QtWidgets.QLabel("Machine:")
        machine_label.setFont(large)
        self.machine_combo = DelayedComboBox()
        self.machine_combo.addItems(machine.value for machine in coi.Machine)
        self.machine_combo.setCurrentText(coi.Machine.NO_MACHINE.value)
        self.machine_combo.stableTextChanged.connect(self._on_machine_changed)
        self.lsa_selector = LsaSelector(
            parent=self,
            model=LsaSelectorModel(
                accelerator=LsaSelectorAccelerator.LHC,
                categories=set(AbstractLsaSelectorContext.Category),
                lsa=lsa,
                # Without `resident_only`, we'd also fetch non-resident
                # contexts, which don't fire the `userSelectionChanged`
                # event that we connect to.
                resident_only=True,
            ),
        )
        self.lsa_selector.userSelectionChanged.connect(self._on_lsa_user_changed)
        self.lsa_selector.showCategoryFilter = True  # type: ignore # mypy bug #9911
        self.tabs = QtWidgets.QTabWidget()
        self.num_opt_tab = NumOptTab(lsa_hooks=lsa_hooks, plot_manager=plot_manager)
        self.rl_exec_tab = RlExecTab(lsa_hooks=lsa_hooks, plot_manager=plot_manager)
        self.tabs.addTab(self.num_opt_tab, "Num. Optimization")
        self.tabs.addTab(self.rl_exec_tab, "Run RL Agent")
        self.tabs.setElideMode(QtCore.Qt.ElideRight)
        # Lay out all widgets.
        layout = QtWidgets.QVBoxLayout(self)
        machine_layout = QtWidgets.QFormLayout()
        machine_layout.setContentsMargins(0, 0, 0, 0)
        machine_layout.addRow(machine_label, self.machine_combo)
        layout.addLayout(machine_layout)
        layout.addWidget(self.lsa_selector, stretch=1)
        layout.addWidget(self.tabs)
        # Fill all GUI elements, fire any events based on that.
        self._on_machine_changed(self.machine_combo.currentText())

    def make_initial_selection(self, selection: translate.InitialSelection) -> None:
        """Pre-select machine and user according to command-line arguments."""
        if self.lsa_selector.selected_context is not None:
            raise RuntimeError("initial selection has already been made")
        self.machine_combo.setStableText(selection.machine.value)
        default_category = AbstractLsaSelectorContext.Category.OPERATIONAL
        try:
            if selection.user:
                self.lsa_selector.select_user(selection.user)
                if self.lsa_selector.selected_context is None:
                    LOG.error("cannot select user: %s", selection.user)
                    raise ValueError(f"cannot select user: {selection.user}")
                default_category = self.lsa_selector.selected_context.category
        finally:
            self.lsa_selector.model.filter_categories = {default_category}

    def rbac_login(self, token: "pyrbac.Token") -> None:
        # pylint: disable = import-error, import-outside-toplevel
        from cern.rbac.common import RbaToken
        from cern.rbac.util.holder import ClientTierTokenHolder  # type: ignore
        from java.nio import ByteBuffer

        byte_buffer = ByteBuffer.wrap(token.encode())
        java_token = RbaToken.parseAndValidate(byte_buffer)
        ClientTierTokenHolder.setRbaToken(java_token)
        japc_token = self._japc.rbacGetToken()
        user_name = japc_token and japc_token.getUser().getName()
        LOG.info("JAPC login via RBAC, user: %s", user_name)

    def rbac_logout(self) -> None:
        self._japc.rbacLogout()
        LOG.info("JAPC logout via RBAC")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # pylint: disable = invalid-name
        self._finalizers.close()
        self._japc.rbacLogout()
        super().closeEvent(event)

    def _on_machine_changed(self, value: str) -> None:
        LOG.debug("machine changed: %s", value)
        # Unload JAPC. This avoids JAPC with selector for machine A to
        # an env for machine B if the user never selected a context for
        # machine B (and thus _on_lsa_user_changed() was never called
        # for machine B).
        self._finalizers.close()
        # Switch LSA widget to new machine. If the user previously
        # selected a context for this machine, re-select it.
        machine = coi.Machine(value)
        last_selection = self._last_lsa_selection.get(value, None)
        self.lsa_selector.accelerator = t.cast(
            t.Any,
            translate.machine_to_lsa_accelerator(machine) or LsaSelectorAccelerator.LHC,
        )
        if last_selection:
            self.lsa_selector.select_user(last_selection)
        self.num_opt_tab.setMachine(machine)
        self.rl_exec_tab.setMachine(machine)

    def _on_lsa_user_changed(self, user_name: str) -> None:
        assert self.lsa_selector.selected_context is not None, (
            "This should never happen"
        )
        context_name = self.lsa_selector.selected_context.name
        LOG.debug("cycle changed: %s, %s", context_name, user_name)
        self._last_lsa_selection[self.machine_combo.currentText()] = user_name
        # Workflow for changing the context: close current coi.Problem,
        # clean up JAPC, change selector, pass new JAPC to new
        # coi.Problem.
        self._finalizers.close()
        self._japc.setSelector(user_name)
        self._finalizers.callback(self._japc.clearSubscriptions)
        self._finalizers.enter_context(self.num_opt_tab.create_lsa_context(self._japc))
        self._finalizers.enter_context(self.rl_exec_tab.create_lsa_context(self._japc))
        self._finalizers.callback(LOG.debug, "Invoking finalizers")
