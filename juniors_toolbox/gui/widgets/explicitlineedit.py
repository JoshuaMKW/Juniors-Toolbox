from enum import Enum
from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QLineEdit

class ExplicitLineEdit(QLineEdit):
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

    def _catch_and_name_text(self, text: str):
        self.textChangedNamed.emit(self, text)