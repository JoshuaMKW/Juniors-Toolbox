from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing.sharedctypes import Value
from typing import Any, BinaryIO, Callable, Dict, Iterable, List, Optional, overload
from juniors_toolbox.gui.templates import TemplateEnumType
from juniors_toolbox.utils import A_Clonable

from juniors_toolbox.utils.iohelper import (read_bool, read_double, read_float,
                                            read_sbyte, read_sint16,
                                            read_sint32, read_string,
                                            read_ubyte, read_uint16,
                                            read_uint32, read_vec3f,
                                            write_bool, write_double,
                                            write_float, write_sbyte,
                                            write_sint16, write_sint32,
                                            write_string, write_ubyte,
                                            write_uint16, write_uint32,
                                            write_vec3f)
from juniors_toolbox.utils.types import RGB8, RGB32, RGBA8, Transform, Vec3f


class QualifiedName():
    def __init__(self, *scopes: str):
        self.__scopes = []
        for scope in scopes:
            self.__scopes.extend(scope.split("::"))
        self.__iter = -1

    def scopes(self, other: "QualifiedName") -> bool:
        """
        Check if this scopes another qualified name
        """
        return str(other).startswith(str(self))

    def __iter__(self):
        self.__iter = -1
        return self

    def __next__(self) -> str:
        self.__iter += 1
        if self.__iter > len(self.__scopes):
            raise StopIteration
        return self.__scopes[self.__iter]

    @overload
    def __getitem__(self, index: slice) -> List[str]: ...
    @overload
    def __getitem__(self, index: int) -> str: ...

    def __getitem__(self, index: int | slice) -> str | List[str]:
        if isinstance(index, slice):
            return self.__scopes[index.start:index.stop:index.step]
        return self.__scopes[index]

    def __setitem__(self, index: int, scope: str):
        self.__scopes[index] = scope

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(\"{self.__str__()}\")"

    def __str__(self) -> str:
        return "::".join(self.__scopes)

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (QualifiedName, str)):
            return str(self) == str(other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, (QualifiedName, str)):
            return str(self) != str(other)
        return NotImplemented

    def __add__(self, other: str) -> "QualifiedName":
        return QualifiedName(str(self), str(other))

    def __iadd__(self, other: str) -> "QualifiedName":
        self.__scopes.append(other)
        return self


class ValueType(str, Enum):
    BOOL = "BOOL"
    BYTE = "BYTE"
    CHAR = "CHAR"
    S8 = "S8"
    U8 = "U8"
    SHORT = "SHORT"
    S16 = "S16"
    U16 = "U16"
    S32 = "S32"
    INT = "INT"
    U32 = "U32"
    F32 = "F32"
    FLOAT = "FLOAT"
    F64 = "F64"
    DOUBLE = "DOUBLE"
    STR = "STR"
    STRING = "STRING"
    C_RGB8 = "RGB8"
    C_RGBA8 = "RGBA8"
    C_RGB32 = "RGB32"
    C_RGBA = "COLOR"
    VECTOR3 = "VEC3F"
    TRANSFORM = "TRANSFORM"
    COMMENT = "COMMENT"
    STRUCT = "STRUCT"
    ENUM = "ENUM"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

    @staticmethod
    def type_to_enum(_ty: type):
        """
        Convert a type to the Enum equivalent
        """
        return ValueType(_ty.__name__.upper())

    def to_type(self) -> Optional[type]:
        """
        Convert this to a type
        """
        return _ENUM_TO_TYPE_TABLE[self]

    def is_signed(self) -> bool:
        """
        Return if the type is signed
        """
        return _ENUM_TO_SIGNED_TABLE[self]

    def get_size(self) -> Optional[int]:
        """
        Return the physical size of the data type
        """
        return _ENUM_TO_SIZE_TABLE[self]


def __read_bin_string(f: BinaryIO) -> str:
    len = read_uint16(f)
    if len == 0:
        return ""
    return read_string(f, maxlen=len-1, encoding="shift-jis")


def __write_bin_string(f: BinaryIO, val: str):
    raw = val.encode("shift-jis")
    write_uint16(f, len(raw))
    f.write(raw)


def __read_transform(f: BinaryIO) -> Transform:
    _t = Transform()
    _t.translate(read_vec3f(f))
    _t.rotate(read_vec3f(f))
    _t.scale = Vec3f(*read_vec3f(f))
    return _t


def __write_transform(f: BinaryIO, val: Transform):
    write_vec3f(f, val.translation)
    write_vec3f(f, val.rotation.to_euler())
    write_vec3f(f, val.scale)


_ENUM_TO_TYPE_TABLE = {
    ValueType.BOOL: bool,
    ValueType.BYTE: int,
    ValueType.CHAR: int,
    ValueType.S8: int,
    ValueType.U8: int,
    ValueType.SHORT: int,
    ValueType.S16: int,
    ValueType.U16: int,
    ValueType.S32: int,
    ValueType.INT: int,
    ValueType.U32: int,
    ValueType.F32: float,
    ValueType.FLOAT: float,
    ValueType.F64: float,
    ValueType.DOUBLE: float,
    ValueType.STR: str,
    ValueType.STRING: str,
    ValueType.ENUM: int,
    ValueType.C_RGB8: RGB8,
    ValueType.C_RGBA8: RGBA8,
    ValueType.C_RGB32: RGB8,
    ValueType.C_RGBA: RGBA8,
    ValueType.VECTOR3: Vec3f,
    ValueType.COMMENT: str,
    ValueType.STRUCT: None
}

_ENUM_TO_SIZE_TABLE = {
    ValueType.BOOL: 1,
    ValueType.BYTE: 1,
    ValueType.CHAR: 1,
    ValueType.S8: 1,
    ValueType.U8: 1,
    ValueType.SHORT: 2,
    ValueType.S16: 2,
    ValueType.U16: 2,
    ValueType.S32: 4,
    ValueType.INT: 4,
    ValueType.U32: 4,
    ValueType.F32: 4,
    ValueType.FLOAT: 4,
    ValueType.F64: 8,
    ValueType.DOUBLE: 8,
    ValueType.STR: None,
    ValueType.STRING: None,
    ValueType.ENUM: 4,
    ValueType.C_RGB8: 3,
    ValueType.C_RGBA8: 4,
    ValueType.C_RGB32: 12,
    ValueType.C_RGBA: 4,
    ValueType.VECTOR3: 12,
    ValueType.COMMENT: None,
    ValueType.STRUCT: None
}

_ENUM_TO_SIGNED_TABLE = {
    ValueType.BOOL: False,
    ValueType.BYTE: True,
    ValueType.CHAR: True,
    ValueType.S8: True,
    ValueType.U8: False,
    ValueType.SHORT: True,
    ValueType.S16: True,
    ValueType.U16: False,
    ValueType.S32: True,
    ValueType.INT: True,
    ValueType.U32: False,
    ValueType.F32: False,
    ValueType.FLOAT: False,
    ValueType.F64: False,
    ValueType.DOUBLE: False,
    ValueType.STR: False,
    ValueType.STRING: False,
    ValueType.ENUM: False,
    ValueType.C_RGB8: False,
    ValueType.C_RGBA8: False,
    ValueType.C_RGB32: False,
    ValueType.C_RGBA: False,
    ValueType.VECTOR3: False,
    ValueType.COMMENT: False,
    ValueType.STRUCT: False
}


TEMPLATE_TYPE_READ_TABLE: dict[ValueType, Callable[[BinaryIO], Any]] = {
    ValueType.BOOL: read_bool,
    ValueType.BYTE: read_ubyte,
    ValueType.CHAR: read_ubyte,
    ValueType.S8: read_sbyte,
    ValueType.U8: read_ubyte,
    ValueType.SHORT: read_sint16,
    ValueType.S16: read_sint16,
    ValueType.U16: read_uint16,
    ValueType.S32: read_sint32,
    ValueType.INT: read_sint32,
    ValueType.U32: read_uint32,
    ValueType.F32: read_float,
    ValueType.FLOAT: read_float,
    ValueType.F64: read_double,
    ValueType.DOUBLE: read_double,
    ValueType.STR: __read_bin_string,
    ValueType.STRING: __read_bin_string,
    ValueType.ENUM: read_uint32,
    ValueType.C_RGB8: lambda f: RGB8.from_tuple((read_ubyte(f), read_ubyte(f), read_ubyte(f))),
    ValueType.C_RGBA8: lambda f: RGBA8(read_uint32(f)),
    ValueType.C_RGB32: lambda f: RGB32.from_tuple((read_uint32(f), read_uint32(f), read_uint32(f))),
    ValueType.C_RGBA: lambda f: RGBA8(read_uint32(f)),
    ValueType.VECTOR3: lambda f: Vec3f(*read_vec3f(f)),
    ValueType.TRANSFORM: __read_transform,
    ValueType.COMMENT: lambda f: None,
    ValueType.STRUCT: lambda f: None
}


TEMPLATE_TYPE_WRITE_TABLE: dict[ValueType, Callable[[BinaryIO, Any], None]] = {
    ValueType.BOOL: write_bool,
    ValueType.BYTE: write_ubyte,
    ValueType.CHAR: write_ubyte,
    ValueType.S8: write_sbyte,
    ValueType.U8: write_ubyte,
    ValueType.SHORT: write_sint16,
    ValueType.S16: write_sint16,
    ValueType.U16: write_uint16,
    ValueType.S32: write_sint32,
    ValueType.INT: write_sint32,
    ValueType.U32: write_uint32,
    ValueType.F32: write_float,
    ValueType.FLOAT: write_float,
    ValueType.F64: write_double,
    ValueType.DOUBLE: write_double,
    ValueType.STR: __write_bin_string,
    ValueType.STRING: __write_bin_string,
    ValueType.ENUM: write_uint32,
    ValueType.C_RGB8: lambda f, val: write_ubyte(f, val.tuple()),  # val = RGB8
    ValueType.C_RGBA8: lambda f, val: write_ubyte(f, val.tuple()),
    # val = RGB8
    ValueType.C_RGB32: lambda f, val: write_uint32(f, val.tuple()),
    ValueType.C_RGBA: write_uint32,
    ValueType.VECTOR3: write_vec3f,
    ValueType.TRANSFORM: __write_transform,
    ValueType.COMMENT: lambda f, val: None,
    ValueType.STRUCT: lambda f, val: None
}


class A_Member(A_Clonable, ABC):
    """
    Class describing a member of a structure
    """

    def __init__(self, name: str, value: Any, type: ValueType, *, readOnly: bool = False) -> None:
        self._name = name
        self._value = value
        self._type = type
        self._desc = ""
        self._readOnly = readOnly
        self._parent: Optional["MemberStruct"] = None
        self._arraySize: int | "MemberValue" = 1
        self._arrayIdx: int = 0
        self._arrayInstances: dict[int, "A_Member"] = {}
        self._referencedBy: list["A_Member"] = []

    @staticmethod
    def get_formatted_template_name(name: str, arrayidx: int) -> str:
        """
        Get a template name formatted
        """
        characters = "abcdefghijklmnopqrstuvwxyz"
        charactersLen = len(characters)
        chars = ""
        otherIdx = arrayidx
        for i in range(4, -1, -1):
            chars = "abcdefghijklmnopqrstuvwxyz"[otherIdx % charactersLen] + chars
            if otherIdx < 26:
                break
            otherIdx = (otherIdx // 26) - 1
        templateName = name.replace("{c}", chars)
        templateName = templateName.replace("{C}", chars.upper())
        templateName = templateName.replace("{i}", str(arrayidx))
        return templateName

    def is_from_array(self) -> bool:
        """
        Returns if this member is part of the array for another member
        """
        return self._arrayIdx != 0

    def is_referenced(self) -> bool:
        """
        Returns if this member is referenced by other members
        """
        return len(self._referencedBy) > 0

    def is_read_only(self) -> bool:
        return self._readOnly

    def get_value(self) -> Any:
        return self._value

    def set_value(self, value: Any):
        if not self.is_read_only() or True:
            self._value = value
        else:
            print("Tried setting value of read only member")

    def get_type(self) -> ValueType:
        return self._type

    def set_type(self, _type: ValueType):
        self._type = _type

    def get_description(self) -> str:
        return self._desc

    def set_description(self, desc: str):
        self._desc = desc

    def get_formatted_name(self) -> str:
        return self.get_formatted_template_name(self._name, self._arrayIdx)

    def get_concrete_name(self) -> str:
        """
        Return the name without formatters
        """
        name = self._name.replace("{c}", "")
        name = name.replace("{C}", "")
        name = name.replace("{i}", "")
        return name

    def get_parent(self) -> Optional["MemberStruct"]:
        """
        Get the parent of this `Member`, which is a `Member` representing a struct
        """
        return self._parent

    def set_parent(self, parent: "MemberStruct" | None) -> bool:
        """
        Set the parent, return True if successful (not an array instance)
        """
        if self.is_from_array():
            return False

        oldParent = self._parent
        if oldParent is not None:
            oldParent.remove_child(self)

        for i in range(self.get_array_size()):
            self[i]._parent = parent

        return True

    def get_qualified_name(self) -> QualifiedName:
        """
        Get the full formatted name of this `Member`, as is scoped from its parents
        """
        scopes = [self.get_formatted_name()]
        parent = self.get_parent()
        while parent is not None:
            scopes.append(parent.get_formatted_name())
            parent = parent.get_parent()
        return QualifiedName(*scopes[::-1])

    def is_defined_array(self) -> bool:
        """
        Check if this member has an indefinite array size
        """
        if self.is_from_array():
            return True

        if isinstance(self._arraySize, int):
            return self._arraySize > 0

        return True

    def get_array_size(self) -> int:
        """
        Get the array size of this member, which is the number of times this member is repeated
        """
        if self.is_from_array():
            return 1

        if isinstance(self._arraySize, int):
            if self._arraySize > 127:
                return 127
            elif self._arraySize <= 0:
                return 127
            return self._arraySize

        return int(self._arraySize._value)

    def set_array_size(self, arraySize: int | "MemberValue") -> None:
        """
        Set the array size of this member, which is either the size itself or a member holding it
        """
        if self.is_from_array():
            return

        if isinstance(self._arraySize, MemberValue):
            self._arraySize._referencedBy.remove(self)
        self._arraySize = arraySize
        if isinstance(arraySize, MemberValue):
            arraySize._referencedBy.append(self)

    @abstractmethod
    def is_struct(self) -> bool:
        """
        Check is this `Member` is a struct, meaning it has children `Member`s
        """
        ...

    @abstractmethod
    def has_child(self, name: str) -> bool:
        """
        Check if a child of the given name exists
        """
        ...

    @abstractmethod
    def add_child(self, member: "A_Member") -> bool:
        """
        Add a child to this `Member`, which implies this `Member` be a struct

        Returns False if the member already existed
        """
        ...

    @abstractmethod
    def remove_child(self, item: str | "A_Member") -> None:
        """
        Remove a child from this `Member`, which implies this `Member` be a struct
        """
        ...

    @abstractmethod
    def get_child(self, name: str) -> Optional["A_Member"]:
        """
        Get a child of the given name from this `Member`, which implies this `Member` be a struct
        """
        ...

    @abstractmethod
    def get_children(self, includeArrays: bool = True) -> Iterable["A_Member"]:
        """
        Get all children from this `Member`, which implies this `Member` be a struct

        If `includeArrays` is true, also yield array instances
        """
        ...

    @abstractmethod
    def get_data_size(self) -> int:
        """
        Get the raw data size of this member in bytes
        """
        ...

    @abstractmethod
    def load(self, stream: BinaryIO, endPos: Optional[int] = None) -> None:
        """
        Read the data from `stream` into this member
        """
        ...

    @abstractmethod
    def save(self, stream: BinaryIO) -> None:
        """
        Write the value from this member into `stream`
        """
        ...

    @abstractmethod
    def copy(self, *, deep: bool = False) -> "A_Member": ...

    def __getitem__(self, index: int | slice) -> "A_Member":
        if isinstance(index, slice):
            return NotImplemented

        if index not in range(self.get_array_size()) and self.get_array_size() > 0:
            raise IndexError("Index provided is beyond the member array")

        if index == 0:
            return self

        if index-1 in self._arrayInstances:
            item = self._arrayInstances[index-1]
            item._parent = self._parent
            item._arrayIdx = index
            return item

        _copy = self.copy(deep=True)
        _copy._parent = self._parent
        _copy._arrayIdx = index
        self._arrayInstances[index-1] = _copy
        return _copy

    def __setitem__(self, index: int, item: object) -> None:
        if not isinstance(item, A_Member):
            raise ValueError("Item is not of kind `A_Member`")

        if index not in range(self.get_array_size()) and self.get_array_size() > 0:
            raise IndexError("Index provided is beyond the member array")

        if index == 0:
            self._name = item._name
            self._value = item._value
            self._type = item._type
            return

        self._arrayInstances[index-1] = item
        item._arrayIdx = index
        item._parent = self.get_parent()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(qualname={self.get_qualified_name()}, value={self._value}, type={self._type})"


class MemberValue(A_Member):
    """
    Class describing a member value
    """

    def is_struct(self) -> bool:
        return False

    def has_child(self, name: str) -> bool:
        return False

    def add_child(self, member: "A_Member") -> bool:
        return False

    def remove_child(self, item: str | "A_Member") -> None:
        pass

    def get_child(self, name: str) -> Optional["A_Member"]:
        return None

    def get_children(self, includeArrays: bool = True) -> Iterable["A_Member"]:
        return []

    def get_data_size(self) -> int:
        size = self._type.get_size()
        if size is None:
            return 0
        return size

    def load(self, stream: BinaryIO, endPos: Optional[int] = None) -> None:
        if endPos is None:
            endPos = 1 << 30 # 1 GB
        for i in range(self.get_array_size()):
            if stream.tell() >= endPos:
                break
            self[i]._value = TEMPLATE_TYPE_READ_TABLE[self._type](stream)

    def save(self, stream: BinaryIO) -> None:
        for i in range(self.get_array_size()):
            if i > len(self._arrayInstances):
                break
            TEMPLATE_TYPE_WRITE_TABLE[self._type](stream, self[i]._value)

    def copy(self, *, deep: bool = False) -> "MemberValue":
        cls = self.__class__
        _copy = cls(self._name, self._value, self._type)
        _copy._arraySize = self._arraySize
        _copy._readOnly = self._readOnly
        if not deep:
            _copy._arrayInstances = self._arrayInstances.copy()
        return _copy


class MemberEnum(MemberValue):
    """
    Class describing an Enum bound member
    """
    def __init__(self, name: str, value: Any, type: ValueType, *, readOnly: bool = False, enumInfo: TemplateEnumType) -> None:
        super().__init__(name, value, type, readOnly=readOnly)
        self._enumInfo = enumInfo
        self._enumFlags: dict[str, bool] = {}
        self.__update_enum()

    def set_value(self, value: Any):
        super().set_value(value)
        self.__update_enum()

    def get_enum_info(self) -> dict[str, Any]:
        return self._enumInfo

    def get_enum_flags(self) -> dict[str, bool]:
        return self._enumFlags

    def set_enum_flag(self, enum: str, on: bool):
        self._enumFlags[enum] = on
        if on:
            self._value |= self._enumInfo[enum]
        else:
            self._value &= self._enumInfo[enum]

    def copy(self, *, deep: bool = False) -> "MemberEnum":
        _copy: "MemberEnum" = super().copy(deep=deep)
        _copy._enumInfo = self._enumInfo
        _copy._enumFlags = self._enumFlags
        return _copy

    def __update_enum(self):
        for key, value in self._enumInfo["Flags"].items():
            self._enumFlags[key] = (self.get_value() & value) != 0


class MemberStruct(A_Member):
    """
    Class describing a member structure
    """

    def __init__(self, name: str):
        super().__init__(name, None, ValueType.STRUCT)
        self._children: Dict[str, A_Member] = {}

    def is_struct(self) -> bool:
        return True

    def has_child(self, name: str) -> bool:
        for child in self._children.values():
            for _ in range(child.get_array_size()):
                if child.get_formatted_name() == name:
                    return True

        return False

    def add_child(self, member: "A_Member") -> bool:
        fmtName = member.get_formatted_name()
        if self.has_child(fmtName):
            return False

        self._children[fmtName] = member
        member.set_parent(self)
        return True

    def remove_child(self, item: str | "A_Member") -> None:
        if isinstance(item, str):
            child = self._children.pop(item)
        else:
            child = self._children.pop(item.get_formatted_name())
        child._parent = None

    def get_child(self, name: str) -> Optional["A_Member"]:
        if name in self._children:
            return self._children[name]
        return None

    def get_children(self, includeArrays: bool = True) -> Iterable["A_Member"]:
        for child in self._children.values():
            for i in range(child.get_array_size()):
                if i == 0 or includeArrays:
                    yield child[i]

    def get_data_size(self) -> int:
        return sum([member.get_data_size() for member in self.get_children()])

    def load(self, stream: BinaryIO, endPos: Optional[int] = None) -> None:
        if endPos is None:
            endPos = 1 << 30 # 1 GB
        for i in range(self.get_array_size()):
            if stream.tell() >= endPos:
                break
            for member in self[i].get_children(includeArrays=False):
                member.load(stream, endPos)

    def save(self, stream: BinaryIO) -> None:
        for i in range(self.get_array_size()):
            if i > len(self._arrayInstances):
                break
            for member in self[i].get_children(includeArrays=False):
                member.save(stream)

    def copy(self, *, deep: bool = False) -> "MemberStruct":
        cls = self.__class__
        _copy = cls(self._name)
        _copy._arraySize = self._arraySize
        _copy._readOnly = self._readOnly
        if not deep:
            _copy._arrayInstances = self._arrayInstances.copy()
        for name, child in self._children.items():
            if deep:
                _copy.add_child(child.copy(deep=True))
            else:
                _copy.add_child(child)
        return _copy


class MemberComment(MemberValue):
    """
    Class describing a member comment
    """

    def __init__(self, name: str, value: Any):
        super().__init__(name, value, ValueType.STRUCT)

    def is_read_only(self) -> bool:
        return True

    def get_data_size(self) -> int:
        return 0

    def load(self, stream: BinaryIO, endPos: Optional[int] = None) -> None:
        pass

    def save(self, stream: BinaryIO) -> None:
        pass
