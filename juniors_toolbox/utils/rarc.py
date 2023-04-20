from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from io import BytesIO
from itertools import chain
from pathlib import Path, PurePath
from struct import pack, unpack
from typing import BinaryIO, Iterator, Optional

from enum import IntFlag
from juniors_toolbox.utils import (
    A_Serializable,
    ReadableBuffer,
    VariadicArgs,
    VariadicKwargs,
    jdrama,
)
from juniors_toolbox.utils.iohelper import (
    align_int,
    read_bool,
    read_sint16,
    read_sint32,
    read_string,
    read_ubyte,
    read_uint16,
    read_uint32,
    write_bool,
    write_sint16,
    write_sint32,
    write_string,
    write_uint16,
    write_uint32,
)


def write_pad32(f: BinaryIO):
    next_aligned_pos = (f.tell() + 0x1F) & ~0x1F
    f.write(b"\x00" * (next_aligned_pos - f.tell()))


class FileConflictAction(IntEnum):
    REPLACE = 0
    KEEP = 1
    SKIP = 2


class ResourceAttribute(IntFlag):
    FILE = 0x01
    DIRECTORY = 0x02
    COMPRESSED = 0x04
    PRELOAD_TO_MRAM = 0x10
    PRELOAD_TO_ARAM = 0x20
    LOAD_FROM_DVD = 0x40
    YAZ0_COMPRESSED = 0x80  # Uses YAZ0 compression


@dataclass
class InternalDirectoryEntry:
    magic: str
    nameOffset: int
    nameHash: int
    fileCount: int
    firstFileOffset: int

    name: str
    nodeInfo: InternalNodeEntry | None = None
    subNodes: list[InternalNodeEntry] = field(default_factory=list)

    @classmethod
    def load(cls, archive: BinaryIO, strings_offset: int) -> "InternalDirectoryEntry":
        _oldPos = archive.tell()
        magic = read_string(archive, maxlen=4)

        # Repair magic if it's too long or too short
        if len(magic) != 4:
            if len(magic) < 4:
                magic += " " * (4 - len(magic))
            else:
                magic = magic[:4]
        archive.seek(_oldPos + 4, 0)

        magic = magic
        nameOffset = read_uint32(archive)
        nameHash = read_uint16(archive)
        fileCount = read_uint16(archive)
        firstFileOffset = read_uint32(archive)

        _oldPos = archive.tell()
        archive.seek(strings_offset + nameOffset, 0)
        name = read_string(archive)
        archive.seek(_oldPos, 0)

        self = cls(magic, nameOffset, nameHash, fileCount, firstFileOffset, name)
        return self

    def save(self, archive: BinaryIO, strings_offset: int) -> None:
        archive.write(self.magic.encode("ascii"))
        write_uint32(archive, self.nameOffset)
        write_uint16(archive, self.nameHash)
        write_uint16(archive, self.fileCount)
        write_uint32(archive, self.firstFileOffset)

        _oldPos = archive.tell()
        archive.seek(strings_offset + self.nameOffset, 0)
        write_string(archive, self.name)
        archive.seek(_oldPos, 0)


@dataclass
class InternalNodeEntry:
    fileID: int
    nameHash: int
    flags: ResourceAttribute
    nameOffset: int
    # If file, this is the offset to the file data. If directory, this is the offset to the first file entry in the directory.
    modularA: int
    # If file, this is the size of the file data. If directory, this is the size of the directory node.
    modularB: int

    # These are not part of the file entry, but are used for caching.
    name: str
    data: BytesIO | None
    parent: InternalDirectoryEntry | None = None
    dirInfo: InternalDirectoryEntry | None = None

    @classmethod
    def load(
        cls, archive: BinaryIO, datas_offset: int, strings_offset: int
    ) -> "InternalNodeEntry":
        fileID = read_uint16(archive)
        nameHash = read_uint16(archive)
        flagsAndOffset = read_uint32(archive)
        flags = (flagsAndOffset & 0xFF000000) >> 24
        nameOffset = flagsAndOffset & 0x00FFFFFF
        modularA = read_uint32(archive)
        modularB = read_uint32(archive)
        archive.seek(4, 1)

        _oldPos = archive.tell()

        archive.seek(strings_offset + nameOffset, 0)
        name = read_string(archive)

        self = cls(fileID, nameHash, flags, nameOffset, modularA, modularB, name, None)

        if self.is_file():
            archive.seek(datas_offset + self.modularA, 0)
            self.data = BytesIO(archive.read(self.modularB))

        archive.seek(_oldPos, 0)

        return self

    def save(
        self,
        archive: BinaryIO,
        datas_offset: int,
        strings_offset: int,
        syncID: int | None = None,
    ) -> None:
        if self.is_directory():
            write_uint16(archive, 0xFFFF)
        elif syncID is not None:
            write_uint16(archive, syncID)
        else:
            write_uint16(archive, self.fileID)
        write_uint16(archive, self.nameHash)
        write_uint32(archive, (self.flags << 24) | self.nameOffset)
        write_uint32(archive, self.modularA)
        write_uint32(archive, self.modularB)

        _oldPos = archive.tell()

        archive.seek(strings_offset + self.nameOffset, 0)
        write_string(archive, self.name)

        if self.is_file():
            archive.seek(datas_offset + self.modularA, 0)
            archive.write(self.data.getvalue())

        archive.seek(_oldPos, 0)

    def is_file(self) -> bool:
        return (self.flags & ResourceAttribute.FILE) != 0

    def is_directory(self) -> bool:
        return (self.flags & ResourceAttribute.DIRECTORY) != 0

    def is_preloaded_to_mram(self) -> bool:
        return (self.flags & ResourceAttribute.PRELOAD_TO_MRAM) != 0

    def is_preloaded_to_aram(self) -> bool:
        return (self.flags & ResourceAttribute.PRELOAD_TO_ARAM) != 0

    def is_loaded_from_dvd(self) -> bool:
        return (self.flags & ResourceAttribute.LOAD_FROM_DVD) != 0

    def is_compressed(self) -> bool:
        return (self.flags & ResourceAttribute.COMPRESSION) != 0

    def is_yaz0_compressed(self) -> bool:
        return (self.flags & ResourceAttribute.YAZ0_COMPRESSION) != 0

    def get_data(self) -> BytesIO | None:
        if self.is_file():
            return BytesIO(self.data)
        return None


class ResourceHandle:
    @dataclass
    class _LoadSortedHandles:
        mram: list["ResourceHandle"]
        aram: list["ResourceHandle"]
        dvd: list["ResourceHandle"]

    def __init__(self, entry: InternalNodeEntry):
        self._nodeEntry = entry

    def is_flagged(self, attribute: ResourceAttribute | int) -> bool:
        return (self._nodeEntry.flags & attribute) != 0

    def get_flags(self) -> ResourceAttribute:
        return self._nodeEntry.flags

    def set_flag(self, attribute: ResourceAttribute, active: bool) -> None:
        if active:
            self._nodeEntry.flags |= attribute
        else:
            self._nodeEntry.flags &= attribute

    def get_name(self) -> str:
        return self._nodeEntry.name

    def set_name(self, name: str):
        self._nodeEntry.name = name
        self._nodeEntry.nameHash = jdrama.get_key_code(name)

    def get_extension(self) -> str:
        return "." + self._nodeEntry.name.split(".")[-1]

    def set_extension(self, extension: str):
        parts = self._nodeEntry.name.split(".")
        parts[-1] = extension.lstrip(".")
        self.set_name(".".join(parts))

    def get_stem(self) -> str:
        if "." not in self._nodeEntry.name:
            return self._nodeEntry.name
        return ".".join(self._nodeEntry.name.split(".")[:-1])

    def set_stem(self, stem: str):
        if "." not in self._nodeEntry.name:
            self.set_name(stem)
            return

        index = -1
        extIndex = 0
        while (index := self._nodeEntry.name.find(".", index + 1)) != -1:
            extIndex = index

        self.set_name(stem + self._nodeEntry.name[extIndex:])

    def get_path(self) -> PurePath:
        path = PurePath(self.get_name())
        parent = self.get_parent()
        if parent is None:
            return path
        while True:
            path = parent.get_name() / path
            if parent.get_parent() is None:
                path = parent._nodeEntry.parent.name / path
                break
            parent = parent.get_parent()
        return path

    def get_parent(self) -> ResourceHandle | None:
        if not self._nodeEntry.parent:
            return None
        nodeInfo = self._nodeEntry.parent.nodeInfo
        if nodeInfo is None:
            return None
        if nodeInfo.is_file():
            raise TypeError("Parent is a file, not a directory")
        return ResourceHandle(nodeInfo)

    def set_parent(self, handle: ResourceHandle | None):
        parent = self.get_parent()
        if handle == parent:
            return

        if parent is not None:
            parent.remove_handle(self)

        if handle is not None:
            handle.add_handle(self)

    def is_directory(self) -> bool:
        return self._nodeEntry.is_directory()

    def is_file(self) -> bool:
        return self._nodeEntry.is_file()

    def get_magic(self) -> str:
        return self._nodeEntry.magic

    def get_id(self) -> int:
        return self._nodeEntry.fileID

    def set_id(self, __id: int, /) -> None:
        self._nodeEntry.fileID = __id

    def get_size(self) -> int:
        if self.is_file():
            return self._nodeEntry.modularB
        return len(self._nodeEntry.dirInfo.subNodes)

    def get_data(self) -> bytes:
        if self.is_file():
            return self._nodeEntry.data.getvalue()
        raise TypeError("Cannot get data from a directory")

    def get_handles(self, *, flatten: bool = False) -> Iterator[ResourceHandle]:
        if self.is_file():
            raise TypeError("Cannot get handles from a file")
        # iterate over the nodes in the directory
        for node in self._nodeEntry.dirInfo.subNodes:
            if node.name in [".", ".."]:
                continue
            handle = ResourceHandle(node)
            yield handle
            # if flatten is true, yield all subnodes recursively
            if flatten and handle.is_directory():
                yield from handle.get_handles(flatten=flatten)

    def get_handle(self, __path: PurePath | str, /) -> ResourceHandle | None:
        if self.is_file():
            raise TypeError("Cannot get handles from a file")
        if isinstance(__path, str):
            __path = PurePath(__path)
        # if the path is empty, return self
        if len(__path.parts) == 0:
            return self
        # if the path is a single part, return the child with that name
        if len(__path.parts) == 1:
            for node in self._nodeEntry.dirInfo.subNodes:
                if node.name == __path.parts[0]:
                    return ResourceHandle(node)
            return None
        # if the path is longer, recurse into the first part
        for node in self._nodeEntry.dirInfo.subNodes:
            if node.name == __path.parts[0]:
                return ResourceHandle(node).get_handle(__path.parts[1:])
        return None

    def path_exists(self, __path: PurePath | str, /) -> bool:
        return self.get_handle(__path) is not None

    def add_handle(
        self,
        __handle: ResourceHandle,
        /,
        *,
        action: FileConflictAction = FileConflictAction.REPLACE,
    ) -> bool:
        if self.is_file():
            raise TypeError("Cannot add handles to a file")

        if __handle.get_parent() == self:
            return True

        if self.path_exists(__handle.get_name()):
            if action == FileConflictAction.REPLACE:
                # Clean up the handle's original parent
                if __handle.get_parent() is not None:
                    __handle.get_parent().remove_handle(__handle)
                self.remove_handle(__handle.get_name())
            elif action == FileConflictAction.SKIP:
                return False
            else:
                # Clean up the handle's original parent
                if __handle.get_parent() is not None:
                    __handle.get_parent().remove_handle(__handle)
                __handle.set_name(self._fs_resolve_name(__handle.get_name()))
                self._nodeEntry.dirInfo.fileCount += 1
        else:
            # Clean up the handle's original parent
            if __handle.get_parent() is not None:
                __handle.get_parent().remove_handle(__handle)
            self._nodeEntry.dirInfo.fileCount += 1

        self._nodeEntry.dirInfo.subNodes.append(__handle._nodeEntry)
        __handle._nodeEntry.parent = self._nodeEntry.dirInfo

    def remove_handle(self, __handle: ResourceHandle, /) -> bool:
        if self.is_file():
            raise TypeError("Cannot remove handles from a file")
        if self.path_exists(__handle.get_name()):
            self._nodeEntry.dirInfo.subNodes.remove(__handle._nodeEntry)
            self._nodeEntry.dirInfo.fileCount -= 1
            __handle._nodeEntry.parent = None
            return True
        return False

    def remove_path(self, __path: PurePath | str, /) -> bool:
        if self.is_file():
            raise TypeError("Cannot remove handles from a file")
        handle = self.get_handle(__path)
        if handle:
            self._nodeEntry.dirInfo.subNodes.remove(handle._nodeEntry)
            self._nodeEntry.dirInfo.fileCount -= 1
            handle._nodeEntry.parent = None
            return True
        return False

    def new_file(
        self,
        name: str,
        initialData: bytes | bytearray = b"",
        attributes: ResourceAttribute = ResourceAttribute.FILE
        | ResourceAttribute.PRELOAD_TO_MRAM,
        fileID: int = 0,
    ) -> ResourceHandle | None:
        if self.is_file():
            raise TypeError("Cannot add handles to a file")
        if self.path_exists(name):
            return None

        nodeInfo = InternalNodeEntry(
            fileID=fileID,
            nameHash=jdrama.get_key_code(name),
            flags=attributes,
            nameOffset=-1,
            modularA=-1,
            modularB=len(initialData),
            name=name,
            data=BytesIO(initialData),
        )

        handle = ResourceHandle(nodeInfo)
        handle._nodeEntry.flags |= ResourceAttribute.FILE
        handle._nodeEntry.flags &= ~ResourceAttribute.DIRECTORY
        self.add_handle(handle)
        return handle

    def new_directory(
        self,
        name: str,
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY
        | ResourceAttribute.PRELOAD_TO_MRAM,
    ) -> ResourceHandle | None:
        if self.is_file():
            raise TypeError("Cannot add handles to a file")
        if self.path_exists(name):
            return None

        dirInfo = InternalDirectoryEntry(
            magic=name.upper()[:4].encode("ascii"),
            name=name,
            nameOffset=-1,
            nameHash=jdrama.get_key_code(name),
            fileCount=0,
            firstFileOffset=-1,
            nodeInfo=None,
            subNodes=[],
        )

        nodeInfo = InternalNodeEntry(
            fileID=0xFFFF,
            nameHash=jdrama.get_key_code(name),
            flags=attributes,
            nameOffset=-1,
            modularA=-1,
            modularB=0x10,
            name=name,
            data=None,
            dirInfo=dirInfo,
        )

        dirInfo.nodeInfo = nodeInfo

        handle = ResourceHandle(nodeInfo)
        handle._nodeEntry.flags |= ResourceAttribute.DIRECTORY
        handle._nodeEntry.flags &= ~ResourceAttribute.FILE
        self.add_handle(handle)
        return handle

    def export_to(
        self,
        __folderPath: Path | str,
        /,
        *,
        action: FileConflictAction = FileConflictAction.REPLACE,
    ) -> bool:
        if isinstance(__folderPath, str):
            __folderPath = Path(__folderPath)

        targetPath = __folderPath / self.get_name()

        if __folderPath.is_file():
            raise TypeError("Cannot export to a file")

        if not __folderPath.exists():
            __folderPath.mkdir(parents=True)

        if targetPath.exists():
            if action == FileConflictAction.REPLACE:
                if targetPath.is_dir():
                    shutil.rmtree(targetPath)
                else:
                    targetPath.unlink()
            elif action == FileConflictAction.SKIP:
                return False
            else:
                targetPath = targetPath.with_stem(
                    self._fs_resolve_name(self.get_name())
                )

        if self.is_file():
            with open(targetPath, "wb") as f:
                self.seek(0)
                f.write(self.read())
            return True
        else:
            for handle in self.get_handles():
                handle.export_to(targetPath, action=action)
            return True

    @classmethod
    def import_from(self, path: Path | str) -> ResourceHandle | None:
        if isinstance(path, str):
            path = Path(path)

        if path.is_file():
            with open(path, "rb") as f:
                initialData = f.read()

            nodeInfo = InternalNodeEntry(
                fileID=0,
                nameHash=jdrama.get_key_code(path.stem),
                flags=ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM,
                nameOffset=-1,
                modularA=-1,
                modularB=len(initialData),
                name=path.stem,
                data=BytesIO(initialData),
            )

            return ResourceHandle(nodeInfo)
        else:
            dirInfo = InternalDirectoryEntry(
                magic=path.stem.upper()[:4].encode("ascii"),
                name=path.stem,
                nameOffset=-1,
                nameHash=jdrama.get_key_code(path.stem),
                fileCount=0,
                firstFileOffset=-1,
                nodeInfo=None,
                subNodes=[],
            )

            nodeInfo = InternalNodeEntry(
                fileID=0xFFFF,
                nameHash=jdrama.get_key_code(path.stem),
                flags=ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM,
                nameOffset=-1,
                modularA=-1,
                modularB=0x10,
                name=path.stem,
                data=None,
                dirInfo=dirInfo,
            )

            dirInfo.nodeInfo = nodeInfo

            handle = ResourceHandle(nodeInfo)

            for subPath in path.iterdir():
                subHandle = ResourceHandle.import_from(subPath)
                if subHandle:
                    handle.add_handle(subHandle)

            return handle

    def rename(
        self,
        __path: PurePath | str,
        /,
        *,
        action: FileConflictAction = FileConflictAction.REPLACE,
    ) -> bool:
        """
        Renames the file to the given path.

        1. If the file already exists, it will be replaced if the action is REPLACE.
        2. If the file already exists, it will be skipped if the action is SKIP.
        3. If the file already exists, it will be renamed if the action is KEEP.
        """
        if isinstance(__path, str):
            __path = PurePath(__path)

        pathName = __path.name

        if __path.parent == self.get_path().parent:
            parent = self.get_parent()
            if parent is None:
                return False

            conflictingHandle = parent.get_handle(pathName)
            if conflictingHandle is None:
                self.set_name(pathName)
                return True

            if action == FileConflictAction.REPLACE:
                parent.remove_handle(conflictingHandle)
                self.set_name(pathName)
                return True

            if action == FileConflictAction.KEEP:
                newName = parent._fs_resolve_name(pathName)
                self.set_name(newName)
                return True

            return False

        archive = self.get_archive()
        if archive is None:
            return False

        newParent = archive.get_handle(__path.parent)
        if newParent is None:
            return False

        self.set_parent(newParent)

        conflictingHandle = newParent.get_handle(pathName)
        if conflictingHandle is None:
            self.set_name(pathName)
            return True

        if action == FileConflictAction.REPLACE:
            newParent.remove_handle(conflictingHandle)
            self.set_name(pathName)
            return True

        if action == FileConflictAction.KEEP:
            newName = newParent._fs_resolve_name(pathName)
            self.set_name(newName)
            return True

        return False

    def read(self, __size: int, /) -> bytes:
        """
        Reads a number of bytes from the file.
        """
        if self.is_directory():
            raise TypeError("Cannot read from a directory")

        if self._nodeEntry.data is None:
            raise ValueError("File data is not loaded")

        return self._nodeEntry.data.read(__size)

    def write(self, __buffer: ReadableBuffer, /) -> int:
        """
        Writes a number of bytes to the file.
        """
        if self.is_directory():
            raise TypeError("Cannot write to a directory")

        if self._nodeEntry.data is None:
            raise ValueError("File data is not loaded")

        return self._nodeEntry.data.write(__buffer)

    def seek(self, __offset: int, __whence: int = os.SEEK_CUR) -> int:
        """
        Seeks to a position in the file.
        """
        if self.is_directory():
            raise TypeError("Cannot seek in a directory")

        if self._nodeEntry.data is None:
            raise ValueError("File data is not loaded")

        return self._nodeEntry.data.seek(__offset, __whence)

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, ResourceHandle):
            return self._nodeEntry == __o._nodeEntry
        return False

    def __ne__(self, __o: object) -> bool:
        return not self == __o

    def __hash__(self) -> int:
        return hash(self._nodeEntry)

    def _get_files_by_load_type(self) -> _LoadSortedHandles:
        mramHandles = []
        aramHandles = []
        dvdHandles = []
        for handle in self.get_handles():
            if handle.is_directory():
                info = handle._get_files_by_load_type()
                mramHandles.extend(info.mram)
                aramHandles.extend(info.aram)
                dvdHandles.extend(info.dvd)
            else:
                if handle.is_flagged(ResourceAttribute.PRELOAD_TO_MRAM):
                    mramHandles.append(handle)
                elif handle.is_flagged(ResourceAttribute.PRELOAD_TO_ARAM):
                    mramHandles.append(handle)
                elif handle.is_flagged(ResourceAttribute.LOAD_FROM_DVD):
                    mramHandles.append(handle)
                else:
                    raise ValueError(
                        f"Resource handle {handle.get_name()} isn't set to load"
                    )

        return ResourceHandle._LoadSortedHandles(mramHandles, aramHandles, dvdHandles)

    def _fs_resolve_name(self, name: str) -> str:
        maxIterations = 1000
        parts = name.rsplit(".", 1)
        name = parts[0]

        renameContext = 1
        ogName = name

        possibleNames = []
        for handle in self.get_handles():
            handleName = handle.get_name()
            if renameContext > maxIterations:
                raise FileExistsError(
                    f"Name exists beyond {maxIterations} unique iterations!"
                )
            if handleName.startswith(ogName):
                possibleNames.append(handleName.rsplit(".", 1)[0])

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > maxIterations:
                raise FileExistsError(
                    f"Name exists beyond {maxIterations} unique iterations!"
                )
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        if len(parts) == 2:
            name += f".{parts[1]}"
        return name


class ResourceArchive(A_Serializable):
    @dataclass
    class NodeMetaData:
        directoryCount: int
        directoryTableOffset: int
        fileEntryCount: int
        fileEntryTableOffset: int
        stringTableSize: int
        stringTableOffset: int
        nextFreeFileID: int
        syncIDs: bool

        # These are just for caching purposes
        directoryTable: list[InternalDirectoryEntry]
        nodeEntryTable: list[InternalNodeEntry]

    @dataclass
    class RARCMetaData:
        nodeMetaData: ResourceArchive.NodeMetaData
        mramSize: int
        aramSize: int
        dvdSize: int

        def get_size(self) -> int:
            return self.mramSize + self.aramSize + self.dvdSize

        def get_data_offset(self) -> int:
            ofs = align_int(
                align_int(
                    self.nodeMetaData.directoryCount * 0x10
                    + self.nodeMetaData.fileEntryCount * 0x14,
                    0x20,
                )
                + self.nodeMetaData.stringTableSize,
                0x20,
            )
            return ofs

        def get_string_table_offset(self) -> int:
            return align_int(
                self.nodeMetaData.directoryCount * 0x10
                + self.nodeMetaData.fileEntryCount * 0x14,
                0x20,
            )

    @dataclass
    class StringTableData:
        strings: bytes

        # These are just for caching purposes
        offsets: dict[str, int]

    def __init__(self, rootInfo: InternalDirectoryEntry, syncIDs: bool = True):
        self.nodeInfo = ResourceArchive.NodeMetaData(
            0, 0x20, 0, 0x30, 5, 0x60, 0, syncIDs, [rootInfo], []
        )
        self.metaInfo = ResourceArchive.RARCMetaData(self.nodeInfo, 0, 0, 0)
        self.rootInfo = rootInfo
        self.regenerate_flat_lists()

    @staticmethod
    def is_data_archive(archive: BinaryIO) -> bool:
        _oldPos = archive.tell()
        isValid = archive.read(4) == b"RARC"
        archive.seek(_oldPos, 0)
        return isValid

    @staticmethod
    def is_archive_empty(archive: BinaryIO) -> bool:
        _oldPos = archive.tell()

        assert archive.read(4) == b"RARC", 'Invalid identifier. Expected "RARC"'
        archive.seek(0x20, 0)

        directoryCount = read_uint32(archive)
        archive.seek(4, 1)
        fileEntryCount = read_uint32(archive)

        archive.seek(_oldPos, 0)

        return directoryCount <= 1 and fileEntryCount <= 2

    @staticmethod
    def get_directory_count(archive: BinaryIO) -> int:
        _oldPos = archive.tell()

        assert archive.read(4) == b"RARC", 'Invalid identifier. Expected "RARC"'
        archive.seek(0x20, 0)

        directoryCount = read_uint32(archive)

        archive.seek(_oldPos, 0)

        return directoryCount

    @classmethod
    def from_bytes(
        cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs
    ) -> "ResourceArchive" | None:
        assert data.read(4) == b"RARC", 'Invalid identifier. Expected "RARC"'

        # Header
        rarcSize = read_uint32(data)
        dataHeaderOffset = read_uint32(data)
        dataOffset = read_uint32(data) + 0x20
        dataLength = read_uint32(data)
        mramSize = read_uint32(data)
        aramSize = read_uint32(data)
        data.seek(4, 1)

        # Data Header
        directoryCount = read_uint32(data)
        directoryTableOffset = read_uint32(data) + 0x20
        fileEntryCount = read_uint32(data)
        fileEntryTableOffset = read_uint32(data) + 0x20
        stringTableSize = read_uint32(data)
        stringTableOffset = read_uint32(data) + 0x20
        nextFreeFileID = read_uint16(data)
        syncIDs = read_bool(data)

        # Directory Nodes
        data.seek(directoryTableOffset, 0)

        flatDirectoryList: list[InternalDirectoryEntry] = []
        for _ in range(directoryCount):
            directory = InternalDirectoryEntry.load(data, stringTableOffset)
            flatDirectoryList.append(directory)

        # File Nodes
        data.seek(fileEntryTableOffset, 0)

        flatNodeList: dict[InternalNodeEntry] = []
        for _ in range(fileEntryCount):
            node = InternalNodeEntry.load(data, dataOffset, stringTableOffset)
            if node.is_directory() and node.modularA < 0xFFFF:
                try:
                    node.dirInfo = flatDirectoryList[node.modularA]
                except IndexError:
                    raise IndexError(
                        f'Invalid directory index "{node.modularA}" for node "{node.name}" of archive "{flatDirectoryList[0].name}"'
                    )
                # Skip this and parent directories
                if node.name not in ["", ".", ".."]:
                    assert (
                        node.dirInfo.nodeInfo is None
                    ), f'Directory "{node.dirInfo.name}" already has a node "{node.dirInfo.nodeInfo.name}"'
                    node.dirInfo.nodeInfo = node
            flatNodeList.append(node)

        for dirEntry in flatDirectoryList:
            for nodeInfo in flatNodeList[
                dirEntry.firstFileOffset : dirEntry.fileCount + dirEntry.firstFileOffset
            ]:
                nodeInfo.parent = dirEntry
                dirEntry.subNodes.append(nodeInfo)

        archive = cls(flatDirectoryList[0], syncIDs)
        archive._flatNodeList = flatNodeList
        archive._flatDirectoryList = flatDirectoryList

        return archive

    def to_bytes(self) -> bytes:
        stream = BytesIO()

        dataTable = self._regenerate_data_info(0)

        stringTableData = self._get_string_table_data(self.nodeInfo.nodeEntryTable)

        # File Writing
        stream.write(b"RARC")
        stream.write(
            b"\xDD\xDD\xDD\xDD\x00\x00\x00\x20\xDD\xDD\xDD\xDD\xEE\xEE\xEE\xEE"
        )
        write_uint32(stream, self.metaInfo.mramSize)
        write_uint32(stream, self.metaInfo.aramSize)
        write_uint32(stream, self.metaInfo.dvdSize)

        # Data Header
        write_uint32(stream, len(self.nodeInfo.directoryTable))
        stream.write(b"\xDD\xDD\xDD\xDD")
        write_uint32(stream, len(self.nodeInfo.nodeEntryTable))
        stream.write(b"\xDD\xDD\xDD\xDD")
        stream.write(b"\xEE\xEE\xEE\xEE")
        stream.write(b"\xEE\xEE\xEE\xEE")
        write_uint16(stream, len(self.nodeInfo.nodeEntryTable))
        write_bool(stream, self.sync_ids())

        # Padding
        stream.write(b"\x00\x00\x00\x00\x00")

        # Directory Nodes
        directoryEntryOffset = stream.tell()

        datasOffset = self.metaInfo.get_data_offset()
        stringTableOffset = self.metaInfo.get_string_table_offset()

        for directory in self.nodeInfo.directoryTable:
            directory.save(stream, stringTableOffset)

        # Padding
        write_pad32(stream)

        # File Entries
        fileEntryOffset = stream.tell()
        for i, entry in enumerate(self.nodeInfo.nodeEntryTable):
            entry.save(
                stream,
                datasOffset,
                stringTableOffset,
                i if self.nodeInfo.syncIDs else None,
            )

        # Padding
        write_pad32(stream)

        # String Table
        validStringTableOffset = stream.tell()
        assert (
            validStringTableOffset == stringTableOffset
        ), f"String table offset is invalid. Expected {stringTableOffset}, got {validStringTableOffset}"
        stream.write(stringTableData.strings)

        # Padding
        write_pad32(stream)

        # File Table
        validDatasOffset = stream.tell()
        assert (
            validDatasOffset == datasOffset
        ), f"Data offset is invalid. Expected {datasOffset}, got {validDatasOffset}"
        stream.write(dataTable.getvalue())

        # Header
        rarcSize = len(stream.getvalue())

        stream.seek(0x4, 0)
        write_uint32(stream, rarcSize)
        stream.seek(0x4, 1)
        write_uint32(stream, datasOffset - 0x20)
        write_uint32(stream, rarcSize - datasOffset)
        stream.seek(0x10, 1)
        write_uint32(stream, directoryEntryOffset - 0x20)
        stream.seek(0x4, 1)
        write_uint32(stream, fileEntryOffset - 0x20)
        write_uint32(stream, datasOffset - stringTableOffset)
        write_uint32(stream, stringTableOffset - 0x20)

        return stream.getvalue()

    @classmethod
    def import_from(self, path: Path | str) -> ResourceHandle | None:
        if isinstance(path, str):
            path = Path(path)

        if not path.is_dir():
            return None

        archive = ResourceArchive(path.name)

        for p in path.iterdir():
            resource = ResourceHandle.import_from(p)

            if resource is None:
                continue

            archive.add_handle(resource)

        return archive

    def export_to(
        self,
        path: Path | str,
        *,
        action: FileConflictAction = FileConflictAction.REPLACE,
    ) -> bool:
        if isinstance(path, str):
            path = Path(path)

        rootPath = path / self.rootInfo.name
        rootPath.mkdir(parents=True, exist_ok=True)

        for node in self.rootInfo.subNodes:
            ResourceHandle(node).export_to(rootPath, action=action)

        return True

    def get_handle(
        self, __path: PurePath | str, /, *, flatten: bool = False
    ) -> ResourceHandle | None:
        if isinstance(__path, str):
            __path = PurePath(__path)
        if len(__path.parts) == 0:
            return None
        if len(__path.parts) == 1:
            # Get the handle from the root directory
            for node in self.rootInfo.subNodes:
                if node.name == __path.name:
                    return ResourceHandle(node)
        # Get the handle from the subdirectory
        for node in self.rootInfo.subNodes:
            if node.name == __path.parts[0]:
                return ResourceHandle(node).get_handle(
                    __path.relative_to(__path.parts[0]), flatten=flatten
                )
        return None

    def get_handles(self, *, flatten: bool = False) -> list[ResourceHandle]:
        if flatten:
            return [
                ResourceHandle(node)
                for node in self.rootInfo.nodeEntryTable
                if node.name not in [".", ".."]
            ]
        return [
            ResourceHandle(node)
            for node in self.rootInfo.subNodes
            if node.name not in [".", ".."]
        ]

    def add_handle(self, handle: ResourceHandle, /) -> bool:
        if handle.is_directory():
            return False

        if handle._nodeEntry in self.rootInfo.subNodes:
            return False

        self.rootInfo.subNodes.append(handle._nodeEntry)
        self.rootInfo.fileCount += 1
        handle._nodeEntry.parent = self.rootInfo
        return True

    def remove_path(self, __path: PurePath | str, /) -> bool:
        if isinstance(__path, str):
            __path = PurePath(__path)
        if len(__path.parts) == 0:
            return False
        if len(__path.parts) == 1:
            for node in self.rootInfo.subNodes:
                if node.name == __path.name:
                    self.rootInfo.subNodes.remove(node)
                    self.rootInfo.fileCount -= 1
                    node.parent = None
                    return True
        for node in self.rootInfo.subNodes:
            if node.name == __path.parts[0]:
                return ResourceHandle(node).remove_path(
                    __path.relative_to(__path.parts[0])
                )

    def rename(
        self,
        __path: PurePath | str,
        /,
        *,
        action: FileConflictAction = FileConflictAction.REPLACE,
    ) -> bool:
        if isinstance(__path, str):
            __path = PurePath(__path)
        if len(__path.parts) > 1:
            return False
        self.set_name(__path.name)
        return True

    def sync_ids(self) -> bool:
        return self._syncIDs

    def get_next_free_id(self) -> int:
        allIDs: list[int] = []
        for handle in self.get_handles(flatten=True):
            if handle.is_directory():
                continue
            allIDs.append(handle.get_id())

        if len(allIDs) == 0:
            return 0

        allIDs.sort()
        for i in range(allIDs[0] + 1, allIDs[-1]):
            if i not in allIDs:
                return i
        return len(allIDs)

    def regenerate_ids(self) -> None:
        if not self.sync_ids():
            return
        nodeID = 0
        for handle in self.get_handles(flatten=True):
            if handle.is_directory():
                continue
            handle.set_id(nodeID)
            nodeID += 1

    def regenerate_flat_lists(self) -> None:
        self.nodeInfo.fileTable = []
        self._regenerate_flat_lists_for_node(self.rootInfo)

    def _regenerate_flat_lists_for_node(self, dirInfo: InternalDirectoryEntry) -> None:
        # Sort the subnodes
        specialNodes = []
        for child in dirInfo.subNodes:
            if child.is_directory() and child.name in [".", ".."]:
                specialNodes.append(child)
        for specialNode in specialNodes:
            dirInfo.subNodes.remove(specialNode)
            dirInfo.subNodes.append(specialNode)

        dirInfo.firstFileOffset = self.nodeInfo.fileEntryCount
        self.nodeInfo.nodeEntryTable.extend(dirInfo.subNodes)

        for child in dirInfo.subNodes:
            if child.is_directory() and child.name not in [".", ".."]:
                self._regenerate_flat_lists_for_node(child.dirInfo)

    def _regenerate_data_info(self, offset: int) -> BytesIO:
        mramData = b""
        aramData = b""
        dvdData = b""

        offsetMap: dict[ResourceHandle, int] = {}

        startOffset = offset
        sortedHandles = self._get_files_by_load_type()
        for handle in sortedHandles.mram:
            data = handle.get_data()
            # Check if the data is already in the MRAM data
            for otherHandle in sortedHandles.mram:
                if otherHandle is handle:
                    continue
                if otherHandle.get_data() == data:
                    offsetMap[handle] = offsetMap[otherHandle]
                    break
            else:
                offsetMap[handle] = offset
            handle._nodeEntry.modularA = offsetMap[handle]
            mramData += data
            offset += len(data)

        self.metaInfo.mramSize = offset - startOffset

        startOffset = offset
        for handle in sortedHandles.aram:
            data = handle.get_data()
            # Check if the data is already in the ARAM data
            for otherHandle in sortedHandles.aram:
                if otherHandle is handle:
                    continue
                if otherHandle.get_data() == data:
                    offsetMap[handle] = offsetMap[otherHandle]
                    break
            else:
                offsetMap[handle] = offset
            aramData += data
            offset += len(data)

        self.metaInfo.aramSize = offset - startOffset

        startOffset = offset
        for handle in sortedHandles.dvd:
            data = handle.get_data()
            # Check if the data is already in the DVD data
            for otherHandle in sortedHandles.dvd:
                if otherHandle is handle:
                    continue
                if otherHandle.get_data() == data:
                    offsetMap[handle] = offsetMap[otherHandle]
                    break
            else:
                offsetMap[handle] = offset
            dvdData += data
            offset += len(data)

        self.metaInfo.dvdSize = offset - startOffset

        return BytesIO(mramData + aramData + dvdData)

    def _get_string_table_data(
        self, fileList: list[InternalNodeEntry]
    ) -> StringTableData:
        offsets: dict[str, int] = {}
        stringBuf = BytesIO()

        rootName = self.get_name()
        offsets[rootName] = 0
        write_string(stringBuf, rootName)

        # Write the special nodes
        offsets["."] = stringBuf.tell()
        write_string(stringBuf, ".")

        offsets[".."] = stringBuf.tell()
        write_string(stringBuf, "..")

        # Write the rest of the nodes
        for entry in fileList:
            # Skip duplicate names
            if entry.name not in offsets:
                offsets[entry.name] = stringBuf.tell()
                write_string(stringBuf, entry.name)

        return ResourceArchive._StringTableData(stringBuf.getvalue(), offsets)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, ResourceArchive):
            return False

        if self.get_name() != __o.get_name():
            return False

        return self.get_handles() == __o.get_handles()

    def __ne__(self, __o: object) -> bool:
        if not isinstance(__o, ResourceArchive):
            return True

        if self.get_name() != __o.get_name():
            return True

        return self.get_handles() != __o.get_handles()

    def __hash__(self) -> int:
        return hash((self.get_name(), self.get_size()))

    def __repr__(self) -> str:
        return f"ResourceArchive({self.get_name()}, {self.get_size()} bytes)"

    def __str__(self) -> str:
        return f"ResourceArchive({self.get_name()}, {self.get_size()} bytes)"
