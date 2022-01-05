from PySide2.QtCore import Signal, SignalInstance
from PySide2.QtGui import QCloseEvent
from PySide2.QtWidgets import QDockWidget

class SyncedDockWidget(QDockWidget):
    closed: SignalInstance = Signal(QDockWidget)

    def closeEvent(self, event: QCloseEvent):
        super().closeEvent(event)
        self.closed.emit(self)
