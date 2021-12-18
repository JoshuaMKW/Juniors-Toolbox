import json
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import (BinaryIO, Dict, Iterable, Iterator, List, TextIO, Tuple,
                    Union)

from sms_bin_editor.utils.iohelper import (read_bool, read_double, read_float,
                                           read_sbyte, read_sint16,
                                           read_sint32, read_string,
                                           read_ubyte, read_uint16,
                                           read_uint32, read_vec3f, write_bool,
                                           write_double, write_float,
                                           write_sbyte, write_sint16,
                                           write_sint32, write_string,
                                           write_ubyte, write_uint16,
                                           write_uint32, write_vec3f)

from sms_bin_editor.objects.types import RGBA, Vec3f


class AttributeInvalidError(Exception):
    ...


class AttributeType(str, Enum):
    BOOL = "BOOL"
    BYTE = "BYTE"
    CHAR = "CHAR"
    S8 = "S8"
    U8 = "U8"
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
    RGBA = "RGBA"
    C_RGBA = "COLORRGBA"
    VECTOR3 = "VEC3F"
    COMMENT = "COMMENT"
    TEMPLATE = "TEMPLATE"

    __ENUM_TO_TYPE_TABLE = {
        BOOL: bool,
        BYTE: int,
        CHAR: int,
        S8: int,
        U8: int,
        S16: int,
        U16: int,
        S32: int,
        INT: int,
        U32: int,
        F32: float,
        FLOAT: float,
        F64: float,
        DOUBLE: float,
        STR: str,
        STRING: str,
        RGBA: RGBA,
        C_RGBA: RGBA,
        VECTOR3: Vec3f,
        COMMENT: str,
        TEMPLATE: None
    }

    __ENUM_TO_SIZE_TABLE = {
        BOOL: 1,
        BYTE: 1,
        CHAR: 1,
        S8: 1,
        U8: 1,
        S16: 2,
        U16: 2,
        S32: 4,
        INT: 4,
        U32: 4,
        F32: 4,
        FLOAT: 4,
        F64: 8,
        DOUBLE: 8,
        STR: None,
        STRING: None,
        RGBA: 4,
        VECTOR3: 12,
        COMMENT: None,
        TEMPLATE: None
    }

    @staticmethod
    def type_to_enum(_ty: type):
        """
        Convert a type to the Enum equivalent
        """
        return AttributeType(_ty.__name__.upper())

    def enum_to_type(self) -> type:
        """
        Convert this to a type
        """
        return self.__ENUM_TO_TYPE_TABLE[self]

    def get_size(self) -> int:
        """
        Return the physical size of the data type
        """
        return self.__ENUM_TO_SIZE_TABLE[self]


def __read_bin_string(f: BinaryIO) -> str:
    len = read_uint16(f)
    if len == 0:
        return ""
    return read_string(f, maxlen=len-1)


def __write_bin_string(f: BinaryIO, val: str):
    raw = val.encode()
    write_uint16(f, len(raw))
    f.write(raw)


TEMPLATE_TYPE_READ_TABLE = {
    AttributeType.BOOL: read_bool,
    AttributeType.BYTE: read_ubyte,
    AttributeType.CHAR: read_ubyte,
    AttributeType.S8: read_sbyte,
    AttributeType.U8: read_ubyte,
    AttributeType.S16: read_sint16,
    AttributeType.U16: read_uint16,
    AttributeType.S32: read_sint32,
    AttributeType.INT: read_sint32,
    AttributeType.U32: read_uint32,
    AttributeType.F32: read_float,
    AttributeType.FLOAT: read_float,
    AttributeType.F64: read_double,
    AttributeType.DOUBLE: read_double,
    AttributeType.STR: __read_bin_string,
    AttributeType.STRING: __read_bin_string,
    AttributeType.RGBA: lambda f: RGBA(read_uint32(f)),
    AttributeType.C_RGBA: lambda f: RGBA(read_uint32(f)),
    AttributeType.VECTOR3: lambda f: Vec3f(*read_vec3f(f)),
    AttributeType.COMMENT: lambda f: None,
    AttributeType.TEMPLATE: lambda f: None
}


TEMPLATE_TYPE_WRITE_TABLE = {
    AttributeType.BOOL: write_bool,
    AttributeType.BYTE: write_ubyte,
    AttributeType.CHAR: write_ubyte,
    AttributeType.S8: write_sbyte,
    AttributeType.U8: write_ubyte,
    AttributeType.S16: write_sint16,
    AttributeType.U16: write_uint16,
    AttributeType.S32: write_sint32,
    AttributeType.INT: write_sint32,
    AttributeType.U32: write_uint32,
    AttributeType.F32: write_float,
    AttributeType.FLOAT: write_float,
    AttributeType.F64: write_double,
    AttributeType.DOUBLE: write_double,
    AttributeType.STR: __write_bin_string,
    AttributeType.STRING: __write_bin_string,
    AttributeType.RGBA: write_uint32,
    AttributeType.C_RGBA: write_uint32,
    AttributeType.VECTOR3: write_vec3f,
    AttributeType.COMMENT: lambda f, val: None,
    AttributeType.TEMPLATE: lambda f, val: None
}


@dataclass
class ObjectAttribute():
    """
    Class representing a single attribute in an object template
    """
    name: str
    type: AttributeType
    comment: str = ""
    countRef: Union["ObjectAttribute", int] = 1

    # -- TEMPLATE SPECIFIC -- #
    _subattrs: List["ObjectAttribute"] = field(default_factory=lambda: [])

    @staticmethod
    def get_formatted_name(name: str, char: str, num: int) -> str:
        """
        Get this attribute's name formatted
        """
        templateName = name.replace("{c}", char[0])
        templateName = templateName.replace("{C}", char[0].upper())
        templateName = templateName.replace("{i}", str(num))
        return templateName

    def is_struct(self) -> bool:
        """
        Return if this attribute is a struct type
        """
        return self.type == AttributeType.TEMPLATE

    def is_count_referenced(self) -> bool:
        """
        Return if this attribute's count is referenced from another object attribute
        """
        return isinstance(self.countRef, ObjectAttribute)

    def get_attribute(self, name: str) -> "ObjectAttribute":
        if not self.is_struct():
            raise AttributeInvalidError(
                "Can't get attributes of a non struct!")
        for attribute in self._subattrs:
            if attribute.name == name:
                return attribute

    def add_attribute(self, attribute: "ObjectAttribute") -> bool:
        if not self.is_struct():
            raise AttributeInvalidError(
                "Can't add attributes of a non struct!")
        if attribute in self:
            return False
        self._subattrs.append(attribute)
        return True

    def remove_attribute(self, name: str) -> bool:
        if not self.is_struct():
            raise AttributeInvalidError(
                "Can't remove attributes of a non struct!")
        for attribute in self._subattrs:
            if attribute.name == name:
                self._subattrs.remove(attribute)
                return True
        return False

    def iter_attributes(self) -> Iterable["ObjectAttribute"]:
        """
        Iterate through the object attributes of thie object template
        """
        if not self.is_struct():
            raise AttributeInvalidError(
                "Can't iterate on attributes of a non struct!")
        for attribute in self._subattrs:
            yield attribute

    def get_size(self) -> int:
        """
        Return the data size of this object template, as represented by file structure
        """
        if self.is_struct():
            return sum([a.get_size() for a in self._subattrs])
        return self.type.get_size()

    def read_from(self, f: BinaryIO) -> Union[int, float, str, bytes, list, RGBA, Vec3f]:
        """
        Read data from a stream following the map of this template attribute
        """
        if self.is_struct():
            return [attr.read_from(f) for attr in self.iter_attributes()]
        return TEMPLATE_TYPE_READ_TABLE[self.type](f)

    def write_to(self, f: BinaryIO, data: Union[int, float, str, bytes, list, RGBA, Vec3f]):
        """
        Write data to a stream following the map of this template attribute
        """
        if self.is_struct():
            for v in data:
                ty = AttributeType.type_to_enum(v.__class__)
                TEMPLATE_TYPE_WRITE_TABLE[ty](f, v)
        else:
            TEMPLATE_TYPE_WRITE_TABLE[self.type](f, data)

    def __str__(self):
        if self.type == AttributeType.COMMENT:
            return f"{self.name} {self.type.upper()} {self.comment}"
        return f"{self.name} {self.type.upper()}" + f"[{self.countRef.name}]" if isinstance(self.countRef, ObjectAttribute) else F"[{self.countRef}]"

    def __contains__(self, attr: Union["ObjectAttribute", str]) -> bool:
        if isinstance(attr, ObjectAttribute):
            return attr in self._subattrs
        return any([a.name == attr for a in self._subattrs])


class ObjectTemplate():
    """
    Class representing a whole object template
    """
    TEMPLATE_PATH = Path("Templates")

    def __init__(self):
        self.name = ""
        self._attrs: List[ObjectAttribute] = []
        self._counts: Dict[str, int] = {}

        self.__eof = 0

    @classmethod
    def from_template(cls, file: Path) -> "ObjectTemplate":
        """
        Create an instance from a template file
        """
        if not file.is_file():
            return None

        this = cls()
        with file.open("r") as f:
            this.parse(f)

        return this

    def to_template(self, file: Path):
        """
        Create a template file from this instance
        """
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w") as f:
            for attribute in self:
                f.write(f"{attribute}\n")

    def get_attribute(self, name: str) -> ObjectAttribute:
        for attr in self._attrs:
            if attr.name == name:
                return attr

    def add_attribute(self, attribute: ObjectAttribute, index: int = -1):
        """
        Add an attribute to this object template
        """
        if index == -1:
            self._attrs.append(attribute)
        else:
            self._attrs.insert(index, attribute)

    def remove_attribute(self, attribute: Union[ObjectAttribute, str]) -> bool:
        """
        Remove an attribute from this object instance

        Returns True if successful
        """
        if not attribute in self:
            return False

        if isinstance(attribute, ObjectAttribute):
            self._attrs.remove(attribute)
        else:
            for attr in self._attrs:
                if attr.name == attribute:
                    self._attrs.remove(attr)
        return True

    def iter_attributes(self, deep: bool = False) -> Iterable[ObjectAttribute]:
        """
        Iterate through this object template's attributes

        `deep`: When true, also iterate through all subattributes of structs
        """
        for attribute in self._attrs:
            yield attribute
            if deep and attribute.is_struct():
                yield from attribute.iter_attributes()

    def get_count(self, attribute: Union[ObjectAttribute, str]) -> int:
        """
        Return the instance count this template has of an attribute
        """
        if isinstance(attribute, ObjectAttribute):
            attribute = attribute.name

        try:
            return self._counts[attribute]
        except KeyError:
            return 0

    def set_count(self, attribute: Union[ObjectAttribute, str], count: int) -> bool:
        """
        Set the instance count of an attribute, returns `True` if successful
        """
        if isinstance(attribute, ObjectAttribute):
            attribute = attribute.name

        if attribute in self:
            self._counts[attribute] = count
            return True
        return False

    def copy(self) -> "ObjectTemplate":
        """
        Return a copy of this template instance
        """
        new = ObjectTemplate(self)
        new.name = self.name
        return new

    # -- TEMPLATE PARSING -- #

    def parse(self, f: TextIO):
        """
        Fills this object template with the contents of a template file stream
        """
        oldpos = f.tell()
        f.seek(0, 2)
        self.__eof = f.tell()
        f.seek(oldpos, 0)

        self.name = f.readline().strip()
        while (entry := f.readline()) != "":
            attr = self.parse_attr(f, entry)
            if attr is None:
                continue
            self._attrs.append(attr)

    def parse_attr(self, f: TextIO, entry: str) -> ObjectAttribute:
        """
        Parse an attribute entry from an object template file
        """
        entry = entry.strip()
        if entry == "" or entry.startswith(("//", "#")):
            return None

        info = entry.split()

        name = info[0]
        attrtype = AttributeType(info[1])
        this = ObjectAttribute(name, attrtype)

        if len(info) >= 3:
            countRefName = info[2][1:-1]
            if countRefName.isnumeric():
                this.countRef = int(countRefName)
            elif countRefName == "*":
                this.countRef = -1
            else:
                for attribute in self._attrs:
                    if attribute.name == countRefName:
                        this.countRef = attribute
                        break
                    
        if attrtype == AttributeType.COMMENT:
            this.comment = info[2]
        elif attrtype == AttributeType.TEMPLATE:
            while (next := f.readline()).strip() != "}":
                if f.tell() >= self.__eof:
                    raise AttributeInvalidError(
                        "Parser found EOF during struct generation!")
                this._subattrs.append(self.parse_attr(f, next))

        return this

    def __len__(self) -> int:
        return len(self._attrs)

    def __contains__(self, attr: Union[ObjectAttribute, str]) -> bool:
        if isinstance(attr, ObjectAttribute):
            return attr in self._attrs
        return any([a.name == attr for a in self._attrs])
