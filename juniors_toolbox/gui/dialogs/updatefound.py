from pathlib import Path
from typing import Iterable, Optional, Tuple

from github.GitRelease import GitRelease
from github.PaginatedList import PaginatedList

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
                               QToolBar, QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox, QCheckBox, QTextBrowser,
                               QVBoxLayout, QWidget)
from enum import IntEnum

from juniors_toolbox import __version__
from juniors_toolbox.update import ReleaseManager


class UpdateFoundDialog(QDialog):
    def __init__(self, manager: ReleaseManager, isMulti: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        if isMulti:
            self.setFixedSize(400, 190)
        else:
            self.setFixedSize(400, 160)

        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.CustomizeWindowHint, True)

        self.mainLayout = QVBoxLayout()

        self.titleText = QLabel()
        titleFont = self.titleText.font()
        titleFont.setBold(True)
        titleFont.setPointSize(16)
        self.titleText.setFont(titleFont)
        self.mainLayout.addWidget(self.titleText)

        self.descriptionText = QLabel()
        descriptionFont = self.descriptionText.font()
        descriptionFont.setPointSize(12)
        self.descriptionText.setFont(descriptionFont)
        self.mainLayout.addWidget(self.descriptionText)

        self.releasesView = QTextBrowser()
        self.releasesView.setAcceptRichText(True)
        releasesFont = self.releasesView.font()
        releasesFont.setPointSize(12)
        self.releasesView.setFont(releasesFont)

        self.buttonsLayout = QHBoxLayout()

        self.rejectButton = QPushButton("Maybe Later")
        self.acceptButton = QPushButton("Update")
        self.rejectButton.clicked.connect(self.reject)
        self.acceptButton.clicked.connect(self.accept)

        self.setLayout(self.mainLayout)

        self.manager = manager

    def display_updates(self, updates: PaginatedList[GitRelease]) -> QDialog.DialogCode:
        if updates.totalCount == 0:
            return QDialog.Rejected

        newestRelease: GitRelease = updates[0]

        self.setWindowModality(Qt.ApplicationModal)
        self.titleText.setText(
            f"{__name__} {newestRelease.tag_name} available!"
        )
        self.releasesView.setMarkdown(
            self.manager.compile_changelog_from(__version__)
        )

        retCode: QDialog.DialogCode = self.exec()  # type: ignore
        if retCode == QDialog.Accepted:
            self.manager.view(newestRelease)
        return retCode
