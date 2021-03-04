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

from ..gui.plot_manager import PlotManager
from .num_opt_tab import NumOptTab

if t.TYPE_CHECKING:
    import pjlsa  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


def translate_machine(machine: coi.Machine) -> t.Optional[LsaSelectorAccelerator]:
    """Fetch the LSA accelerator for a given CERN machine."""
    return {
        coi.Machine.NoMachine: None,
        coi.Machine.Linac2: None,
        coi.Machine.Linac3: LsaSelectorAccelerator.LEIR,
        coi.Machine.Linac4: LsaSelectorAccelerator.PSB,
        coi.Machine.Leir: LsaSelectorAccelerator.LEIR,
        coi.Machine.PS: LsaSelectorAccelerator.PS,
        coi.Machine.PSB: LsaSelectorAccelerator.PSB,
        coi.Machine.SPS: LsaSelectorAccelerator.SPS,
        coi.Machine.Awake: LsaSelectorAccelerator.AWAKE,
        coi.Machine.LHC: LsaSelectorAccelerator.LHC,
    }.get(machine)


class ControlPane(QtWidgets.QWidget):

    # pylint: disable = too-many-instance-attributes

    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        lsa: "pjlsa.LSAClient",
        plot_manager: PlotManager,
        japc_no_set: bool = False,
    ) -> None:
        super().__init__(parent)
        # Set up internal attributes.
        self._japc = PyJapc("", noSet=japc_no_set, incaAcceleratorName="AD")
        self._last_lsa_selection: t.Dict[str, str] = {}
        self._finalizers = contextlib.ExitStack()
        # Build the GUI.
        large = QtGui.QFont()
        large.setPointSize(12)
        machine_label = QtWidgets.QLabel("Machine:")
        machine_label.setFont(large)
        self.machine_combo = QtWidgets.QComboBox()
        self.machine_combo.addItems(
            machine.name for machine in coi.Machine if translate_machine(machine)
        )
        self.machine_combo.currentTextChanged.connect(self._on_machine_changed)
        self.lsa_selector = LsaSelector(
            model=LsaSelectorModel(LsaSelectorAccelerator.SPS, lsa, resident_only=True),
            parent=self,
        )
        self.lsa_selector.userSelectionChanged.connect(self._on_lsa_user_changed)
        self.tabs = QtWidgets.QTabWidget()
        self.num_opt_tab = NumOptTab(plot_manager=plot_manager)
        self.tabs.addTab(self.num_opt_tab, "Num. Optimization")
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
        self.machine_combo.setCurrentText("SPS")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # pylint: disable = invalid-name
        self._finalizers.close()
        super().closeEvent(event)

    def _on_machine_changed(self, name: str) -> None:
        LOG.debug("machine changed: %s", name)
        machine = coi.Machine[name]
        last_selection = self._last_lsa_selection.get(name, None)
        self.lsa_selector.accelerator = translate_machine(machine)
        if last_selection:
            self.lsa_selector.select_user(last_selection)
        self.num_opt_tab.setMachine(machine)

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
        self._finalizers.callback(LOG.debug, "Invoking finalizers")
