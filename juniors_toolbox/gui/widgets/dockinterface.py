from abc import abstractmethod
from pathlib import Path
from typing import Optional
from typing_extensions import Unpack

from PySide6.QtCore import Signal, Slot, QSize, Qt, QPoint
from PySide6.QtGui import QCloseEvent, QHideEvent, QResizeEvent, QPaintEvent, QContextMenuEvent
from PySide6.QtWidgets import QDockWidget, QWidget, QStyle, QStylePainter, QStyleOptionFrame, QStyleOptionDockWidget, QMenu

from juniors_toolbox.gui.widgets import ABCWidget
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs


class A_DockingInterface(QDockWidget, ABCWidget):
    closed = Signal(QDockWidget)
    hidden = Signal(QDockWidget)
    resized = Signal(QResizeEvent)

    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._titleText: Optional[str] = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    @abstractmethod
    def populate(self, scene: Optional[SMSScene], *
                 args: VariadicArgs, **kwargs: VariadicKwargs) -> None: ...

    def get_context_menu(self, pos: QPoint) -> QMenu:
        return QMenu()

    def titleText(self):
        if self._titleText is None:
            return self.windowTitle()
        return self._titleText

    def setTitleText(self, text):
        self._titleText = text
        self.repaint()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.get_context_menu(event.pos())
        menu.exec()

    def paintEvent(self, event: QPaintEvent):
        painter = QStylePainter(self)
        if self.isFloating():
            options = QStyleOptionFrame()
            options.initFrom(self)
            painter.drawPrimitive(QStyle.PE_FrameDockWidget, options)
        options = QStyleOptionDockWidget()
        self.initStyleOption(options)
        options.title = self.titleText()
        painter.drawControl(QStyle.CE_DockWidgetTitle, options)

    @Slot(QCloseEvent)
    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        self.closed.emit(self)
        # event.ignore()
        # self.closed.emit(self)

    @Slot(QHideEvent)
    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        # self.hidden.emit(self)

    @Slot(QResizeEvent)
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resized.emit(event)

    def y_contains(self, y: int, h: int) -> bool:
        return (
            self.pos().y() <= y <= self.pos().y() + self.rect().height() or
            self.pos().y() <= y+h <= self.pos().y() + self.rect().height()
        )

    def x_contains(self, x: int, w: int) -> bool:
        return (
            self.pos().x() <= x < self.pos().x() + self.rect().width() or
            self.pos().x() <= x+w < self.pos().x() + self.rect().width()
        )
