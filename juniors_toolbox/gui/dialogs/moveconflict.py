from pathlib import Path
from tkinter import W
from typing import Optional
from PySide6.QtCore import (QAbstractItemModel, QDataStream, QEvent, QIODevice,
                            QLine, QMimeData, QModelIndex, QObject, QPoint,
                            QSize, Qt, QThread, QTimer, QUrl, Signal,
                            SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QDragEnterEvent,
                           QDragLeaveEvent, QDragMoveEvent, QDropEvent, QIcon,
                           QImage, QKeyEvent, QMouseEvent, QPaintDevice,
                           QPainter, QPaintEvent, QPalette, QPixmap,
                           QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QMenuBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem,
                               QSplitter, QStyle, QStyleOptionComboBox,
                               QStylePainter, QTableWidget, QTableWidgetItem,
                               QToolBar, QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox, QCheckBox,
                               QVBoxLayout, QWidget)
from enum import IntEnum


class MoveConflictDialog(QDialog):
    class ActionRole(IntEnum):
        REPLACE = 0
        SKIP = 1
        KEEP = 2

    def __init__(self, src: Path, dst: Path, isMulti: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Moving \"{src.name}\" from \"./{src.parent.name}\" to \"./{dst.parent.name}\""
        )
        if isMulti:
            self.setFixedSize(400, 190)
        else:
            self.setFixedSize(400, 160)

        layout = QVBoxLayout()

        conflictMessage = QLabel()
        conflictMessage.setWordWrap(True)

        allCheckBox = QCheckBox("Apply to all")
        allCheckBox.setCheckable(True)

        self.allCheckBox = allCheckBox

        srcType = "folder" if src.is_dir() else "file"
        dstType = "folder" if src.is_dir() else "file"

        conflictMessage.setText(
            f"The destination specified already has a {dstType} named \"{src.name}\""
        )
        replaceButton = QPushButton(f"Replace the {dstType}")
        skipButton = QPushButton(f"Skip this {srcType}")
        keepButton = QPushButton("Keep both (rename)")

        replaceButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        skipButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        keepButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        replaceButton.clicked.connect(lambda: self.__accept_role(MoveConflictDialog.ActionRole.REPLACE))
        skipButton.clicked.connect(lambda: self.__accept_role(MoveConflictDialog.ActionRole.SKIP))
        keepButton.clicked.connect(lambda: self.__accept_role(MoveConflictDialog.ActionRole.KEEP))

        choicesBox = QDialogButtonBox(Qt.Vertical)
        choicesBox.addButton(replaceButton, QDialogButtonBox.ButtonRole.AcceptRole)
        choicesBox.addButton(skipButton, QDialogButtonBox.ButtonRole.AcceptRole)
        choicesBox.addButton(keepButton, QDialogButtonBox.ButtonRole.AcceptRole)
        choicesBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.conflictMessage = conflictMessage
        self.choicesBox = choicesBox

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        layout.addWidget(self.conflictMessage)
        if isMulti:
            layout.addWidget(self.allCheckBox)
            layout.addWidget(frame)
        layout.addWidget(self.choicesBox)

        self.setLayout(layout)

        self.actionRole: QDialogButtonBox.ButtonRole = None

    def __accept_role(self, role: ActionRole):
        self.actionRole = role
        self.accept()