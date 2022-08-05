import time
from enum import IntEnum
from typing import Optional

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTextEdit, QWidget


class ConsoleLogWidget(A_DockingInterface):
    class Level(IntEnum):
        LOG = 0
        INFO = 1
        WARNING = 2
        ERROR = 3

    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.setMinimumSize(300, 180)

        self.messageLog = QTextEdit()
        font = self.messageLog.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.messageLog.setFont(font)
        self.messageLog.setStyleSheet("background-color: rgb(10, 12, 16)")

        self.messageLog.setReadOnly(True)

        self.setWidget(self.messageLog)

    def log(self, scope: str, message: str) -> None:
        self._log_message(scope, message, ConsoleLogWidget.Level.LOG)

    def info(self, scope: str, message: str) -> None:
        self._log_message(scope, message, ConsoleLogWidget.Level.INFO)

    def warning(self, scope: str, message: str) -> None:
        self._log_message(scope, message, ConsoleLogWidget.Level.WARNING)

    def error(self, scope: str, message: str) -> None:
        self._log_message(scope, message, ConsoleLogWidget.Level.ERROR)

    def _log_message(self, scope: str, message: str, level: "ConsoleLogWidget.Level") -> None:
        t = time.localtime()
        current_time = time.strftime("%H:%M:%S", t)

        if level == ConsoleLogWidget.Level.LOG:
            self.messageLog.setTextColor(QColor(Qt.white))
        elif level == ConsoleLogWidget.Level.INFO:
            self.messageLog.setTextColor(QColor(70, 110, 255))
        elif level == ConsoleLogWidget.Level.WARNING:
            self.messageLog.setTextColor(QColor(100, 160, 10))
        elif level == ConsoleLogWidget.Level.ERROR:
            self.messageLog.setTextColor(QColor(255, 80, 80))

        self.messageLog.append(
            f"[{current_time}] {scope}: {message}"
        )
