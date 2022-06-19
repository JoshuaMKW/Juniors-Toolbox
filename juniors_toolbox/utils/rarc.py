from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import subprocess
import tempfile
import time
from enum import IntEnum
from io import BytesIO
from itertools import chain
from pathlib import Path, PurePath
from struct import pack, unpack
from typing import BinaryIO, Optional
from aenum import IntFlag

import oead
from juniors_toolbox.utils import A_Serializable, ReadableBuffer, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.iohelper import (read_string, read_ubyte,
                                           read_uint16, read_uint32,
                                           write_string, write_ubyte,
                                           write_uint16, write_uint32)


def write_pad32(f: BinaryIO):
    next_aligned_pos = (f.tell() + 0x1F) & ~0x1F
    f.write(b"\x00"*(next_aligned_pos - f.tell()))



class ResourceAttribute(IntFlag):
    FILE = 0x01
    DIRECTORY = 0x02
    COMPRESSED = 0x04
    PRELOAD_TO_MRAM = 0x10
    PRELOAD_TO_ARAM = 0x20
    LOAD_FROM_DVD = 0x40
    YAZ0_COMPRESSED = 0x80  # Uses YAZ0 compression


class A_ResourceHandle():

    @dataclass
    class _DataInformation:
        data: BytesIO
        offsets: dict["A_ResourceHandle", int]
        mramSize: int
        aramSize: int
        dvdSize: int

    @dataclass
    class _LoadSortedHandles:
        mram: list["A_ResourceHandle"]
        aram: list["A_ResourceHandle"]
        dvd: list["A_ResourceHandle"]

    def __init__(
        self,
        name: str,
        parent: Optional["A_ResourceHandle"] = None,
        attributes: ResourceAttribute = ResourceAttribute.PRELOAD_TO_MRAM
    ):
        self._archive: Optional["ResourceArchive"] = None
        self._name = name

        self._parent = parent
        if parent is not None:
            self._archive = parent._archive

        self._attributes = attributes

    def is_flagged(self, attribute: ResourceAttribute | int) -> bool:
        return (self._attributes & attribute) != 0

    def set_flag(self, attribute: ResourceAttribute, active: bool) -> None:
        if active:
            self._attributes |= attribute
        else:
            self._attributes &= attribute

    def get_name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name

    def get_extension(self) -> str:
        return self._name.split(".")[-1]

    def set_extension(self, extension: str):
        parts = self._name.split(".")
        parts[-1] = extension
        self._name = ".".join(parts)

    def get_stem(self) -> str:
        if "." not in self._name:
            return self._name
        return ".".join(self._name.split(".")[:-1])

    def set_stem(self, stem: str):
        if "." not in self._name:
            self._name = stem
            return

        index = -1
        extIndex = 0
        while (index := self._name.find(".", index+1)) != -1:
            extIndex = index

        self._name = stem + self._name[extIndex:]

    def get_path(self) -> PurePath:
        path = PurePath(self.get_name())
        parent = self.get_parent()
        while parent is not None:
            path = parent.get_name() / path
            parent = parent.get_parent()
        return path

    def get_archive(self) -> Optional["ResourceArchive"]:
        return self._archive

    def get_parent(self) -> Optional["A_ResourceHandle"]:
        return self._parent

    def set_parent(self, handle: "A_ResourceHandle"):
        self._parent = handle

    @abstractmethod
    def is_directory(self) -> bool: ...

    @abstractmethod
    def is_file(self) -> bool: ...

    @abstractmethod
    def get_size(self) -> int: ...

    @abstractmethod
    def get_data(self) -> bytes: ...

    @abstractmethod
    def get_raw_data(self) -> bytes: ...

    @abstractmethod
    def get_handles(self, *, flatten: bool = False) -> list["A_ResourceHandle"]: ...

    @abstractmethod
    def get_handle(self, path: PurePath) -> Optional["A_ResourceHandle"]: ...

    @abstractmethod
    def exists(self, path: PurePath) -> bool: ...

    @abstractmethod
    def new_file(
        self,
        name: str,
        initialData: bytes | bytearray = b"",
        attributes: ResourceAttribute = ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]: ...

    @abstractmethod
    def new_directory(
        self,
        name: str,
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]: ...

    @abstractmethod
    def export_to(self, folderPath: Path) -> bool: ...

    @abstractmethod
    @classmethod
    def import_from(self, path: Path) -> Optional["A_ResourceHandle"]: ...

    @abstractmethod
    def read(self, __size: int, /) -> bytes: ...

    @abstractmethod
    def write(self, __buffer: ReadableBuffer, /) -> int: ...

    @abstractmethod
    def seek(self, __offset: int, __whence: int = os.SEEK_CUR) -> int: ...

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
                    raise ValueError(f"Resource handle {handle.get_name()} isn't set to load")
        return A_ResourceHandle._LoadSortedHandles(
            mramHandles,
            aramHandles,
            dvdHandles
        )

    def _get_data_info(self, offset: int) -> _DataInformation:
        mramData = b""
        aramData = b""
        dvdData = b""

        offsetMap: dict["A_ResourceHandle", int] = {}

        startOffset = offset
        sortedHandles = self._get_files_by_load_type()
        for handle in sortedHandles.mram:
            offsetMap[handle] = offset
            data = handle.get_data()
            mramData += data
            offset += len(data)

        mramSize = offset - startOffset

        startOffset = offset
        for handle in sortedHandles.aram:
            offsetMap[handle] = offset
            data = handle.get_data()
            aramData += data
            offset += len(data)

        aramSize = offset - startOffset

        startOffset = offset
        for handle in sortedHandles.dvd:
            offsetMap[handle] = offset
            data = handle.get_data()
            dvdData += data
            offset += len(data)

        dvdSize = offset - startOffset

        return A_ResourceHandle._DataInformation(
            data=BytesIO(mramData + aramData + dvdData),
            offsets=offsetMap,
            mramSize=mramSize,
            aramSize=aramSize,
            dvdSize=dvdSize
        )


class ResourceDirectory(A_ResourceHandle):
    def __init__(
        self,
        name: str,
        parent: Optional["A_ResourceHandle"] = None,
        children: Optional[list["A_ResourceHandle"]] = None, 
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM
    ):
        super().__init__(name, parent, attributes)
        
        if children is None:
            children = []
        self._children = children

    def is_directory(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def get_size(self) -> int:
        return 0

    def get_data(self) -> bytes:
        return b""

    def get_raw_data(self) -> bytes:
        return b""

    def get_handles(self, *, flatten: bool = False) -> list["A_ResourceHandle"]:
        if not flatten:
            return self._children

        def _get_r_handles(thisHandle: "A_ResourceHandle", handles: list) -> None:
            for handle in thisHandle.get_handles():
                if handle.is_directory():
                    _get_r_handles(handle, handles)
                elif handle.is_file():
                    handles.append(handle)
                else:
                    raise ValueError(f"Handle \"{handle.get_name}\" is not a file nor directory")
        
        handles: list[A_ResourceHandle] = []
        _get_r_handles(self, handles)

        return handles

    def get_handle(self, path: PurePath) -> Optional["A_ResourceHandle"]:
        curDir, *subParts = path.parts
        curDir = str(curDir)
        for handle in self.get_handles():
            if handle.get_name() == curDir:
                if len(subParts) == 0:
                    return handle
                return handle.get_handle(
                    PurePath(*subParts)
                )
        return None

    def exists(self, path: PurePath) -> bool:
        return self.get_handle(path) is not None

    def new_file(
        self,
        name: str,
        initialData: bytes | bytearray = b"",
        attributes: ResourceAttribute = ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        if self.exists(PurePath(name)):
            return None

        newFile = ResourceFile(
            name,
            initialData,
            self,
            attributes
        )

        self._children.append(newFile)
        return newFile

    def new_directory(
        self,
        name: str,
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        if self.exists(PurePath(name)):
            return None

        newDir = ResourceDirectory(
            name,
            self,
            attributes=attributes
        )

        self._children.append(newDir)
        return newDir

    def export_to(self, folderPath: Path) -> bool:
        if not folderPath.is_dir():
            return False

        thisDir = folderPath / self.get_name()
        thisDir.mkdir(exist_ok=True)

        successful = True
        for handle in self.get_handles():
            successful &= handle.export_to(thisDir)

        return successful

    @classmethod
    def import_from(self, path: Path) -> Optional["A_ResourceHandle"]:
        if not path.is_dir():
            return None

        thisResource = ResourceDirectory(path.name)

        for p in path.iterdir():
            resource: A_ResourceHandle | None
            if p.is_dir():
                resource = ResourceDirectory.import_from(p)
            elif p.is_file():
                resource = ResourceFile.import_from(p)

            if resource is None:
                continue

            thisResource._children.append(resource)

        return thisResource

    def read(self, __size: int, /) -> bytes:
        raise RuntimeError("Resource directories don't have read support")

    def write(self, __buffer: ReadableBuffer, /) -> int:
        raise RuntimeError("Resource directories don't have write support")

    def seek(self, __offset: int, __whence: int = os.SEEK_CUR) -> int:
        return 0


class ResourceFile(A_ResourceHandle):
    def __init__(
        self,
        name: str,
        initialData: bytes | bytearray = b"",
        parent: Optional["A_ResourceHandle"] = None,
        attributes: ResourceAttribute = ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM
    ):
        super().__init__(name, parent, attributes)

        self._data = BytesIO(initialData)
        self._curPos = 0

    def is_directory(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def get_size(self) -> int:
        return 0

    def get_data(self) -> bytes:
        data = self.get_raw_data()

        fill = 32 - (len(data) % 32)
        if fill == 32:
            return data

        return data + b"\x00" * fill

    def get_raw_data(self) -> bytes:
        return self._data.getvalue()

    def get_handles(self, *, flatten: bool = False) -> list["A_ResourceHandle"]:
        return []

    def get_handle(self, path: PurePath) -> Optional["A_ResourceHandle"]:
        return None

    def exists(self, path: PurePath) -> bool:
        return self.get_handle(path) is not None

    def new_file(
        self,
        name: str,
        initialData: bytes | bytearray = b"",
        attributes: ResourceAttribute = ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        return None

    def new_directory(
        self,
        name: str,
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        return None

    def export_to(self, folderPath: Path) -> bool:
        if not folderPath.is_dir():
            return False

        thisFile = folderPath / self.get_name()
        thisFile.write_bytes(
            self.get_data()
        )

        return True

    @classmethod
    def import_from(self, path: Path) -> Optional["A_ResourceHandle"]:
        if not path.is_file():
            return None

        return ResourceFile(
            path.name,
            path.read_bytes()
        )

    def read(self, __size: int, /) -> bytes:
        return self._data.read(__size)

    def write(self, __buffer: ReadableBuffer, /) -> int:
        return self._data.write(__buffer)

    def seek(self, __offset: int, __whence: int = os.SEEK_CUR) -> int:
        return self._data.seek(__offset, __whence)


class ResourceArchive(ResourceDirectory):
    @dataclass
    class RARCFileEntry:
        fileID: int
        flags: ResourceAttribute
        name: str
        offset: int
        size: int
        nameHash: int

    def __init__(
        self,
        rootName: str,
        parent: Optional["A_ResourceHandle"] = None,
        children: Optional[list["A_ResourceHandle"]] = None
    ):
        super().__init__(rootName, parent, children)
        
        if children is None:
            children = []
        self._children = children

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional[A_Serializable]:
        ...

    def to_bytes(self) -> bytes:
        stream = BytesIO()

        dataInfo = self._get_data_info(0)
        fileID = 0
        nextFolderID = 1
        

        

    def is_directory(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def get_size(self) -> int:
        return 0

    def get_handles(self) -> list["A_ResourceHandle"]:
        return self._children

    def get_handle(self, path: PurePath) -> Optional["A_ResourceHandle"]:
        curDir, *subParts = path.parts
        curDir = str(curDir)
        for handle in self.get_handles():
            if handle.get_name() == curDir:
                if len(subParts) == 0:
                    return handle
                return handle.get_handle(
                    PurePath(*subParts)
                )
        return None

    def exists(self, path: PurePath) -> bool:
        return self.get_handle(path) is not None

    def new_file(
        self,
        name: str,
        initialData: bytes | BinaryIO = b"",
        attributes: ResourceAttribute = ResourceAttribute.FILE | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        return None

    def new_directory(
        self,
        name: str,
        attributes: ResourceAttribute = ResourceAttribute.DIRECTORY | ResourceAttribute.PRELOAD_TO_MRAM
    ) -> Optional["A_ResourceHandle"]:
        return None

    def export_to(self, folderPath: Path) -> bool:
        if not folderPath.is_dir():
            return False

        thisFile = folderPath / self.get_name()
        thisFile.write_bytes(
            self.to_bytes()
        )

        return True

    @classmethod
    def import_from(self, path: Path) -> Optional["A_ResourceHandle"]:
        if not path.is_file():
            return None

        return ResourceFile(
            path.name,
            path.read_bytes()
        )


class CompressionSetting():
    def __init__(self, yaz0_fast=False, wszst=False, compression_level="9"):
        self.yaz0_fast = yaz0_fast
        self.wszst = wszst
        self.compression_level = compression_level

    def run_wszst(self, file):
        if not self.wszst:
            raise RuntimeError("Wszst is not used")
        handle, abspath = tempfile.mkstemp()
        os.close(handle)
        filedata = file.getvalue()
        with open(abspath, "wb") as f:
            print("writing to", abspath)
            f.write(filedata)
            f.close()

        outpath = abspath+".yaz0_tmp"
        args = ["wszst", "COMPRESS", abspath, "--dest",
                outpath, "--compr", self.compression_level]
        try:
            subprocess.run(args, check=True)
        except Exception as err:
            print("Encountered error, cleaning up...")
            os.remove(abspath)
            raise

        with open(outpath, "rb") as f:
            compressed_data = f.read()

        os.remove(abspath)
        os.remove(outpath)

        if len(filedata) >= len(compressed_data):
            return compressed_data
        else:
            print("Compressed data bigger than original, using uncompressed data")
            return filedata


class FileListing():
    def __init__(
        self,
        isFile: bool,
        isCompressed: bool = False,
        isPreloadToMRAM: bool = False,
        isPreloadToARAM: bool = False,
        isLoadFromDVD: bool = True,
        isYAZ0Compressed: bool = True
    ):
        flags = 0b01 if isFile else 0b10
        flags |= int(isCompressed) << 2
        flags |= int(isPreloadToMRAM) << 4
        flags |= int(isPreloadToARAM) << 5
        flags |= int(isLoadFromDVD) << 6
        flags |= int(isYAZ0Compressed) << 7
        self._flags = flags

    @classmethod
    def from_flags(cls, flags):
        if flags & 0x40:
            print("Unknown flag 0x40 set")
        if flags & 0x8:
            print("Unknown flag 0x8 set")

        return cls(flags & ResourceAttribute.FILE != 0,
                   flags & ResourceAttribute.DIRECTORY != 0,
                   flags & ResourceAttribute.COMPRESSED != 0,
                   flags & ResourceAttribute.PRELOAD_TO_MRAM != 0,
                   flags & ResourceAttribute.PRELOAD_TO_ARAM != 0,
                   flags & ResourceAttribute.LOAD_FROM_DVD != 0,
                   flags & ResourceAttribute.YAZ0_COMPRESSED != 0)

    def isFile(self) -> bool:
        return bool(self._flags & ResourceAttribute.FILE)

    def isDir(self) -> bool:
        return bool(self._flags & ResourceAttribute.DIRECTORY)

    def isCompressed(self) -> bool:
        return bool(self._flags & ResourceAttribute.COMPRESSED)

    def isPreloadToMRAM(self) -> bool:
        return bool(self._flags & ResourceAttribute.PRELOAD_TO_MRAM)

    def isPreloadToARAM(self) -> bool:
        return bool(self._flags & ResourceAttribute.PRELOAD_TO_ARAM)

    def isLoadFromDVD(self) -> bool:
        return bool(self._flags & ResourceAttribute.LOAD_FROM_DVD)

    def isYAZ0(self) -> bool:
        return bool(self._flags & ResourceAttribute.YAZ0_COMPRESSED)

    def get_flags(self) -> int:
        return self._flags

    def to_string(self) -> str:
        result = []
        if self.isFile():
            result.append("FILE")
        elif self.isDir():
            result.append("DIR")
        else:
            raise ValueError("Archive is neither a file nor directory?")

        if self.isCompressed():
            result.append("YAZ0" if self.isYAZ0() else "YAY0")

        if self.isPreloadToMRAM():
            result.append("MRAM")
        elif self.isPreloadToARAM():
            result.append("ARAM")
        elif self.isLoadFromDVD():
            result.append("DVD")

        return "[" + "|".join(result) + "]"

    @classmethod
    def from_string(cls, string: str):
        settings = {
            "FILE": False,
            "DIR": False,
            "COMPRESSED": False,
            "MRAM": False,
            "ARAM": False,
            "DVD": False,
            "YAZ0": False
        }

        result = string[1:-1].split("|")
        for setting in result:
            settings[setting] = True

        if not any((settings["FILE"], settings["DIR"])):
            raise ValueError("Archive is neither a file nor directory?")

        return cls(
            settings["FILE"],
            settings["COMPRESSED"],
            settings["MRAM"],
            settings["ARAM"],
            settings["DVD"],
            settings["YAZ0"]
        )

    @classmethod
    def default(cls):
        # Default is a uncompressed Data File
        return cls(True, False, False, True, False, True)

    def __str__(self):
        return str(self.__dict__)
