from __future__ import annotations
from abc import ABC, abstractmethod

from dataclasses import dataclass
from enum import IntEnum
from io import BytesIO
from logging import root
import os
from pathlib import Path, PurePath
import shutil
import time
from typing import Any, Optional, Union, overload
from isort import file

from numpy import source
from juniors_toolbox.gui.images import get_icon

from juniors_toolbox.utils.rarc import (A_ResourceHandle, FileConflictAction, ResourceArchive, ResourceDirectory,
                                        ResourceFile)
from PySide6.QtCore import (QAbstractItemModel, QByteArray, QDataStream, QFile, QDir, QFileSystemWatcher, QUrl,
                            QFileInfo, QIODevice, QMimeData, QModelIndex, QIdentityProxyModel,
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


class A_JSystemFSImporter(ABC):
    def __init__(self, model: JSystemFSModel) -> None:
        super().__init__()
        self.sourceModel = model

    @abstractmethod
    def process(self, src: Path | QMimeData, parent: QModelIndex |
                QPersistentModelIndex) -> PurePath | None: ...


class A_JSystemFSExporter(ABC):
    def __init__(self, model: JSystemFSModel) -> None:
        super().__init__()
        self.sourceModel = model

    @abstractmethod
    def process(self, index: QModelIndex | QPersistentModelIndex,
                dest: Path | QMimeData) -> PurePath | None: ...


class JSystemFileImporter(A_JSystemFSImporter):
    def process(self, src: Path | QMimeData, parent: QModelIndex | QPersistentModelIndex) -> PurePath | None:
        return super().process(src, parent)


class JSystemFileExporter(A_JSystemFSExporter):
    def process(self, index: QModelIndex | QPersistentModelIndex, dest: Path | QMimeData) -> PurePath | None:
        return super().process(index, dest)


class JSystemFSModel(QAbstractItemModel):
    """
    Mimics QFileSystemModel with a watchdog and async updates, with RARC support
    """
    directoryLoaded = Signal(PurePath)
    fileRenamed = Signal(PurePath, str, str)
    rootPathChanged = Signal(PurePath)
    conflictFound = Signal(PurePath, PurePath)

    FileIconRole = Qt.DecorationRole
    FilePathRole = Qt.UserRole + 1
    FileNameRole = Qt.UserRole + 2

    ExtensionToTypeMap: dict[str, str] = {
        ".szs": "Yaz0 Compressed File",
        ".arc": "Archive (RARC)",
        ".thp": "Nintendo JPEG Video",
        ".map": "Codewarrior Symbol Map",
        ".me": "Dummy File",
        ".bmg": "Message Table",
        ".bnr": "Game Banner",
        ".bin": "Binary Data",
        ".ral": "Rail Table",
        ".ymp": "Pollution Heightmap",
        ".bti": "Texture Image",
        ".blo": "2D Layout",
        ".bcr": "Controller Rumble Script",
        ".bfn": "Font",
        ".bmd": "J3D Model",
        ".bdl": "J3D Model",
        ".bmt": "J3D Material Table",
        ".bck": "J3D Bone Animation",
        ".btp": "J3D Texture Pattern Animation",
        ".btk": "J3D Texture Animation",
        ".brk": "J3D Texture Register Animation",
        ".bpk": "J3D Color Animation",
        ".blk": "J3D Vertex Animation (UNUSED)",
        ".col": "Collision Model",
        ".jpa": "JSystem Particle Effect",
        ".sb": "SPC Script (Sunscript)",
        ".prm": "Parameter Table",
        ".pad": "Controller Input Recording",
        ".bmp": "Bitmap Image",
        ".bas": "Animation Sound Index",
        ".aaf": "Audio Initialization Info",
        ".asn": "Audio Name Table",
        ".bms": "Audio Sequence",
        ".aw": "Audio Archive",
        ".afc": "Streamed Audio (UNUSED)",
        ".ws": "Wave System Table",
        ".bnk": "Instrument Bank",
    }

    @dataclass
    class _HandleInfo:
        path: PurePath
        parent: "JSystemFSModel._HandleInfo" | None
        children: list["JSystemFSModel._HandleInfo"]
        isFile: bool
        size: int
        loaded: bool = False

        def __repr__(self) -> str:
            if self.parent:
                return f"Handle(\"{self.path.parent.name}/{self.path.name}\", parent={self.parent.path.name})"
            return f"Handle(\"{self.path.parent.name}/{self.path.name}\", parent=None)"

    class _HandleType(IntEnum):
        FILE = 0
        DIRECTORY = 1
        ARCHIVE = 2

    def __init__(self, rootPath: Path | None, readOnly: bool = True, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._rootPath = rootPath
        self._rootDirectory = PurePath()
        self._readOnly = readOnly
        self._nameFilterDisables = True
        self._filter = QDir.Filter.AllEntries
        self._nameFilters: list[str] = []

        self._fileSystemWatcher = QFileSystemWatcher(self)
        self._fileSystemWatcher.fileChanged.connect(self.file_changed)
        self._fileSystemWatcher.directoryChanged.connect(
            self.directory_changed)
        self._archives: dict[PurePath, ResourceArchive] = {}

        if rootPath is not None:
            self._fileSystemWatcher.addPath(str(rootPath))

        self._icons: dict[str, QIcon] = {}
        self._conflictAction: FileConflictAction | None = None

        self._initialize_icons()
        self.update()

    @property
    def rootPath(self) -> Path | None:
        return self._rootPath

    @rootPath.setter
    def rootPath(self, rootPath: Path | None) -> bool:
        if rootPath == self._rootPath:
            return True

        self._fileSystemWatcher.removePath(str(self._rootPath))
        self._rootPath = rootPath
        if rootPath is None:
            return False

        if not rootPath.exists():
            return False

        self._fileSystemWatcher.addPath(str(rootPath))
        self.update()

        self.rootPathChanged.emit(rootPath)
        self.layoutChanged.emit()
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
        self._nameFilters = filters
        self.update()

    def is_loaded(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return True

        parentInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        return parentInfo.loaded

    def is_file(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        if self.is_child_of_archive(index):
            archiveIndex = self.get_parent_archive(index)
            if not archiveIndex.isValid():
                return False

            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if not path.is_relative_to(archivePath):
                return False

            virtualPath = path.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return False

            return handle.is_file()

        return os.path.isfile(path)

    def is_dir(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        if self.is_child_of_archive(index):
            archiveIndex = self.get_parent_archive(index)
            if not archiveIndex.isValid():
                return False

            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return False

            if not path.is_relative_to(archivePath):
                return False

            virtualPath = path.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return False

            return handle.is_directory()

        return os.path.isdir(path)

    def is_archive(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        if self.is_child_of_archive(index):
            archiveIndex = self.get_parent_archive(index)
            if not archiveIndex.isValid():
                return False

            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return False

            if not path.is_relative_to(archivePath):
                return False

            virtualPath = path.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return False

            return handle.is_file() and handle.get_extension() == ".arc"

        return os.path.isfile(path) and path.suffix == ".arc"

    def is_populated(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        path = self.get_path(index)

        archiveIndex = self.get_parent_archive(index)
        if archiveIndex.isValid():
            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return False

            if not path.is_relative_to(archivePath):
                return False

            virtualPath = path.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return False

            if handle.is_directory():
                return len(handle.get_handles()) > 0

            if handle.is_file() and handle.get_extension() == ".arc":
                return not ResourceArchive.is_archive_empty(
                    BytesIO(handle.get_raw_data())
                )

        if os.path.isdir(path):
            for _ in Path(path).glob("*"):
                return True
            return False

        if os.path.isfile(path) and path.suffix == ".arc":
            with open(path, "rb") as f:
                isEmpty = ResourceArchive.is_archive_empty(f)
            return not isEmpty

        return False

    def is_child_of_archive(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        parent = index.parent()
        while parent.isValid():
            if self.get_path(parent) in self._archives:
                return True
            parent = parent.parent()
        return False

    def is_yaz0_compressed(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        path = self.get_path(index)
        if path.suffix != ".szs":
            return False
        with open(path, "rb") as f:
            magic = f.read(4)
        return magic == b"Yaz0"

    def get_conflict_action(self) -> FileConflictAction | None:
        return self._conflictAction

    def set_conflict_action(self, action: FileConflictAction):
        self._conflictAction = action

    def get_parent_archive(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        parent = index.parent()
        while parent.isValid():
            path = self.get_path(parent)
            if path in self._archives:
                return parent
            parent = parent.parent()
        return QModelIndex()

    def get_path_index(self, path: PurePath) -> QModelIndex:
        if self.rootPath is None:
            return QModelIndex()

        if str(path) in {"", "."}:
            return self.createIndex(0, 0, self._fileSystemCache)

        if not path.is_relative_to(self.rootPath):
            return QModelIndex()

        relPath = path.relative_to(self.rootPath)
        handleInfo = self._fileSystemCache

        column = 0
        for part in relPath.parts[1:]:
            row = 0
            for child in handleInfo.children:
                if child.path.name == part:
                    handleInfo = child
                    continue
                row += 1
            else:
                return QModelIndex()

        return self.createIndex(row, column, handleInfo)

    def get_icon(self, index: QModelIndex | QPersistentModelIndex) -> QIcon:
        return self.data(index, self.FileIconRole)

    def get_name(self, index: QModelIndex | QPersistentModelIndex) -> str:
        return self.data(index, self.FileNameRole)

    def get_path(self, index: QModelIndex | QPersistentModelIndex) -> PurePath:
        return self.data(index, self.FilePathRole)

    def get_size(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if not index.isValid():
            return -1

        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        return handleInfo.size

    def get_type(self, index: QModelIndex | QPersistentModelIndex) -> str:
        if not index.isValid():
            return "NOT FOUND"

        name = self.get_name(index)
        if self.is_file(index):
            return self.ExtensionToTypeMap.get(name, "File")
        return "Folder"

    def move(self, index: QModelIndex | QPersistentModelIndex, parent: QModelIndex | QPersistentModelIndex, action: FileConflictAction = FileConflictAction.REPLACE) -> QModelIndex:
        self.set_conflict_action(action)

        thisParent = index.parent()
        thisRow = index.row()
        destRow = self.rowCount(parent)

        if not self.moveRow(
            thisParent,
            thisRow,
            parent,
            destRow
        ):
            return QModelIndex()

        return self.createIndex(destRow, 0, parent)

    def rename(self, index: QModelIndex | QPersistentModelIndex, name: str, action: FileConflictAction | None = None) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        parentInfo = handleInfo.parent
        if parentInfo is None:
            return QModelIndex()

        thisPath = self.get_path(index)
        destPath = thisPath.with_name(name)

        if os.path.exists(destPath) and action == FileConflictAction.SKIP:
            return QModelIndex()

        if action is None:
            self.conflictFound.emit(thisPath, destPath)
            while (action := self.get_conflict_action()) is None:
                time.sleep(0.1)

        archiveIndex = self.get_parent_archive(index)
        if archiveIndex.isValid():
            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return QModelIndex()

            virtualPath = thisPath.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return QModelIndex()

            successful = handle.rename(name, action=action)
            if not successful:
                return QModelIndex()

            if action == FileConflictAction.REPLACE:
                for i, subHandle in enumerate(parentInfo.children):
                    if subHandle.path.name == name:
                        self.removeRow(i, index.parent())
                handleInfo.path = handleInfo.path.with_name(handle.get_name())

            elif action == FileConflictAction.KEEP:
                handleInfo.path = handleInfo.path.with_name(handle.get_name())

            newIndex = self.createIndex(
                parentInfo.children.index(handleInfo),
                0,
                handleInfo
            )
            return newIndex

        if os.path.exists(destPath):
            if os.path.isdir(destPath):
                if action == FileConflictAction.REPLACE:
                    shutil.rmtree(destPath)
                    os.rename(thisPath, destPath)
                    for i, subHandle in enumerate(parentInfo.children):
                        if subHandle.path.name == name:
                            self.removeRow(i, index.parent())
                    handleInfo.path = handleInfo.path.with_name(name)

                elif action == FileConflictAction.KEEP:
                    newPath = self._resolve_path_conflict(name, index.parent())
                    if newPath is None:
                        return QModelIndex()
                    os.rename(thisPath, newPath)
                    handleInfo.path = handleInfo.path.with_name(newPath.name)

                newIndex = self.createIndex(
                    parentInfo.children.index(handleInfo),
                    0,
                    handleInfo
                )
                return newIndex

            if action == FileConflictAction.REPLACE:
                os.replace(thisPath, destPath)
                for i, subHandle in enumerate(parentInfo.children):
                    if subHandle.path.name == name:
                        self.removeRow(i, index.parent())
                handleInfo.path = handleInfo.path.with_name(name)

            elif action == FileConflictAction.KEEP:
                newPath = self._resolve_path_conflict(name, index.parent())
                if newPath is None:
                    return QModelIndex()
                os.rename(thisPath, newPath)
                handleInfo.path = handleInfo.path.with_name(newPath.name)

        os.rename(thisPath, destPath)
        handleInfo.path = handleInfo.path.with_name(name)

        return index

    def remove(self, index: QModelIndex | QPersistentModelIndex) -> bool:
        if not index.isValid():
            return False

        parentIndex = index.parent()
        parentInfo: JSystemFSModel._HandleInfo = parentIndex.internalPointer()
        thisInfo: JSystemFSModel._HandleInfo = index.internalPointer()

        path = self.get_path(index)
        if os.path.isfile(path):
            os.remove(path)
            parentInfo.children.remove(thisInfo)
            return True

        if os.path.exists(path):
            return False

        archiveIndex = self.get_parent_archive(index)
        if not archiveIndex.isValid():
            return False

        archivePath = self.get_path(archiveIndex)
        archive = self._archives[archivePath]
        if archive is None:
            return False

        if not archive.remove_path(path):
            return False

        parentInfo.children.remove(thisInfo)
        return True

    def import_path(self, data: QMimeData, destinationParent: QModelIndex | QPersistentModelIndex, action: FileConflictAction | None = None) -> bool:
        if not destinationParent.isValid():
            return False

        # Path importing is a file
        if not data.hasFormat("x-application/jsystem-fs-data"):
            return False

        importData = data.data("x-application/jsystem-fs-data")
        dataStream = QDataStream(importData, QDataStream.ReadOnly)

        isVirtual = dataStream.readBool()
        if isVirtual:
            successful = self._import_virtual_path(
                dataStream, destinationParent, action)
        else:  # We can save on resources here because the path exists on the filesystem
            successful = self._import_fs_path(
                dataStream, destinationParent, action)

        return successful

    def export_path(self, data: QMimeData, pathIndex: QModelIndex | QPersistentModelIndex) -> bool:
        if not pathIndex.isValid():
            return False

        dataStream = QDataStream(b"", QDataStream.WriteOnly)

        parentArchiveIndex = self.get_parent_archive(pathIndex)

        isVirtual = parentArchiveIndex.isValid()
        dataStream.writeBool(isVirtual)

        if isVirtual:  # Within an archive
            successful = self._export_virtual_path(
                dataStream, pathIndex, parentArchiveIndex)
        else:
            successful = self._export_fs_path(
                dataStream, pathIndex)

        return successful

    def mkdir(self, parent: QModelIndex | QPersistentModelIndex, name: str) -> QModelIndex:
        if not parent.isValid():
            return QModelIndex()

        parentPath = self.get_path(parent)
        parentInfo: JSystemFSModel._HandleInfo = parent.internalPointer()

        row = len(parentInfo.children)
        column = 0

        if not os.path.isdir(parentPath):
            if self.is_archive(parent):
                archive = self._archives[parentPath]
                dirHandle = archive.new_directory(name)
                if dirHandle is None:
                    return QModelIndex()

            elif self.is_child_of_archive(parent):
                archiveIndex = self.get_parent_archive(parent)
                if not archiveIndex.isValid():
                    return QModelIndex()

                archivePath = self.get_path(archiveIndex)
                archive = self._archives[archivePath]

                virtualPath = parentPath.relative_to(archivePath)
                parentHandle = archive.get_handle(virtualPath)
                if parentHandle is None:
                    return QModelIndex()

                dirHandle = parentHandle.new_directory(name)
                if dirHandle is None:
                    return QModelIndex()

            handleInfo = JSystemFSModel._HandleInfo(
                parentPath / name, parentInfo, [], False, 0
            )
            parentInfo.children.append(handleInfo)

            return self.createIndex(row, column, handleInfo)

        if os.path.isdir(parentPath.parent) and not os.path.exists(parentPath / name):
            os.mkdir(parentPath / name)

            handleInfo = JSystemFSModel._HandleInfo(
                parentPath / name, parentInfo, [], False, 0
            )
            parentInfo.children.append(handleInfo)

        return self.createIndex(row, column, handleInfo)

    def rmdir(self, index: QModelIndex | QPersistentModelIndex) -> bool:
        if not index.isValid():
            return False

        parentIndex = index.parent()
        parentInfo: JSystemFSModel._HandleInfo = parentIndex.internalPointer()
        thisInfo: JSystemFSModel._HandleInfo = index.internalPointer()

        path = self.get_path(index)
        if os.path.isdir(path):
            shutil.rmtree(path)
            parentInfo.children.remove(thisInfo)
            return True

        if os.path.exists(path):
            return False

        archiveIndex = self.get_parent_archive(index)
        if not archiveIndex.isValid():
            return False

        archivePath = self.get_path(archiveIndex)
        archive = self._archives[archivePath]

        if not archive.remove_path(path):
            return False

        parentInfo.children.remove(thisInfo)
        return True

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsDropEnabled
        itemFlags = Qt.ItemIsDragEnabled | Qt.ItemIsEnabled | Qt.ItemIsEditable
        if self.is_dir(index):
            itemFlags |= Qt.ItemIsDragEnabled
        return itemFlags

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return -1

        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        isFile = handleInfo.isFile
        name = handleInfo.path.name
        stem = handleInfo.path.stem
        extension = handleInfo.path.suffix

        _type = self.ExtensionToTypeMap[extension] if isFile else "Folder"

        if role == Qt.DisplayRole:
            return name

        if role == Qt.DecorationRole:
            if isFile:
                if extension in self._icons:
                    return self._icons[extension]
                return self._icons["file"]
            return self._icons["folder"]

        if role == Qt.EditRole:
            return name

        if role == Qt.ToolTipRole:
            return _type

        if role == Qt.WhatsThisRole:
            return _type

        if role == Qt.SizeHintRole:
            return QSize(80, 90)

        if role == self.FileNameRole:
            return stem

        if role == self.FilePathRole:
            return handleInfo.path

    def setData(self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = Qt.DisplayRole) -> bool:
        if not index.isValid():
            return False

        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        path = handleInfo.path

        changed = False
        if role == Qt.DisplayRole:
            newPath = path.parent / value
            changed = self.rename(index, newPath)

        if role == Qt.EditRole:
            newPath = path.parent / value
            changed = self.rename(index, newPath)

        if role == self.FileNameRole:
            newPath = path.parent / (value.split(".")[0] + "." + path.suffix)
            changed = self.rename(index, newPath)

        if role == self.FilePathRole:
            changed = self.rename(index, value)

        if changed:
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    def canFetchMore(self, parent: QModelIndex | QPersistentModelIndex) -> bool:
        if not parent.isValid():
            return False
        handleInfo: JSystemFSModel._HandleInfo = parent.internalPointer()
        return self.rootPath is not None and handleInfo.loaded is False

    def fetchMore(self, parent: QModelIndex | QPersistentModelIndex) -> None:
        if self.rootPath is None:
            return

        if not self.rootPath.exists():
            return

        if not parent.isValid():
            return

        self._cache_path(parent)

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        return super().canDropMimeData(data, action, row, column, parent)

    def hasChildren(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return True

        return self.is_populated(parent)

    def hasIndex(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        return self.index(row, column, parent).isValid()

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:
        if column > 0:
            return QModelIndex()

        if row < 0 or column < 0:
            return QModelIndex()

        if not parent.isValid():
            return self.createIndex(row, column, self._fileSystemCache)

        if not self.hasChildren(parent):
            return QModelIndex()
        handleInfo: JSystemFSModel._HandleInfo = parent.internalPointer()  # type: ignore

        if row >= len(handleInfo.children):
            return QModelIndex()
        return self.createIndex(row, column, handleInfo.children[row])

    @overload
    def parent(self) -> QObject: ...

    @overload
    def parent(self, child: QModelIndex | QPersistentModelIndex): ...

    def parent(self, child: QModelIndex | QPersistentModelIndex | None = None) -> QModelIndex:  # type: ignore
        if child is None:
            return super().parent()

        if not child.isValid():
            return QModelIndex()

        if child.column() > 0:
            return QModelIndex()

        handleInfo: JSystemFSModel._HandleInfo = child.internalPointer()
        parentInfo = handleInfo.parent
        if parentInfo is None:
            return QModelIndex()

        pParentInfo = parentInfo.parent
        if pParentInfo is None:
            return self.createIndex(0, 0, self._fileSystemCache)

        return self.createIndex(pParentInfo.children.index(parentInfo), 0, parentInfo)

    def mimeData(self, indexes: list[QModelIndex | QPersistentModelIndex]) -> QMimeData:
        urls: list[QUrl] = []
        for index in indexes:
            urls.append(
                QUrl(
                    str(self.get_path(index))
                )
            )
        mimeData = QMimeData()
        mimeData.setUrls(urls)
        return mimeData

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        folder = self.get_path(parent)
        for url in data.urls():
            urlPath = PurePath(url.toLocalFile())
            dstPath = folder / urlPath.name
            if os.path.exists(dstPath):
                continue
            os.rename(urlPath, dstPath)
        return True

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return 1 if self._fileSystemCache.size >= 0 else 0
        handleInfo: JSystemFSModel._HandleInfo = parent.internalPointer()
        return len(handleInfo.children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 1

    def removeRows(self, row: int, count: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return False

        handleInfo: JSystemFSModel._HandleInfo = parent.internalPointer()
        if row not in range(len(handleInfo.children)):
            return False

        self.beginRemoveRows(parent, row, row+count)

        try:
            for i in range(row+count, row+1, -1):
                handleInfo.children.pop(i)
        except IndexError:
            self.endRemoveRows()
            return False

        self.endRemoveRows()
        return True

    def removeColumns(self, column: int, count: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        return False

    def insertRows(self, row: int, count: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        return super().insertRows(row, count, parent)

    def insertColumns(self, row: int, count: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        return super().insertColumns(row, count, parent)

    def moveRows(self, sourceParent: QModelIndex | QPersistentModelIndex, sourceRow: int, count: int, destinationParent: QModelIndex | QPersistentModelIndex, destinationChild: int) -> bool:
        if not sourceParent.isValid() or not destinationParent.isValid():
            return False

        sourceParentInfo: JSystemFSModel._HandleInfo = sourceParent.internalPointer()
        destParentInfo: JSystemFSModel._HandleInfo = destinationParent.internalPointer()
        destParentPath = destParentInfo.path

        if destinationChild not in range(len(destParentInfo.children)):
            return False

        # Check if the source is part of an archive
        sourceArchive: Optional[ResourceArchive] = None
        sourceArchiveIndex = self.get_parent_archive(sourceParent)
        sourceArchivePath = self.get_path(sourceArchiveIndex)
        if sourceArchiveIndex.isValid():
            sourceArchive = self._archives[sourceArchivePath]

        # Check if the destination is part of an archive
        destArchive: Optional[ResourceArchive] = None
        destArchiveIndex = self.get_parent_archive(destinationParent)
        destArchivePath = self.get_path(destArchiveIndex)
        if destArchiveIndex.isValid():
            destArchive = self._archives[destArchivePath]

        successful = True
        self.beginMoveRows(sourceParent, sourceRow, sourceRow +
                           count, destinationParent, destinationChild)

        conflictAction = self.get_conflict_action()
        for i in range(sourceRow+count, sourceRow-1, -1):  # Reverse to preserve indices
            thisIndex = self.index(i, 0, sourceParent)
            if not thisIndex.isValid():
                self._conflictAction = None
                return False

            thisInfo: JSystemFSModel._HandleInfo = thisIndex.internalPointer()
            thisPath = thisInfo.path
            destPath = destParentPath / thisPath.name

            if sourceArchive:  # Source exists in an archive
                virtualSourcePath = thisPath.relative_to(sourceArchivePath)
                sourceHandle = sourceArchive.get_handle(virtualSourcePath)
                if sourceHandle is None:
                    successful = False
                    continue

                if destArchive:  # Destination exists in an archive
                    virtualDestPath = destPath.relative_to(destArchivePath)
                    destHandle = destArchive.get_handle(virtualDestPath)
                    if destHandle:  # Destination move exists
                        if conflictAction is None:
                            self.conflictFound.emit(thisPath, destPath)
                            while (conflictAction := self.get_conflict_action()) is None:
                                time.sleep(0.1)

                        if conflictAction == FileConflictAction.REPLACE:
                            for i, handleInfo in enumerate(destParentInfo.children):
                                if handleInfo.path.name == destHandle.get_name():
                                    self.removeRow(i, destinationParent)
                                    break

                        elif conflictAction == FileConflictAction.KEEP:
                            newPath = self._resolve_path_conflict(
                                thisPath.name, destinationParent)
                            if newPath is None:
                                return QModelIndex()
                            destPath = newPath
                            virtualDestPath = destPath.relative_to(
                                destArchivePath)

                        else:  # Skip
                            continue

                    # Archives are the same, internal move
                    if sourceArchive == destArchive:
                        successful &= sourceHandle.rename(
                            virtualDestPath, action=FileConflictAction.REPLACE)
                        continue

                    sourceParentHandle = sourceHandle.get_parent()
                    if sourceParentHandle is None:
                        successful = False
                        continue

                    destParentHandle = destArchive.get_handle(
                        virtualDestPath.parent)
                    if destParentHandle is None:
                        successful = False
                        continue

                    # Archives are different, move between them
                    sourceParentHandle.remove_handle(sourceHandle)
                    destParentHandle.add_handle(sourceHandle)
                    continue

                # Destination exists in the filesystem
                if os.path.exists(destPath):
                    if conflictAction is None:
                        self.conflictFound.emit(thisPath, destPath)
                        while (conflictAction := self.get_conflict_action()) is None:
                            time.sleep(0.1)

                    if conflictAction == FileConflictAction.REPLACE:
                        for i, handleInfo in enumerate(destParentInfo.children):
                            if handleInfo.path.name == destPath.name:
                                self.removeRow(i, destinationParent)
                                break

                    elif conflictAction == FileConflictAction.KEEP:
                        newPath = self._resolve_path_conflict(
                            thisPath.name, destinationParent)
                        if newPath is None:
                            successful = False
                            continue
                        destPath = newPath
                        virtualDestPath = destPath.relative_to(destArchivePath)

                    else:  # Skip
                        continue

                # Move handle from archive into filesystem
                successful &= sourceHandle.export_to(Path(destPath.parent))

            # Source exists in filesystem
            if destArchive:  # Destination exists in an archive
                virtualDestPath = destPath.relative_to(destArchivePath)
                destHandle = destArchive.get_handle(virtualDestPath)
                if destHandle:  # Destination move exists
                    if conflictAction is None:
                        self.conflictFound.emit(thisPath, destPath)
                        while (conflictAction := self.get_conflict_action()) is None:
                            time.sleep(0.1)

                    if conflictAction == FileConflictAction.REPLACE:
                        for i, handleInfo in enumerate(destParentInfo.children):
                            if handleInfo.path.name == destHandle.get_name():
                                self.removeRow(i, destinationParent)
                                break

                    elif conflictAction == FileConflictAction.KEEP:
                        newPath = self._resolve_path_conflict(
                            thisPath.name, destinationParent)
                        if newPath is None:
                            return QModelIndex()
                        destPath = newPath
                        virtualDestPath = destPath.relative_to(destArchivePath)

                    else:  # Skip
                        continue

                # Move from filesystem to archive
                if (isSrcDir := os.path.isdir(thisPath)):
                    sourceHandle = ResourceDirectory.import_from(
                        Path(thisPath))
                else:
                    sourceHandle = ResourceFile.import_from(Path(thisPath))

                if sourceHandle is None:
                    successful = False
                    continue

                destParentHandle = destArchive.get_handle(
                    virtualDestPath.parent)
                if destParentHandle is None:
                    successful = False
                    continue

                if not destParentHandle.add_handle(sourceHandle, action=FileConflictAction.REPLACE):
                    successful = False
                    continue

                # Remove old path
                if isSrcDir:
                    shutil.rmtree(thisPath)
                else:
                    os.remove(thisPath)

                continue

            # Filesystem to filesystem
            if os.path.exists(destPath):
                if conflictAction is None:
                    self.conflictFound.emit(thisPath, destPath)
                    while (conflictAction := self.get_conflict_action()) is None:
                        time.sleep(0.1)

                if conflictAction == FileConflictAction.REPLACE:
                    for i, handleInfo in enumerate(destParentInfo.children):
                        if handleInfo.path.name == destPath.name:
                            self.removeRow(i, destinationParent)
                            break

                elif conflictAction == FileConflictAction.KEEP:
                    newPath = self._resolve_path_conflict(
                        thisPath.name, destinationParent)
                    if newPath is None:
                        return QModelIndex()
                    destPath = newPath

                else:  # Skip
                    continue

            shutil.move(thisPath, destPath)

        self.endMoveRows()

        self._conflictAction = None
        return successful

    def moveColumns(self, sourceParent: QModelIndex | QPersistentModelIndex, sourceColumn: int, count: int, destinationParent: QModelIndex | QPersistentModelIndex, destinationChild: int) -> bool:
        return False

    @Slot()
    def update(self) -> bool:
        if self.rootPath is None:
            self._fileSystemCache = JSystemFSModel._HandleInfo(
                path=Path(),
                parent=None,
                children=[],
                isFile=False,
                size=-1
            )
            return False

        self._fileSystemCache = JSystemFSModel._HandleInfo(
            path=self.rootPath,
            parent=None,
            children=[],
            isFile=False,
            size=0
        )

        rootIndex = self.index(0, 0)
        self._cache_path(rootIndex)
        return True

    @Slot(str)
    def file_changed(self, path: str):
        if path not in self._fileSystemWatcher.files():
            self._fileSystemWatcher.addPath(path)

        self.update()

    @Slot(str)
    def directory_changed(self, path: str):
        if path not in self._fileSystemWatcher.directories():
            self._fileSystemWatcher.addPath(path)

        self.update()

    def _cache_path(self, index: QModelIndex | QPersistentModelIndex):
        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        if handleInfo is None or handleInfo.loaded:
            return

        handleInfo.children.clear()

        path = handleInfo.path
        if os.path.isdir(path):
            i = 0
            for p in os.listdir(path):
                subPath = path / p
                if os.path.isdir(subPath):
                    info = JSystemFSModel._HandleInfo(
                        path=subPath,
                        parent=handleInfo,
                        children=[],
                        isFile=False,
                        size=sum(
                            1 for _ in Path(subPath).glob('*')
                        )
                    )
                else:
                    info = JSystemFSModel._HandleInfo(
                        path=subPath,
                        parent=handleInfo,
                        children=[],
                        isFile=True,
                        size=os.stat(subPath).st_size
                    )
                handleInfo.children.append(info)
                i += 1
            handleInfo.size = i
            handleInfo.loaded = True
            return

        if path.suffix == ".arc":
            self._cache_archive(index)

    def _cache_archive(self, index: QModelIndex | QPersistentModelIndex):

        def _recursive_cache(handle: A_ResourceHandle, subHandleInfo: "JSystemFSModel._HandleInfo"):
            nonlocal index

            i = 0
            for p in handle.get_handles():
                if p.is_file():
                    subHandleInfo.children.append(
                        JSystemFSModel._HandleInfo(
                            path=self.get_path(index) / p.get_path(),
                            parent=subHandleInfo,
                            children=[],
                            isFile=True,
                            size=p.get_size()
                        )
                    )
                    continue
                childHandleInfo = JSystemFSModel._HandleInfo(
                    path=self.get_path(index) / p.get_path(),
                    parent=subHandleInfo,
                    children=[],
                    isFile=False,
                    size=p.get_size()
                )
                _recursive_cache(p, childHandleInfo)
                subHandleInfo.children.append(childHandleInfo)
                i += 1
            subHandleInfo.size = i
            subHandleInfo.loaded = True

        handleInfo: JSystemFSModel._HandleInfo = index.internalPointer()
        if handleInfo.loaded:
            return

        handleInfo.children.clear()

        path = handleInfo.path
        if self.is_child_of_archive(index):
            parentArchiveIndex = self.get_parent_archive(index)
            parentArchivePath = self.get_path(parentArchiveIndex)
            parentArchive = self._archives[parentArchivePath]

            if not path.is_relative_to(parentArchivePath):
                return False

            virtualPath = path.relative_to(parentArchivePath)
            handle = parentArchive.get_handle(virtualPath)
            if handle is None:
                return

            archive = ResourceArchive.from_bytes(
                BytesIO(handle.get_data())
            )
        else:
            with open(path, "rb") as f:
                archive = ResourceArchive.from_bytes(f)

        if archive:
            self._archives[path] = archive
            _recursive_cache(archive, handleInfo)

        handleInfo.loaded = True

    def _initialize_icons(self):
        for extension in self.ExtensionToTypeMap:
            icon = get_icon(extension.lstrip(".") + ".png")
            if icon is None:
                continue
            self._icons[extension] = icon
        self._icons["file"] = get_icon("generic_file.png")
        self._icons["folder"] = get_icon("generic_folder.png")

    def _resolve_path_conflict(self, name: str, parent: QModelIndex | QPersistentModelIndex) -> PurePath | None:
        if not parent.isValid():
            return None

        handleInfo: JSystemFSModel._HandleInfo = parent.internalPointer()
        if len(handleInfo.children) == 0:
            return handleInfo.path / name

        parts = name.rsplit(".", 1)
        name = parts[0]

        renameContext = 1
        ogName = name

        possibleNames = []
        for subHandleInfo in handleInfo.children:
            subName = subHandleInfo.path.name
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            if subName.startswith(ogName):
                possibleNames.append(subName.rsplit(".", 1)[0])

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        if len(parts) == 2:
            name += f".{parts[1]}"
        return handleInfo.path / name

    def _import_fs_path(
        self,
        inputStream: QDataStream,
        destinationParent: QModelIndex | QPersistentModelIndex,
        action: FileConflictAction | None = None
    ):
        thisPath = Path(inputStream.readString())

        destFolder = self.get_path(destinationParent)
        destParentInfo: JSystemFSModel._HandleInfo = destinationParent.internalPointer()  # type: ignore
        destPath = destFolder / thisPath.name

        if thisPath.is_dir():
            subDir = self.mkdir(destinationParent, thisPath.name)
            childCount = inputStream.readUInt32()

            successful = True
            for _ in range(childCount):
                successful &= self._import_fs_path(inputStream, subDir, action)
            return successful

        # Check if the destination is part of an archive
        destArchive: Optional[ResourceArchive] = None
        destArchiveIndex = self.get_parent_archive(destinationParent)

        # Source exists in filesystem
        if destArchiveIndex.isValid():  # Destination exists in an archive
            destArchivePath = self.get_path(destArchiveIndex)
            destArchive = self._archives[destArchivePath]
            virtualDestPath = destFolder.relative_to(destArchivePath)
            destHandle = destArchive.get_handle(virtualDestPath)
            if destHandle:  # Destination move exists
                if action is None:
                    self.conflictFound.emit(thisPath, destFolder)
                    while (action := self.get_conflict_action()) is None:
                        time.sleep(0.1)

                if action == FileConflictAction.REPLACE:
                    for i, handleInfo in enumerate(destParentInfo.children):
                        if handleInfo.path.name == destHandle.get_name():
                            self.removeRow(i, destinationParent)
                            break

                elif action == FileConflictAction.KEEP:
                    newPath = self._resolve_path_conflict(
                        thisPath.name, destinationParent)
                    if newPath is None:
                        return QModelIndex()
                    destPath = newPath
                    virtualDestPath = destPath.relative_to(destArchivePath)

                else:  # Skip
                    return True

            # Move from filesystem to archive
            if (isSrcDir := os.path.isdir(thisPath)):
                sourceHandle = ResourceDirectory.import_from(
                    Path(thisPath))
            else:
                sourceHandle = ResourceFile.import_from(Path(thisPath))

            if sourceHandle is None:
                return False

            destParentHandle = destArchive.get_handle(
                virtualDestPath.parent)
            if destParentHandle is None:
                destParentHandle = destArchive

            if not destParentHandle.add_handle(sourceHandle, action=FileConflictAction.REPLACE):
                return False

            # Remove old path
            if isSrcDir:
                shutil.rmtree(thisPath)
            else:
                os.remove(thisPath)

            return True

        # Filesystem to filesystem
        if os.path.exists(destPath):
            if action is None:
                self.conflictFound.emit(thisPath, destPath)
                while (action := self.get_conflict_action()) is None:
                    time.sleep(0.1)

            if action == FileConflictAction.REPLACE:
                for i, handleInfo in enumerate(destParentInfo.children):
                    if handleInfo.path.name == destPath.name:
                        self.removeRow(i, destinationParent)
                        break

            elif action == FileConflictAction.KEEP:
                newPath = self._resolve_path_conflict(
                    thisPath.name, destinationParent)
                if newPath is None:
                    return QModelIndex()
                destPath = newPath

            else:  # Skip
                return True

        shutil.move(thisPath, destPath)
        return True

    def _import_virtual_path(
        self,
        inputStream: QDataStream,
        destinationParent: QModelIndex | QPersistentModelIndex,
        action: FileConflictAction | None = None
    ) -> bool:
        """
        This function handles importing filesystem nodes from
        an archive or archive subdirectory to the real filesystem
        """
        thisPath = Path(inputStream.readString())
        thisName = thisPath.name

        destParentInfo: JSystemFSModel._HandleInfo = destinationParent.internalPointer()  # type: ignore
        destFolder = self.get_path(destinationParent)
        destPath = destFolder / thisName

        handleType = JSystemFSModel._HandleType(inputStream.readInt8())

        destArchiveIndex = self.get_parent_archive(destinationParent)
        if not destArchiveIndex.isValid():  # To filesystem
            # If a file, we simply copy the data to a file of the same name in this dir
            if handleType == JSystemFSModel._HandleType.FILE:
                fileData = QByteArray()
                inputStream >> fileData

                with open(destPath, "wb") as f:
                    f.write(fileData.data())

                return True

            # If a dir, we create a sub dir of this name and iterate over the next items within this dir
            elif handleType == JSystemFSModel._HandleType.DIRECTORY:
                childrenCount = inputStream.readUInt32()

                folderIndex = self.mkdir(destinationParent, thisPath.name)

                successful = True
                for _ in range(childrenCount):
                    successful &= self._import_virtual_path(
                        inputStream, folderIndex, action)

                return successful

            # If an archive, we can create the archive in the cache and import future items into it
            # TODO: For now we simply copy an unextracted form of the archive
            elif handleType == JSystemFSModel._HandleType.ARCHIVE:
                fileData = QByteArray()
                inputStream >> fileData

                with open(destPath, "wb") as f:
                    f.write(fileData.data())

                # self._archives[destPath] = ResourceArchive.from_bytes(fileData.data())
                return True

            raise ValueError(
                f"Encountered invalid type ID ({handleType}) while deserializing archive info")

        destArchivePath = self.get_path(destArchiveIndex)
        destArchive = self._archives[destArchivePath]

        virtualPath = destPath.relative_to(destArchivePath)
        destHandle = destArchive.get_handle(virtualPath)
        if destHandle:
            if action is None:
                self.conflictFound.emit(thisPath, destFolder)
                while (action := self.get_conflict_action()) is None:
                    time.sleep(0.1)

            if action == FileConflictAction.REPLACE:
                for i, handleInfo in enumerate(destParentInfo.children):
                    if handleInfo.path.name == destHandle.get_name():
                        self.removeRow(i, destinationParent)
                        break

            elif action == FileConflictAction.KEEP:
                newPath = self._resolve_path_conflict(
                    thisPath.name, destinationParent)
                if newPath is None:
                    return QModelIndex()
                destPath = newPath
                virtualDestPath = destPath.relative_to(destArchivePath)

            else:  # Skip
                return True

        destParentHandle = destArchive.get_handle(
            virtualDestPath.parent)
        if destParentHandle is None:
            destParentHandle = destArchive

        # If a file, we simply copy the data to a file of the same name in this dir
        if handleType == JSystemFSModel._HandleType.FILE:
            fileData = QByteArray()
            inputStream >> fileData

            newHandle = ResourceFile(
                thisName,
                initialData=fileData.data()
            )
            destParentHandle.add_handle(
                newHandle, action=FileConflictAction.REPLACE)

            return True

        # If a dir, we create a sub dir of this name and iterate over the next items within this dir
        elif handleType == JSystemFSModel._HandleType.DIRECTORY:
            childrenCount = inputStream.readUInt32()

            folderIndex = self.mkdir(destinationParent, thisPath.name)

            successful = True
            for _ in range(childrenCount):
                successful &= self._import_virtual_path(
                    inputStream, folderIndex, action)

            return successful

        # If an archive, we can create the archive in the cache and import future items into it
        # TODO: For now we simply copy an unextracted form of the archive
        elif handleType == JSystemFSModel._HandleType.ARCHIVE:
            fileData = QByteArray()
            inputStream >> fileData

            newHandle = ResourceFile(
                thisName,
                initialData=fileData.data()
            )
            destParentHandle.add_handle(
                newHandle, action=FileConflictAction.REPLACE)

            # self._archives[destPath] = ResourceArchive.from_bytes(fileData.data())
            return True

        raise ValueError(
            f"Encountered invalid type ID ({handleType}) while deserializing archive info")

    def _export_fs_path(
        self,
        outputStream: QDataStream,
        srcIndex: QModelIndex | QPersistentModelIndex
    ) -> bool:
        srcPath = Path(self.get_path(srcIndex))
        srcParentInfo: JSystemFSModel._HandleInfo = srcIndex.internalPointer()  # type: ignore

        outputStream.writeString(str(srcPath))

        if not srcPath.is_dir():
            return True

        if srcParentInfo.size > 0:  # Number of children already cached
            outputStream.writeUInt32(srcParentInfo.size)

            successful = True
            for p in srcPath.iterdir():
                successful &= self._export_fs_path(
                    outputStream, self.get_path_index(p))
            return successful
        else:
            paths = [p for p in srcPath.iterdir()]
            outputStream.writeUInt32(len(paths))

            successful = True
            for p in paths:
                successful &= self._export_fs_path(
                    outputStream, self.get_path_index(p))
            return successful

    def _export_virtual_path(
        self,
        outputStream: QDataStream,
        srcIndex: QModelIndex | QPersistentModelIndex,
        srcArchiveIndex: QModelIndex | QPersistentModelIndex
    ) -> bool:
        """
        This function handles exporting filesystem nodes from
        an archive or archive subdirectory to the real filesystem
        """
        srcPath = self.get_path(srcIndex)
        srcParentInfo: JSystemFSModel._HandleInfo = srcIndex.internalPointer()  # type: ignore

        if not srcArchiveIndex.isValid():  # To filesystem
            return False

        srcArchivePath = self.get_path(srcArchiveIndex)
        srcArchive = self._archives[srcArchivePath]

        virtualPath = srcPath.relative_to(srcArchivePath)
        srcHandle = srcArchive.get_handle(virtualPath)
        if srcHandle is None:
            return False

        outputStream.writeString(str(srcPath))

        if srcHandle.is_file():
            outputStream.writeInt8(JSystemFSModel._HandleType.FILE)
            outputStream << srcHandle.get_raw_data()
            return True

        if srcHandle.is_directory():
            outputStream.writeInt8(JSystemFSModel._HandleType.DIRECTORY)
            if srcParentInfo.size > 0:  # Size is cached already
                outputStream.writeUInt32(srcParentInfo.size)

                successful = True
                for p in srcHandle.get_handles():
                    successful &= self._export_virtual_path(
                        outputStream, self.get_path_index(
                            srcPath / p.get_name()), srcArchiveIndex
                    )
                return successful
            else:
                paths = [p for p in srcHandle.get_handles()]
                outputStream.writeUInt32(len(paths))

                successful = True
                for p in paths:
                    successful &= self._export_virtual_path(
                        outputStream, self.get_path_index(
                            srcPath / p.get_name()), srcArchiveIndex
                    )
                return successful

        if srcHandle.is_archive():
            outputStream.writeInt8(JSystemFSModel._HandleType.ARCHIVE)
            outputStream << srcHandle.get_raw_data()
            return True

        raise NotImplementedError(
            "Handle encountered is not a supported handle type")


class JSystemFSSortProxyModel(QSortFilterProxyModel):
    def lessThan(self, source_left: QModelIndex | QPersistentModelIndex, source_right: QModelIndex | QPersistentModelIndex) -> bool:
        sourceModel: JSystemFSModel = self.sourceModel()
        if sourceModel.is_populated(source_left):
            if sourceModel.is_file(source_right):
                return True

        if sourceModel.is_populated(source_right):
            if sourceModel.is_file(source_left):
                return False

        return super().lessThan(source_left, source_right)


class JSystemFSDirectoryProxyModel(JSystemFSSortProxyModel):
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.SizeHintRole:
            return QSize(40, 20)

        return super().data(index, role)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:
        sourceModel: JSystemFSModel = self.sourceModel()
        sourceIndex = sourceModel.index(source_row, 0, source_parent)
        return sourceModel.is_dir(sourceIndex) or sourceModel.is_archive(sourceIndex)

    def hasChildren(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return True

        sourceModel: JSystemFSModel = self.sourceModel()
        sourceParent = self.mapToSource(parent)
        path = sourceModel.get_path(sourceParent)

        archiveIndex = sourceModel.get_parent_archive(sourceParent)
        if archiveIndex.isValid():
            archivePath = sourceModel.get_path(archiveIndex)
            archive = sourceModel._archives[archivePath]
            if archive is None:
                return False

            if not path.is_relative_to(archivePath):
                return False

            virtualPath = path.relative_to(archivePath)
            handle = archive.get_handle(virtualPath)
            if handle is None:
                return False

            if handle.is_directory():
                for subHandle in handle.get_handles():
                    if subHandle.is_directory() or subHandle.get_extension() == ".arc":
                        return True
                return False

            if handle.is_file() and handle.get_extension() == ".arc":
                return not ResourceArchive.is_archive_empty(
                    BytesIO(handle.get_raw_data())
                )

        if os.path.isdir(path):
            for p in Path(path).glob("*"):
                if p.is_dir() or p.suffix == ".arc":
                    return True
            return False

        if os.path.isfile(path) and path.suffix == ".arc":
            with open(path, "rb") as f:
                dirCount = ResourceArchive.get_directory_count(f)
            return dirCount > 1

        return False
