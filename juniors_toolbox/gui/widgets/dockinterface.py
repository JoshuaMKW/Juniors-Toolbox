from abc import abstractmethod
from pathlib import Path
from typing import Optional
from typing_extensions import Unpack

from PySide6.QtCore import Signal, Slot, QSize
from PySide6.QtGui import QCloseEvent, QHideEvent, QResizeEvent
from PySide6.QtWidgets import QDockWidget, QWidget

from juniors_toolbox.gui.widgets import ABCWidget
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs


class A_DockingInterface(QDockWidget, ABCWidget):
    closed = Signal(QDockWidget)
    hidden = Signal(QDockWidget)
    resized = Signal(QResizeEvent)

    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)

    @abstractmethod
    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None: ...

    @abstractmethod
    def __del__(self) -> None: ...

    @Slot(QCloseEvent)
    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        self.closed.emit(self)
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
