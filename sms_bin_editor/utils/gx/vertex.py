from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Any, BinaryIO, List, Tuple, Union

from sms_bin_editor.utils.iohelper import (read_float, read_sbyte, read_sint16,
                                           read_ubyte, read_uint16,
                                           write_sbyte, write_sint16,
                                           write_ubyte, write_uint16)
from sms_bin_editor.utils.gx.color import Color

import glm


@dataclass
class VertexComponentCount:
    class Position(IntEnum):
        XY = 0
        XYZ = auto()

    class Normal(IntEnum):
        XYZ = 0
        NBT = auto()  # Index NBT triplets
        NBT3 = auto()  # index N/B/T individually

    class Color(IntEnum):
        RGB = 0
        RGBA = auto()

    class TextureCoordinate(IntEnum):
        S = 0
        ST = auto()
        U = S
        UV = ST

    item: Union[Position, Normal, Color, TextureCoordinate]


@dataclass
class VertexBufferType:
    class Generic(IntEnum):
        U8 = 0
        S8 = auto()
        U16 = auto()
        S16 = auto()
        F32 = auto()

    class Color(IntEnum):
        RGB565 = 0
        RGB8 = auto()  # 8 bit, no alpha
        RGBX8 = auto()  # 8 bit, alpha discarded
        RGBA4 = auto()  # 4 bit
        RGBA6 = auto()  # 6 bit
        RGBA8 = auto()  # 8 bit

        FMT_16B_565 = RGB565
        FMT_24B_888 = RGB8
        FMT_32B_888X = RGBX8
        FMT_16B_4444 = RGBA4
        FMT_24B_6666 = RGBA6
        FMT_32B_8888 = RGBA8

    item: Union[Generic, Color]


class VertexAttribute(IntEnum):
    POSITIONNORMALMATRIXINDEX = 0
    TEXTURE0MATRIXINDEX = auto()
    TEXTURE1MATRIXINDEX = auto()
    TEXTURE2MATRIXINDEX = auto()
    TEXTURE3MATRIXINDEX = auto()
    TEXTURE4MATRIXINDEX = auto()
    TEXTURE5MATRIXINDEX = auto()
    TEXTURE6MATRIXINDEX = auto()
    TEXTURE7MATRIXINDEX = auto()
    POSITION = auto()
    NORMAL = auto()
    COLOR0 = auto()
    COLOR1 = auto()
    TEXCOORD0 = auto()
    TEXCOORD1 = auto()
    TEXCOORD2 = auto()
    TEXCOORD3 = auto()
    TEXCOORD4 = auto()
    TEXCOORD5 = auto()
    TEXCOORD6 = auto()
    TEXCOORD7 = auto()

    POSITIONMATRIXARRAY = auto()
    NORMALMATRIXARRAY = auto()
    TEXTUREMATRIXARRAY = auto()
    LIGHTARRAY = auto()
    NORMALBINORMALTANGENT = auto()
    MAX = auto()

    UNDEFINED = 0xFF - 1
    TERMINATE = 0xFF


class VertexBufferAttribute(IntEnum):
    POSITION = 9
    NORMAL = auto()
    COLOR0 = auto()
    COLOR1 = auto()
    TEXCOORD0 = auto()
    TEXCOORD1 = auto()
    TEXCOORD2 = auto()
    TEXCOORD3 = auto()
    TEXCOORD4 = auto()
    TEXCOORD5 = auto()
    TEXCOORD6 = auto()
    TEXCOORD7 = auto()

    NORMALBINORMALTANGENT = 25
    MAX = auto()

    UNDEFINED = 0xFF - 1
    TERMINATE = 0xFF

    def __init__(self, value: int):
        super().__init__(value)
        assert(value < VertexBufferAttribute.MAX)


class VertexAttributeType(IntEnum):
    NONE = 0        # No data will be sent
    DIRECT = auto()  # Data will be sent directly
    BYTE = auto()   # 8-bit indices
    SHORT = auto()  # 16-bit indices


class PrimitiveType(IntEnum):
    QUADS = auto()         # 0x80
    QUADS2 = auto()        # 0x88
    TRIANGLES = auto()     # 0x90
    TRIANGLESTRIP = auto()  # 0x98
    TRIANGLEFAN = auto()   # 0xA0
    LINES = auto()         # 0xA8
    LINESTRIP = auto()     # 0xB0
    POINTS = auto()        # 0xB8
    MAX = auto()


PRIMITIVE_MASK = 0x78
PRIMITIVE_SHIFT = 3


def encode_draw_primitive_command(_type: PrimitiveType) -> int:
    return 0x80 | ((_type.value << PRIMITIVE_SHIFT) & PRIMITIVE_MASK)


def decode_draw_primitive_command(_cmd: int) -> PrimitiveType:
    return PrimitiveType((_cmd & PRIMITIVE_MASK) >> PRIMITIVE_SHIFT)


class VertexBufferKind(IntEnum):
    POSITION = 0
    NORMAL = auto()
    COLOR = auto()
    TEXCOORD = auto()


def compute_component_count(kind: VertexBufferKind, count: VertexComponentCount) -> int:
    if kind == VertexBufferKind.POSITION:
        return count.item + 2
    if kind == VertexBufferKind.NORMAL:
        return 3
    if kind == VertexBufferKind.COLOR:
        return count.item + 3
    if kind == VertexBufferKind.TEXCOORD:
        return count.item + 1
    raise ValueError("Invalid component count!")


def read_generic_component_single(
    reader: BinaryIO,
    _type: VertexBufferType.Generic,
    divisor: int = 0
) -> float:
    if _type == VertexBufferType.Generic.U8:
        return float(read_ubyte(reader)) / float(1 << divisor)
    if _type == VertexBufferType.Generic.S8:
        return float(read_sbyte(reader)) / float(1 << divisor)
    if _type == VertexBufferType.Generic.U16:
        return float(read_uint16(reader)) / float(1 << divisor)
    if _type == VertexBufferType.Generic.S16:
        return float(read_sint16(reader)) / float(1 << divisor)
    if _type == VertexBufferType.Generic.F32:
        return read_float(reader) / float(1 << divisor)
    return 0.0


def read_color_components(reader: BinaryIO, _type: VertexBufferType.Color) -> Color:
    result = Color(0, 0, 0, 0)

    if _type == VertexBufferType.Color.RGB565:
        color = read_uint16(reader)
        result.red = float((color & 0xF800) >> 11) * (255.0 / 31.0)
        result.green = float((color & 0x07E0) >> 5) * (255.0 / 63.0)
        result.blue = float(color & 0x001F) * (255.0 / 31.0)
    elif _type == VertexBufferType.Color.RGB8:
        result.red = read_ubyte(reader)
        result.green = read_ubyte(reader)
        result.blue = read_ubyte(reader)
    elif _type == VertexBufferType.Color.RGBX8:
        result.red = read_ubyte(reader)
        result.green = read_ubyte(reader)
        result.blue = read_ubyte(reader)
        reader.seek(1, 1)
    elif _type == VertexBufferType.Color.RGBA4:
        color = read_uint16(reader)
        result.red = ((color & 0xF000) >> 12) * 17
        result.green = ((color & 0x0F00) >> 8) * 17
        result.blue = ((color & 0x00F0) >> 4) * 17
        result.alpha = (color & 0x000F) * 17
    elif _type == VertexBufferType.Color.RGBA6:
        color = int.from_bytes(reader.read(3), "big", signed=False)
        result.red = float((color & 0xFC0000) >> 18) * (255.0 / 63.0)
        result.green = float((color & 0x03F000) >> 12) * (255.0 / 63.0)
        result.blue = float((color & 0x000FC0) >> 6) * (255.0 / 63.0)
        result.alpha = float(color & 0x00003F) * (255.0 / 63.0)
    elif _type == VertexBufferType.Color.RGBA8:
        result.red = read_ubyte(reader)
        result.green = read_ubyte(reader)
        result.blue = read_ubyte(reader)
        result.alpha = read_ubyte(reader)

    return result


def read_generic_components(
    reader: BinaryIO,
    _type: VertexBufferType.Generic,
    trueCount: int,
    divisor: int = 0
) -> List[float]:
    assert 0 < trueCount < 4, "True count is out of range! (1 - 3)"

    out = []
    for _ in range(trueCount):
        out.append(read_generic_component_single(reader, _type, divisor))
    return out


def read_components(
    reader: BinaryIO,
    _type: VertexBufferType,
    trueCount: int,
    divisor: int = 0
) -> List[float]:
    return read_generic_components(reader, _type.item, trueCount, divisor)


def write_color_components(writer: BinaryIO, color: Color, _type: VertexBufferType.Color):
    if _type == VertexBufferType.Color.RGB565:
        write_uint16(((color.red & 0xF8) << 8) | (
            (color.green & 0xFC) << 3) | ((color.blue & 0xF8) >> 3))
    elif _type == VertexBufferType.Color.RGB8:
        write_ubyte(writer, color.red)
        write_ubyte(writer, color.green)
        write_ubyte(writer, color.blue)
    elif _type == VertexBufferType.Color.RGBX8:
        write_ubyte(writer, color.red)
        write_ubyte(writer, color.green)
        write_ubyte(writer, color.blue)
        writer.write(b"\x00")
    elif _type == VertexBufferType.Color.RGBA4:
        write_uint16(((color.red & 0xF0) << 8) | (
            (color.green & 0xF0) << 4) | (color.blue & 0xF0) | ((color.alpha & 0xF0) >> 4))
    elif _type == VertexBufferType.Color.RGBA6:
        value = (((color.red & 0xFC) << 16) | (
            (color.green & 0xFC) << 10) | ((color.blue & 0xFC) << 4) | ((color.alpha & 0xFC) >> 2))
        writer.write(value.to_bytes(3, "big", signed=False))
    elif _type == VertexBufferType.Color.RGBA8:
        write_ubyte(writer, color.red)
        write_ubyte(writer, color.green)
        write_ubyte(writer, color.blue)
        write_ubyte(writer, color.alpha)
    else:
        raise ValueError("Invalid buffer type!")


def write_generic_components(
    writer: BinaryIO,
    components: Tuple[int, object, glm]
)


def writeComponents(
    writer: BinaryIO,
    d: 
)
