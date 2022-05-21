from pathlib import Path
from typing import Optional, Tuple
from unittest import skip
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

    def __init__(self, isMulti: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        if isMulti:
            self.setFixedSize(400, 190)
        else:
            self.setFixedSize(400, 160)

        layout = QVBoxLayout()

        conflictMessage = QLabel()
        conflictMessage.setWordWrap(True)

        allCheckBox = QCheckBox("Apply to all")
        allCheckBox.setCheckable(True)
        allCheckBox.toggled.connect(self.block)

        replaceButton = QPushButton()
        skipButton = QPushButton()
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
        self.allCheckBox = allCheckBox
        self.replaceButton = replaceButton
        self.skipButton = skipButton
        self.keepButton = keepButton
        self.choicesBox = choicesBox

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        layout.addWidget(self.conflictMessage)
        if isMulti:
            layout.addWidget(self.allCheckBox)
            layout.addWidget(frame)
        layout.addWidget(self.choicesBox)

        self.setLayout(layout)

        self.__actionRole: QDialogButtonBox.ButtonRole = None
        self.__blocked = False

    def set_paths(self, src: Path, dst: Path):
        self.setWindowTitle(
            f"Moving \"{src.name}\" from \"./{src.parent.name}\" to \"./{dst.parent.name}\""
        )

        srcType = "folder" if src.is_dir() else "file"
        dstType = "folder" if src.is_dir() else "file"

        self.conflictMessage.setText(
            f"The destination specified already has a {dstType} named \"{src.name}\""
        )
        self.replaceButton.setText(f"Replace the {dstType}")
        self.skipButton.setText(f"Skip this {srcType}")


    def resolve(self) -> Tuple[QDialog.DialogCode, ActionRole]:
        if not self.__blocked:
            return self.exec(), self.__actionRole
        return QDialog.DialogCode.Accepted, self.__actionRole

    @Slot(bool)
    def block(self, block: bool):
        self.__blocked = block
        self.allCheckBox.blockSignals(True)
        self.allCheckBox.setChecked(block)
        self.allCheckBox.blockSignals(False)

    def __accept_role(self, role: ActionRole):
        self.__actionRole = role
        self.accept()