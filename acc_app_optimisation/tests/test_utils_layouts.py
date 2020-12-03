#!/usr/bin/env python
"""Tests for `acc_app_optimisation.utils.layouts`."""

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = import-outside-toplevel
# pylint: disable = redefined-outer-name

import pytest

# pylint: disable = wrong-import-position
pytest.importorskip("PyQt5.QtWidgets")

from PyQt5 import QtWidgets

import acc_app_optimisation.utils.layouts as layout_utils


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication([])


@pytest.fixture
def mock_layout() -> QtWidgets.QLayout:
    child_layout = QtWidgets.QHBoxLayout(objectName="childLayout")
    for i in range(1, 4):
        child_layout.addWidget(QtWidgets.QWidget(objectName=f"grandChild_{i}"))
    parent_layout = QtWidgets.QVBoxLayout(objectName="parentLayout")
    parent_layout.addLayout(child_layout)
    parent_layout.addSpacerItem(QtWidgets.QSpacerItem(10, 10))
    parent_layout.addWidget(QtWidgets.QWidget(objectName="childWidget"))
    return parent_layout


@pytest.mark.usefixtures("app")
def test_iter_layout(mock_layout: QtWidgets.QLayout) -> None:
    for item in layout_utils.iter_layout(mock_layout):
        if item.widget():
            assert item.widget().objectName() == "childWidget"
        elif item.layout():
            assert ["grandChild_1", "grandChild_2", "grandChild_3"] == [
                item.widget().objectName() for item in layout_utils.iter_layout(item)
            ]
        else:
            assert isinstance(item, QtWidgets.QSpacerItem)


@pytest.mark.usefixtures("app")
def test_drain_layout(mock_layout: QtWidgets.QLayout) -> None:
    parent = QtWidgets.QWidget()
    parent.setLayout(mock_layout)
    assert [type(item) for item in layout_utils.drain_layout(mock_layout)] == [
        QtWidgets.QHBoxLayout,
        QtWidgets.QSpacerItem,
        QtWidgets.QWidgetItem,
    ]
    assert [child.objectName() for child in parent.children()] == [
        "parentLayout",
        "grandChild_1",
        "grandChild_2",
        "grandChild_3",
        "childWidget",
    ]


@pytest.mark.usefixtures("app")
def test_iter_layout_widgets(mock_layout: QtWidgets.QLayout) -> None:
    assert [w.objectName() for w in layout_utils.iter_layout_widgets(mock_layout)] == [
        "grandChild_1",
        "grandChild_2",
        "grandChild_3",
        "childWidget",
    ]
    assert ["childWidget"] == [
        w.objectName()
        for w in layout_utils.iter_layout_widgets(mock_layout, recursive=False)
    ]


@pytest.mark.usefixtures("app")
def test_clear_children(mock_layout: QtWidgets.QLayout) -> None:
    parent = QtWidgets.QWidget()
    parent.setLayout(mock_layout)
    layout_utils.clear_children(parent)
    assert [child.objectName() for child in parent.children()] == ["parentLayout"]
    assert not list(layout_utils.iter_layout(mock_layout))
