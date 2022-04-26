from enum import Enum
from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QLineEdit

from juniors_toolbox.gui.widgets.property import A_ValueProperty

class ExplicitLineEdit(QLineEdit, A_ValueProperty):
    textChangedNamed: SignalInstance = Signal(QLineEdit, str)

    class FilterKind(Enum):
        STR = None
        INT = QIntValidator()
        FLOAT = QDoubleValidator()

        @classmethod
        def type_to_filter(cls, _ty: type):
            return cls[_ty.__name__.upper()]

    def __init__(self, name: str, filter: FilterKind, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName(name)
        self.setValidator(filter.value)
        self.textChanged.connect(self._catch_and_name_text)

    def get_value(self):
        return self.text()

    def set_value(self, value: str):
        self.setText(value)

    def _catch_and_name_text(self, text: str):
        self.textChangedNamed.emit(self, text)