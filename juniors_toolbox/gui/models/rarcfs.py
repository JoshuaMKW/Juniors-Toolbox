from asyncore import read
from logging import root
import os
from pathlib import Path, PurePath
from typing import Optional, Union

from juniors_toolbox.utils.rarc import (ResourceArchive, ResourceDirectory,
                                        ResourceFile)
from PySide6.QtCore import (QAbstractItemModel, QByteArray, QDataStream, QFile, QDir,
                            QFileInfo, QIODevice, QMimeData, QModelIndex,
                            QObject, QPersistentModelIndex, QPoint, QRect,
                            QRectF, QRegularExpression, QSize,
                            QSortFilterProxyModel, Qt, Signal, Slot)
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QImage,
                           QIntValidator, QMouseEvent, QPainter, QPainterPath,
                           QPaintEvent, QPen, QPolygon, QStandardItem,
                           QStandardItemModel, QTextCursor, QTransform)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog,
                               QFileSystemModel, QFormLayout, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout,
                               QLineEdit, QMenu, QMenuBar, QPlainTextEdit,
                               QPushButton, QSizePolicy, QSplitter,
                               QVBoxLayout, QWidget)


class JSystemFSModel(QAbstractItemModel):
    """
    Mimics QFileSystemModel with a watchdog and async updates, with RARC support
    """
    directoryLoaded = Signal(PurePath)
    fileRenamed = Signal(PurePath, str, str)
    rootPathChanged = Signal(PurePath)

    def __init__(self, rootPath: Path, readOnly: bool = True, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._rootPath = rootPath
        self._rootDirectory = PurePath()
        self._readOnly = readOnly
        self._nameFilterDisables = True
        self._filter = ""

        self._archives: dict[PurePath, ResourceArchive] = {}

    @property
    def rootPath(self) -> Path:
        return self._rootPath

    @rootPath.setter
    def rootPath(self, rootPath: Path) -> bool:
        if not rootPath.exists():
            return False
        self._rootPath = rootPath
        self.rootPathChanged.emit(rootPath)
        return True

    @property
    def rootDirectory(self) -> PurePath:
        return self._rootDirectory

    @rootDirectory.setter
    def rootDirectory(self, rootDirectory: PurePath) -> bool:
        self._rootDirectory = rootDirectory
        return self.update()

    @property
    def readOnly(self) -> bool:
        return self._readOnly

    @readOnly.setter
    def readOnly(self, readOnly: bool):
        self._readOnly = readOnly

    @property
    def nameFilterDisables(self) -> bool:
        return self._nameFilterDisables

    @nameFilterDisables.setter
    def nameFilterDisables(self, disables: bool):
        self._nameFilterDisables = disables
        self.update()

    @property
    def filter(self) -> QDir.Filters:
        return self._filter

    @filter.setter
    def filter(self, filter: QDir.Filters):
        self._filter = filter
        self.update()

    @property
    def nameFilters(self) -> list[str]:
        return self._nameFilters

    @filter.setter
    def nameFilters(self, filters: list[str]):
        self._nameFilters = filter
        self.update()

    def is_file(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        if self.is_child_of_archive(index):
            archive, truncatedPath = self._get_parent_archive(path)
            if archive is None:
                return False
            file = archive.get_handle(truncatedPath)
            if file is None:
                return False
            return file.is_file()

        return os.path.isfile(path)

    def is_dir(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        if self.is_child_of_archive(index):
            archive, truncatedPath = self._get_parent_archive(path)
            if archive is None:
                return False
            file = archive.get_handle(truncatedPath)
            if file is None:
                return False
            return file.is_directory()

        return os.path.isdir(path)

    def is_archive(self, index: QModelIndex) -> bool:
        ...

    def is_child_of_archive(self, index: QModelIndex) -> bool:
        ...

    def is_yaz0_compressed(self, index: QModelIndex) -> bool:
        ...

    def get_icon(self, index: QModelIndex) -> QIcon:
        ...

    def get_info(self, index: QModelIndex) -> QFileInfo:
        ...

    def get_name(self, index: QModelIndex) -> str:
        ...

    def get_path(self, index: QModelIndex) -> PurePath:
        ...

    def get_permissions(self, index: QModelIndex) -> QFile.Permissions:
        ...

    def get_size(self, index: QModelIndex) -> int:
        ...

    def get_type(self, index: QModelIndex) -> str:
        ...

    def mkdir(self, parent: QModelIndex, name: str) -> QModelIndex:
        ...

    def remove(self, index: QModelIndex) -> bool:
        ...

    def rmdir(self, index: QModelIndex) -> bool:
        ...

    def canFetchMore(self, parent: QModelIndex | QPersistentModelIndex) -> bool:
        return True

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        return super().canDropMimeData(data, action, row, column, parent)

    def hasChildren(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return False

        return self.is_dir(parent) or self.is_archive(parent)

    @Slot()
    def update(self) -> bool:
        ...

    def _get_parent_archive(self, path: PurePath) -> tuple[ResourceArchive | None, PurePath]:
        oldPath = path
        while path not in self._archives:
            if len(path.parts) == 0:
                return None, PurePath()
            if not path.is_relative_to(self.rootPath):
                return None, PurePath()
            path = Path(*path.parts[:-1])
        return self._archives[path], oldPath.relative_to(path)
    

