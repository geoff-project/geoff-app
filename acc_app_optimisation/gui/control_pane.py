import contextlib
import typing as t
from logging import getLogger

from accwidgets.lsa_selector import (
    LsaSelector,
    LsaSelectorAccelerator,
    LsaSelectorModel,
)
from cernml import coi
from pyjapc import PyJapc
from PyQt5 import QtCore, QtGui, QtWidgets

from .delayed_combo_box import DelayedComboBox
from .num_opt_tab import NumOptTab
from .rl_exec_tab import RlExecTab
from .rl_train_tab import RlTrainTab

if t.TYPE_CHECKING:
    # pylint: disable = import-error, ungrouped-imports, unused-import
    import pjlsa
    from accwidgets.rbac import RbaToken as AccWidgetsRbaToken

    from .plot_manager import PlotManager

LOG = getLogger(__name__)


def translate_machine(machine: coi.Machine) -> LsaSelectorAccelerator:
    """Fetch the LSA accelerator for a given CERN machine."""
    return {
        coi.Machine.LINAC_3: LsaSelectorAccelerator.LEIR,
        coi.Machine.LINAC_4: LsaSelectorAccelerator.PSB,
        coi.Machine.LEIR: LsaSelectorAccelerator.LEIR,
        coi.Machine.PS: LsaSelectorAccelerator.PS,
        coi.Machine.PSB: LsaSelectorAccelerator.PSB,
        coi.Machine.SPS: LsaSelectorAccelerator.SPS,
        coi.Machine.AWAKE: LsaSelectorAccelerator.AWAKE,
        coi.Machine.LHC: LsaSelectorAccelerator.LHC,
    }.get(machine, LsaSelectorAccelerator.LHC)


class ControlPane(QtWidgets.QWidget):
    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        initial_machine: coi.Machine,
        lsa: "pjlsa.LSAClient",
        plot_manager: "PlotManager",
        japc_no_set: bool = False,
    ) -> None:
        super().__init__(parent)
        # Set up internal attributes.
        # TODO: PyJapc should be a global.
        self._japc = PyJapc("", noSet=japc_no_set, incaAcceleratorName="AD")
        self._last_lsa_selection: t.Dict[str, str] = {}
        self._finalizers = contextlib.ExitStack()
        # Build the GUI.
        large = QtGui.QFont()
        large.setPointSize(12)
        machine_label = QtWidgets.QLabel("Machine:")
        machine_label.setFont(large)
        self.machine_combo = DelayedComboBox()
        self.machine_combo.addItems(machine.value for machine in coi.Machine)
        self.machine_combo.setCurrentText(initial_machine.value)
        self.machine_combo.stableTextChanged.connect(self._on_machine_changed)
        self.lsa_selector = LsaSelector(
            model=LsaSelectorModel(LsaSelectorAccelerator.SPS, lsa, resident_only=True),
            parent=self,
        )
        self.lsa_selector.userSelectionChanged.connect(self._on_lsa_user_changed)
        self.tabs = QtWidgets.QTabWidget()
        self.num_opt_tab = NumOptTab(plot_manager=plot_manager)
        self.rl_train_tab = RlTrainTab(plot_manager=plot_manager)
        self.rl_exec_tab = RlExecTab(plot_manager=plot_manager)
        self.tabs.addTab(self.num_opt_tab, "Num. Optimization")
        self.tabs.addTab(self.rl_train_tab, "Train RL Agent")
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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # pylint: disable = invalid-name
        self._finalizers.close()
        self._japc.rbacLogout()
        super().closeEvent(event)

    def rbac_login(self, pyrbac_token: "AccWidgetsRbaToken") -> None:
        # pylint: disable = import-error, import-outside-toplevel
        from cern.rbac.common import RbaToken
        from cern.rbac.util.holder import ClientTierTokenHolder  # type: ignore
        from java.nio import ByteBuffer

        byte_buffer = ByteBuffer.wrap(pyrbac_token.get_encoded())
        java_token = RbaToken.parseAndValidate(byte_buffer)
        ClientTierTokenHolder.setRbaToken(java_token)
        japc_token = self._japc.rbacGetToken()
        user_name = japc_token and japc_token.getUser().getName()
        LOG.info("JAPC login via RBAC, user: %s", user_name)

    def rbac_logout(self) -> None:
        self._japc.rbacLogout()
        LOG.info("JAPC logout via RBAC")

    def _on_machine_changed(self, value: str) -> None:
        LOG.debug("machine changed: %s", value)
        machine = coi.Machine(value)
        last_selection = self._last_lsa_selection.get(value, None)
        self.lsa_selector.accelerator = translate_machine(machine)
        if last_selection:
            self.lsa_selector.select_user(last_selection)
        self.num_opt_tab.setMachine(machine)
        self.rl_train_tab.setMachine(machine)
        self.rl_exec_tab.setMachine(machine)

    def _on_lsa_user_changed(self, user_name: str) -> None:
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
        self._finalizers.enter_context(self.rl_train_tab.create_lsa_context(self._japc))
        self._finalizers.enter_context(self.rl_exec_tab.create_lsa_context(self._japc))
        self._finalizers.callback(LOG.debug, "Invoking finalizers")
