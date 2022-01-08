from PySide2.QtCore import QSize, Signal, SignalInstance
from PySide2.QtGui import QCloseEvent, QHideEvent, QResizeEvent
from PySide2.QtWidgets import QDockWidget

class SyncedDockWidget(QDockWidget):
    closed: SignalInstance = Signal(QDockWidget)
    hidden: SignalInstance = Signal(QDockWidget)
    resized: SignalInstance = Signal(QResizeEvent)

    def closeEvent(self, event: QCloseEvent):
        super().closeEvent(event)
        self.closed.emit(self)

    def hideEvent(self, event: QHideEvent):
        super().hideEvent(event)
        self.hidden.emit(self)

    def minimumSizeHint(self) -> QSize:
        titleSize = self.titleBarWidget().minimumSize()
        widgetSize = self.widget().minimumSize()
        return QSize(widgetSize.width(), titleSize.height() + widgetSize.height())

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.resized.emit(event)

    def y_contains(self, y: int, h: int) -> bool:
        #print(self.objectName() + "(y):")
        #print(f"{self.pos().y()} <= {y} <= {self.pos().y() + self.rect().height()}")
        #print(f"{self.pos().y()} <= {y+h} <= {self.pos().y() + self.rect().height()}")
        return (
            self.pos().y() <= y <= self.pos().y() + self.rect().height() or
            self.pos().y() <= y+h <= self.pos().y() + self.rect().height()
        )

    def x_contains(self, x: int, w: int) -> bool:
        #print(self.objectName() + "(x):")
        #print(f"{self.pos().x()} <= {x} < {self.pos().x() + self.rect().width()}")
        #print(f"{self.pos().x()} <= {x+w} < {self.pos().x() + self.rect().width()}")
        return (
            self.pos().x() <= x < self.pos().x() + self.rect().width() or
            self.pos().x() <= x+w < self.pos().x() + self.rect().width()
        )