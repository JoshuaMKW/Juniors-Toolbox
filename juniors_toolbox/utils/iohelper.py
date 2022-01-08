import struct
from typing import BinaryIO, List, Optional, Union

from chardet import UniversalDetector


def read_sbyte(f: BinaryIO):
    return struct.unpack("b", f.read(1))[0]


def write_sbyte(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">b"
    if isinstance(val, list):
        tag = ">" + ("b"*len(val))
    f.write(struct.pack(tag, val))


def read_sint16(f: BinaryIO):
    return struct.unpack(">h", f.read(2))[0]


def write_sint16(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">h"
    if isinstance(val, list):
        tag = ">" + ("h"*len(val))
    f.write(struct.pack(tag, val))


def read_sint32(f: BinaryIO):
    return struct.unpack(">i", f.read(4))[0]


def write_sint32(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">i"
    if isinstance(val, list):
        tag = ">" + ("i"*len(val))
    f.write(struct.pack(tag, val))


def read_ubyte(f: BinaryIO):
    return struct.unpack("B", f.read(1))[0]


def write_ubyte(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">B"
    if isinstance(val, list):
        tag = ">" + ("B"*len(val))
    f.write(struct.pack(tag, val))


def read_uint16(f: BinaryIO):
    return struct.unpack(">H", f.read(2))[0]


def write_uint16(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">H"
    if isinstance(val, list):
        tag = ">" + ("H"*len(val))
    f.write(struct.pack(tag, val))


def read_uint32(f: BinaryIO):
    return struct.unpack(">I", f.read(4))[0]


def write_uint32(f: BinaryIO, val: Union[int, List[int]]):
    tag = ">I"
    if isinstance(val, list):
        tag = ">" + ("I"*len(val))
    f.write(struct.pack(tag, val))


def read_float(f: BinaryIO):
    return struct.unpack(">f", f.read(4))[0]


def write_float(f: BinaryIO, val: Union[float, List[float]]):
    tag = ">f"
    if isinstance(val, list):
        tag = ">" + ("f"*len(val))
    f.write(struct.pack(tag, val))


def read_double(f: BinaryIO):
    return struct.unpack(">d", f.read(4))[0]


def write_double(f: BinaryIO, val: Union[float, List[float]]):
    tag = ">d"
    if isinstance(val, list):
        tag = ">" + ("d"*len(val))
    f.write(struct.pack(tag, val))


def read_vec3f(f: BinaryIO):
    return struct.unpack(">fff", f.read(12))


def write_vec3f(f: BinaryIO, val: list):
    f.write(struct.pack(">fff", val))


def read_bool(f: BinaryIO, vSize: int = 1):
    return struct.unpack(">?", f.read(vSize))[0] > 0


def write_bool(f: BinaryIO, val: bool, vSize: int = 1):
    if val is True:
        f.write(b'\x00'*(vSize-1) + b'\x01')
    else:
        f.write(b'\x00' * vSize)


def read_string(
    f: BinaryIO,
    offset: Optional[int] = None,
    maxlen: Optional[int] = None,
    encoding: Optional[str] = None
) -> str:
    """ Reads a null terminated string from the specified address """
    if offset is not None:
        f.seek(offset)

    if maxlen is None:
        maxlen = 0

    length = 0
    binary = f.read(1)
    while binary[-1]:
        if length >= maxlen > 0:
            break
        binary += f.read(1)
        length += 1
    else:
        binary = binary[:-1]

    if encoding is None:
        encoder = UniversalDetector()
        encoder.feed(binary)
        encoding = encoder.close()["encoding"]

    try:
        if not encoding or encoding.lower() not in {"ascii", "utf-8", "shift-jis", "iso-8859-1"}:
            encoding = "shift-jis"
        return binary.decode(encoding)
    except UnicodeDecodeError:
        return ""


def write_string(f: BinaryIO, val: str):
    f.write(val.encode())


def align_int(num: int, alignment: int) -> int:
    return (num + (alignment - 1)) & -alignment