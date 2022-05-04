
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, BinaryIO, Callable, Dict, Iterable, List, Optional, overload

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

    def __str__(self) -> str:
        return "::".join(self.__scopes)

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
    return read_string(f, maxlen=len-1)


def __write_bin_string(f: BinaryIO, val: str):
    raw = val.encode()
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
    write_vec3f(f, val.rotation)
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
    ValueType.C_RGB8: lambda f, val: write_ubyte(f, val.tuple()),  # val = RGB8
    ValueType.C_RGBA8: write_uint32,
    # val = RGB8
    ValueType.C_RGB32: lambda f, val: write_uint32(f, val.tuple()),
    ValueType.C_RGBA: write_uint32,
    ValueType.VECTOR3: write_vec3f,
    ValueType.TRANSFORM: __write_transform,
    ValueType.COMMENT: lambda f, val: None,
    ValueType.STRUCT: lambda f, val: None
}


@dataclass
class SimpleValue:
    """
    Class describing a value
    """
    name: str
    value: Any
    type: ValueType


class A_Member(SimpleValue, ABC):
    """
    Class describing a member of a structure
    """
    _parent: Optional["MemberStruct"] = None

    @staticmethod
    def get_formatted_template_name(name: str, char: str, num: int) -> str:
        """
        Get a template name formatted
        """
        templateName = name.replace("{c}", char[0])
        templateName = templateName.replace("{C}", char[0].upper())
        templateName = templateName.replace("{i}", str(num))
        return templateName

    def get_parent(self) -> Optional["MemberStruct"]:
        """
        Get the parent of this `Member`, which is a `Member` representing a struct
        """
        return self._parent

    def get_qualified_name(self) -> QualifiedName:
        """
        Get the full name of this `Member`, as is scoped from its parents
        """
        scopes = [self.name]
        parent = self.get_parent()
        while parent is not None:
            scopes.append(parent.name)
            parent = parent.get_parent()
        return QualifiedName(*scopes[::-1])

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
    def remove_child(self, member: str):
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
    def get_children(self) -> Iterable["A_Member"]:
        """
        Get all children from this `Member`, which implies this `Member` be a struct
        """
        ...

    @abstractmethod
    def get_data_size(self) -> int:
        """
        Get the raw data size of this member in bytes
        """
        ...

    @abstractmethod
    def load(self, stream: BinaryIO):
        """
        Read the data from `stream` into this member
        """
        ...

    @abstractmethod
    def save(self, stream: BinaryIO):
        """
        Write the value from this member into `stream`
        """
        ...

    @abstractmethod
    def as_template(self) -> str:
        """
        Return this member as a template skeleton
        """
        ...


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

    def remove_child(self, member: str) -> None:
        pass

    def get_child(self, name: str) -> Optional["A_Member"]:
        return None

    def get_children(self) -> Iterable["A_Member"]:
        return []

    def get_data_size(self) -> int:
        size = self.type.get_size()
        if size is None:
            return 0
        return size

    def load(self, stream: BinaryIO) -> None:
        self.value = TEMPLATE_TYPE_READ_TABLE[self.type](stream)

    def save(self, stream: BinaryIO) -> None:
        TEMPLATE_TYPE_WRITE_TABLE[self.type](stream, self.value)

    def as_template(self) -> str:
        return f"{self.name} {self.type.value}"


class MemberStruct(A_Member):
    """
    Class describing a member structure
    """
    _children: Dict[str, A_Member] = field(default_factory=lambda: {})
    
    def __init__(self, name: str, value: Any):
        super().__init__(name, value, ValueType.STRUCT)

    def is_struct(self) -> bool:
        return True

    def has_child(self, name: str) -> bool:
        return name in self._children

    def add_child(self, member: "A_Member") -> bool:
        if self.has_child(member.name):
            return False

        self._children[member.name] = member
        return True

    def remove_child(self, name: str) -> None:
        self._children.pop(name)

    def get_child(self, name: str) -> Optional["A_Member"]:
        if name in self._children:
            return self._children[name]
        return None

    def get_children(self) -> Iterable["A_Member"]:
        return self._children.values()

    def get_data_size(self) -> int:
        return sum([member.get_data_size() for member in self.get_children()])

    def load(self, stream: BinaryIO) -> None:
        self.value = [member.load(stream) for member in self.get_children()]

    def save(self, stream: BinaryIO) -> None:
        for member in self.get_children():
            value = member.value
            ty = ValueType.type_to_enum(value.__class__)
            TEMPLATE_TYPE_WRITE_TABLE[ty](stream, value)

    def as_template(self) -> str:
        header = f"{self.name} {self.type.value}"

        repeat = ""
        if self.value > 1:
            repeat = f" [{self.value}]"
        elif self.value == 0:
            repeat = " [*]"
        header += repeat + " {\n"

        body = ""
        for member in self.get_children():
            body += f"{member.as_template()}\n"

        return header + body + "}"


class MemberComment(MemberValue):
    """
    Class describing a member comment
    """
    def __init__(self, name: str, value: Any):
        super().__init__(name, value, ValueType.STRUCT)

    def get_data_size(self) -> int:
        return 0

    def load(self, stream: BinaryIO) -> None:
        pass

    def save(self, stream: BinaryIO) -> None:
        pass

    def as_template(self) -> str:
        return f"{self.name} {self.type.value} {self.value}"