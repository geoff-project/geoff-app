import typing
import jpype.imports

import pjlsa
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import QAbstractTableModel, QObject, QModelIndex, Qt, QVariant


class LsaSelectorModel(QAbstractTableModel):
    def __init__(
        self,
        lsa: pjlsa.LSAClient,
        accelerator: str,
        parent: typing.Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        jpype.imports.registerDomain("cern")
        self.lsa = lsa
        self.contexts = self.findContexts(accelerator.lower())

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    @property
    def user(self):
        return self.context.getUser()

    def setAccelerator(self, accelerator: str):
        self.beginResetModel()
        self.contexts = self.findContexts(accelerator.lower())
        self.endResetModel()

    def findContexts(self, accelerator: str):
        from cern.accsoft.commons.domain import CernAccelerator
        from cern.lsa.client import ServiceLocator, ContextService

        acceleratorsDict = {
            "ps": CernAccelerator.PS,
            "psb": CernAccelerator.PSB,
            "sps": CernAccelerator.SPS,
            "lhc": CernAccelerator.LHC,
            "leir": CernAccelerator.LEIR,
            "ln4": CernAccelerator.LINAC4,
            "awake": CernAccelerator.AWAKE,
        }
        accelerator = acceleratorsDict[accelerator]

        service = ServiceLocator.getService(ContextService)
        _ = service.findStandAloneCycles(accelerator)
        active_contexts = service.findActiveContexts(accelerator)
        resident_contexts = service.findResidentContexts(accelerator)

        df = {}
        df["Context"] = list(resident_contexts)
        df["User"] = [context.getUser().split(".")[-1] for context in df["Context"]]
        df["Status"] = [
            "_NON-PPM"
            if "_NON_MULTIPLEXED" in str(context)
            else "Active"
            if context in active_contexts
            else "Resident"
            for context in df["Context"]
        ]
        ix = sorted(range(len(df["Context"])), key=lambda i: df["Context"][i])
        df = {key: [val[i] for i in ix] for key, val in df.items()}
        ix = sorted(range(len(df["Context"])), key=lambda i: df["Status"][i])
        df = {key: [val[i] for i in ix] for key, val in df.items()}
        return df

    def data(
        self,
        index: QModelIndex,
        role: typing.Optional[Qt.ItemDataRole] = None,
    ) -> typing.Any:

        if index.isValid() and 0 <= index.row() <= self.rowCount():
            if role == Qt.DisplayRole:
                context = self.contexts["Context"][index.row()]
                # self.contexts.loc[index.row(), "Context"]
                user = self.contexts["User"][index.row()]
                # self.contexts.loc[index.row(), "User"]
                if index.column() == 1:
                    return f"{context}"
                elif index.column() == 0:
                    return f"{user}"
            elif role == Qt.BackgroundRole:
                return QColor("black")
            elif role == Qt.ForegroundRole:
                status = self.contexts["Status"][index.row()]
                # self.contexts.loc[index.row(), "Status"]
                if index.column() == 1:
                    if status == "Active":
                        return QColor("lime")
                    elif status == "_NON-PPM":
                        return QColor("orange")
                    else:
                        return QColor("yellow")
                elif index.column() == 0:
                    return QColor("white")
            elif role == Qt.FontRole:
                return QFont("Helvetica", 8, QFont.Bold)
            elif role == Qt.ImCurrentSelection:
                return QColor("red")
            else:
                return QVariant()

    def getItem(self, index):

        if index.isValid():
            context, user = (
                self.contexts["Context"][index.row()],
                self.contexts["User"][index.row()],
            )
            # context, user = self.contexts.loc[index.row(), ["Context", "User"]]
            self.context = context

            return str(context), user

        return None

    def rowCount(self, parent: typing.Optional[QModelIndex] = None) -> int:
        return len(self.contexts["Context"])

    def columnCount(self, parent: typing.Optional[QModelIndex] = None) -> int:
        return 2
