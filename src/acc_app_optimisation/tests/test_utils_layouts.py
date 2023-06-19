# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = import-outside-toplevel
# pylint: disable = redefined-outer-name

"""Tests for `acc_app_optimisation.utils.layouts`."""

import pytest
from pytestqt.qtbot import QtBot

# pylint: disable = wrong-import-position
pytest.importorskip("PyQt5.QtWidgets")

from PyQt5 import QtWidgets  # noqa: E402

import acc_app_optimisation.utils.layouts as layout_utils  # noqa: E402


@pytest.fixture
def widget(qtbot: QtBot) -> QtWidgets.QWidget:
    child_layout = QtWidgets.QHBoxLayout()
    child_layout.setObjectName("childLayout")
    for i in range(1, 4):
        widget = QtWidgets.QWidget()
        widget.setObjectName(f"grandChild_{i}")
        child_layout.addWidget(widget)
    parent_layout = QtWidgets.QVBoxLayout()
    parent_layout.setObjectName("parentLayout")
    parent_layout.addLayout(child_layout)
    parent_layout.addSpacerItem(QtWidgets.QSpacerItem(10, 10))
    child_widget = QtWidgets.QWidget()
    child_widget.setObjectName("childWidget")
    parent_layout.addWidget(child_widget)
    parent_widget = QtWidgets.QWidget()
    parent_widget.setObjectName("parentWidget")
    parent_widget.setLayout(parent_layout)
    qtbot.addWidget(parent_widget)
    return parent_widget


def test_iter_layout(widget: QtWidgets.QWidget) -> None:
    for item in layout_utils.iter_layout(widget.layout()):
        if item.widget():
            assert item.widget().objectName() == "childWidget"
        elif item.layout():
            assert ["grandChild_1", "grandChild_2", "grandChild_3"] == [
                item.widget().objectName()
                for item in layout_utils.iter_layout(item.layout())
            ]
        else:
            assert isinstance(item, QtWidgets.QSpacerItem)


def test_drain_layout(widget: QtWidgets.QWidget) -> None:
    assert [type(item) for item in layout_utils.drain_layout(widget.layout())] == [
        QtWidgets.QHBoxLayout,
        QtWidgets.QSpacerItem,
        QtWidgets.QWidgetItem,
    ]
    assert [child.objectName() for child in widget.children()] == [
        "parentLayout",
        "grandChild_1",
        "grandChild_2",
        "grandChild_3",
        "childWidget",
    ]


def test_iter_layout_widgets(widget: QtWidgets.QWidget) -> None:
    assert [
        w.objectName() for w in layout_utils.iter_layout_widgets(widget.layout())
    ] == [
        "grandChild_1",
        "grandChild_2",
        "grandChild_3",
        "childWidget",
    ]
    assert ["childWidget"] == [
        w.objectName()
        for w in layout_utils.iter_layout_widgets(widget.layout(), recursive=False)
    ]


def test_clear_children(widget: QtWidgets.QWidget) -> None:
    layout_utils.clear_children(widget)
    assert [child.objectName() for child in widget.children()] == ["parentLayout"]
    assert not list(layout_utils.iter_layout(widget.layout()))
