from enum import Enum
from PySide2.QtCore import Signal
from PySide2.QtGui import QDoubleValidator, QIntValidator
from PySide2.QtWidgets import QLineEdit

class ExplicitLineEdit(QLineEdit):
    textChangedNamed = Signal(QLineEdit)

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
        self.textChangedNamed.emit(self)