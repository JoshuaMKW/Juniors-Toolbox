import json
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable, Union

from sms_bin_editor.utils.iohelper import (read_bool, read_double, read_float,
                                           read_sbyte, read_sint16,
                                           read_sint32, read_string,
                                           read_ubyte, read_uint16,
                                           read_uint32, write_bool,
                                           write_double, write_float,
                                           write_sbyte, write_sint16,
                                           write_sint32, write_string,
                                           write_ubyte, write_uint16,
                                           write_uint32)


class AttributeType(str, Enum):
    BOOL = "BOOL"
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
    STRING = "STRING"
    COMMENT = "COMMENT"


TEMPLATE_TYPE_READ_TABLE = {
    AttributeType.BOOL: read_bool,
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
    AttributeType.STRING: read_string,
    AttributeType.COMMENT: lambda f: None
}


TEMPLATE_TYPE_WRITE_TABLE = {
    AttributeType.BOOL: write_bool,
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
    AttributeType.STRING: write_string,
    AttributeType.COMMENT: lambda f, val: None
}


@dataclass
class ObjectAttribute():
    name: str
    type: AttributeType
    comment: str = ""

    def __str__(self):
        if self.type == AttributeType.COMMENT:
            return f"{self.name} {self.type.upper()} {self.comment}"
        return f"{self.name} {self.type.upper()}"

    def read_from(self, f: BinaryIO) -> Union[int, float, str, bytes]:
        return TEMPLATE_TYPE_READ_TABLE[self.type](f)

    def write_to(self, f: BinaryIO, data: Union[int, float, str, bytes]):
        TEMPLATE_TYPE_WRITE_TABLE[self.type](f, data)


class ObjectTemplate(list):
    """
    Template representing the layout of object parameters in a bin
    """
    TEMPLATE_PATH = Path("Templates")

    def __init__(self, __iterable: Iterable[ObjectAttribute] = None):
        super().__init__(__iterable)
        self.name = ""

    @classmethod
    def from_template(cls, file: Path) -> "ObjectTemplate":
        if not file.is_file():
            return None

        this = cls()
        with file.open("r") as f:
            for i, entry in enumerate(f.readlines()):
                if i > 0:
                    info = entry.split()
                    if len(info) > 2:
                        this.append(ObjectAttribute(
                            info[0], AttributeType(info[1]), info[2]))
                    else:
                        this.append(ObjectAttribute(info[0], info[1]))
                else:
                    this.name = entry.strip()
        return this

    def to_template(self, file: Path):
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w") as f:
            for attribute in self:
                f.write(f"{attribute}\n")

    def iter_data(self, data: BinaryIO) -> Iterable[ObjectAttribute]:
        """
        Iterate through raw data, setting attributes and yielding them
        """
        for attribute in self:
            attribute.read_from(data)
            yield attribute

    def copy(self) -> "ObjectTemplate":
        new = ObjectTemplate(self)
        new.name = self.name
        return new