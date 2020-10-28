from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QSpinBox,
    QFormLayout,
    QLabel,
    QWidget,
    QCheckBox,
)


def make_dict_updater(mapping, key):
    def updater(value):
        mapping[key] = value

    return updater


class ParamsForm(QWidget):
    def __init__(self, params_dict, parent=None):
        super().__init__(parent)
        layout = QFormLayout()
        for name, value in params_dict.items():
            label = QLabel(name)
            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setCheckState(value)
                widget.stateChanged.connect(make_dict_updater(params_dict, name))
            elif isinstance(value, float):
                widget = QDoubleSpinBox()
                widget.setMinimum(float("-inf"))
                widget.setMaximum(float("inf"))
                widget.setValue(value)
                widget.valueChanged.connect(make_dict_updater(params_dict, name))
            elif isinstance(value, int):
                widget = QSpinBox()
                widget.setMinimum(-32768)
                widget.setMaximum(32768)
                widget.setValue(value)
                widget.valueChanged.connect(make_dict_updater(params_dict, name))
            else:
                continue
            layout.addRow(label, widget)
        self.setLayout(layout)
