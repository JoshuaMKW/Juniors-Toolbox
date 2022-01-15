from PySide6.QtCore import QSize, Signal, SignalInstance
from PySide6.QtGui import QCloseEvent, QHideEvent, QResizeEvent
from PySide6.QtWidgets import QDockWidget


class SyncedDockWidget(QDockWidget):
    closed: SignalInstance = Signal(QDockWidget)
    hidden: SignalInstance = Signal(QDockWidget)
    resized: SignalInstance = Signal(QResizeEvent)

    def __init__(self, title, parent=None):
        super().__init__(title, parent)

    def closeEvent(self, event: QCloseEvent):
        super().closeEvent(event)
        self.closed.emit(self)
        # self.closed.emit(self)

    def hideEvent(self, event: QHideEvent):
        super().hideEvent(event)
        # self.hidden.emit(self)

    def sizeHint(self) -> QSize:
        self.minimumSizeHint()

    def minimumSizeHint(self) -> QSize:
        return super().minimumSizeHint()
        titleSize = self.titleBarWidget().minimumSize()
        widgetSize = self.widget().minimumSize()
        margins = self.contentsMargins()
        return QSize(
            widgetSize.width() + margins.left() + margins.right(),
            titleSize.height() + widgetSize.height() + margins.top() + margins.bottom()
        )

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
