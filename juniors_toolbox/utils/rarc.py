from abc import ABC, abstractmethod
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
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs
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


class A_ResourceHandle(A_Serializable):
    def __init__(self, name: str, parent: Optional["A_ResourceHandle"] = None, children: Optional[list["A_ResourceHandle"]] = None):
        self._archive: Optional["ResourceArchive"] = None
        self._name = name

        self._parent = parent
        if parent is not None:
            self._archive = parent._archive
            
        if children is None:
            children = []
        self._children = children

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

    def get_path(self) -> Path:
        path = Path(self.get_name())
        parent = self.get_parent()
        while parent is not None:
            path = parent.get_name() / path
            parent = parent.get_parent()
        return path

    def get_abs_path(self) -> Path:
        path = Path(self.get_name())
        parent = self.get_parent()
        while parent is not None:
            path = parent.get_name() / path
            parent = parent.get_parent()
        if self._archive is None:
            return path
        return self._archive.get_abs_path() / path

    def get_archive(self) -> Optional["ResourceArchive"]:
        return self._archive

    def get_parent(self) -> Optional["A_ResourceHandle"]:
        return self._parent

    def set_parent(self, handle: "A_ResourceHandle"):
        self._parent = handle

    @abstractmethod
    def is_folder(self) -> bool: ...

    @abstractmethod
    def is_file(self) -> bool: ...

    @abstractmethod
    def get_size(self) -> int: ...

    @abstractmethod
    def get_data(self) -> BytesIO: ...

    @abstractmethod
    def get_children(self) -> list["A_ResourceHandle"]: ...

    @abstractmethod
    def new_file(self, name: str, initialData: bytes | BinaryIO = b"") -> "A_ResourceHandle": ...

    @abstractmethod
    def new_directory(self, name: str) -> "A_ResourceHandle": ...

    @abstractmethod
    def export_to(self, folderPath: Path, preserveVirtualPath: bool = False) -> bool: ...

    @abstractmethod
    @classmethod
    def import_from(self, path: Path) -> "A_ResourceHandle": ...


class ResourceArchive(A_Serializable):
    def __init__(self, attributes: ResourceAttribute) -> None:
        self._attributes = attributes

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional[A_Serializable]:
        return super().from_bytes(data, *args, **kwargs)

    def to_bytes(self) -> bytes:
        return super().to_bytes()

    def is_flagged(self, attribute: ResourceAttribute) -> bool:
        return (self._attributes & attribute) != 0

    def set_flag(self, attribute: ResourceAttribute, active: bool) -> None:
        if active:
            self._attributes |= attribute
        else:
            self._attributes &= attribute

    def exists(self, path: Path) -> bool:
        return False

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
