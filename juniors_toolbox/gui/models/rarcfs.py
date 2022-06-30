from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from logging import root
import os
from pathlib import Path, PurePath
import shutil
from typing import Any, Optional, Union, overload
from juniors_toolbox.gui.images import get_icon

from juniors_toolbox.utils.rarc import (A_ResourceHandle, ResourceArchive, ResourceDirectory,
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


class JSystemFSModel(QAbstractItemModel):
    """
    Mimics QFileSystemModel with a watchdog and async updates, with RARC support
    """
    directoryLoaded = Signal(PurePath)
    fileRenamed = Signal(PurePath, str, str)
    rootPathChanged = Signal(PurePath)

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
        self._fileSystemWatcher.directoryChanged.connect(self.directory_changed)
        self._archives: dict[PurePath, ResourceArchive | None] = {}

        if rootPath is not None:
            self._fileSystemWatcher.addPath(str(rootPath))

        self._icons: dict[str, QIcon] = {}

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
            if archive is None:
                return False

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
        indexInfo: JSystemFSModel._HandleInfo = index.internalPointer()

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
                if archive is None:
                    return QModelIndex()

                dirHandle = archive.new_directory(name)
                if dirHandle is None:
                    return QModelIndex()

            elif self.is_child_of_archive(parent):
                archiveIndex = self.get_parent_archive(parent)
                if not archiveIndex.isValid():
                    return QModelIndex()

                archivePath = self.get_path(archiveIndex)
                archive = self._archives[archivePath]
                if archive is None:
                    return QModelIndex()

                parentHandle = archive.get_handle(parentPath)
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

    def rename(self, index: QModelIndex | QPersistentModelIndex, _path: PurePath) -> bool:
        if not index.isValid():
            return False

        if os.path.exists(_path):
            return False

        path = self.get_path(index)
        if os.path.exists(path):

            # Move/rename the file
            if os.path.isdir(_path.parent):
                os.rename(path, _path)
                self.update()
                return True

            # Move/rename the handle into the archive from the fs
            fsIndex = self.get_path_index(_path.parent)
            if not fsIndex.isValid():
                return False

            archiveIndex = self.get_parent_archive(fsIndex)
            if not archiveIndex.isValid():
                return False

            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return False

            handle = archive.get_handle(path)
            if handle is None:
                return False

            if handle.path_exists(_path.name):
                return False

            if os.path.isdir(path):
                pathHandle = ResourceDirectory.import_from(Path(path))
            elif os.path.isfile(path):
                pathHandle = ResourceFile.import_from(Path(path))

            if pathHandle is None:
                return False

            os.remove(path)

            handle.add_handle(pathHandle)
            self.update()
            return True

        archiveIndex = self.get_parent_archive(index)
        if not archiveIndex.isValid():
            return False

        archivePath = self.get_path(archiveIndex)
        archive = self._archives[archivePath]
        if archive is None:
            return False

        handle = archive.get_handle(path)
        if handle is None:
            return False

        if _path.is_relative_to(archivePath):
            # Move/rename the handle internally in the archive
            if handle.rename(_path.relative_to(archivePath)):
                self.update()
                return True
            return False

        if not os.path.isdir(_path.parent):
            # Move/rename the handle into the archive from the source archive
            fsIndex = self.get_path_index(_path.parent)
            if not fsIndex.isValid():
                return False

            archiveIndex = self.get_parent_archive(fsIndex)
            if not archiveIndex.isValid():
                return False

            archivePath = self.get_path(archiveIndex)
            archive = self._archives[archivePath]
            if archive is None:
                return False

            pathHandle = archive.get_handle(path)
            if pathHandle is None:
                return False

            if pathHandle.path_exists(_path.name):
                return False

            pathHandle.add_handle(handle)
            self.update()
            return True

        # Move/rename the handle into the fs
        handle.set_name(_path.name)
        handle.export_to(Path(_path.parent))
        archive.remove_handle(handle)

        self.update()
        return True

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
        if archive is None:
            return False

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

    def parent(self, child: QModelIndex | QPersistentModelIndex | None = None) -> QModelIndex: # type: ignore
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

    def mimeData(self, indexes: list[QtCore.QModelIndex | QtCore.QPersistentModelIndex]) -> QMimeData:
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
            if parentArchive is None:
                return
            

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