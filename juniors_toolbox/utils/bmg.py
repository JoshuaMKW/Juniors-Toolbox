from dataclasses import dataclass, field
from enum import Enum, IntEnum
from io import BytesIO
from pathlib import Path
import struct
from typing import Iterable, List, Tuple, Union

from juniors_toolbox.utils.iohelper import align_int, read_string, read_ubyte, read_uint16, read_uint32
from juniors_toolbox.utils.j3d import data


@dataclass
class RichMessage:
    components: list = field(default_factory=lambda: [])

    def get_string(self) -> str:
        string = ""
        for cmp in self.components:
            if isinstance(cmp, str):
                string += cmp
        return string

    @classmethod
    def from_bytes(cls, f: BytesIO, encoding: str = "latin-1") -> "BMG.RichMessage":
        string = b""
        components = []
        while (char := f.read(1)) != b"":
            if char == b"\x1A":
                if string != b"":
                    components.append(string.decode(encoding))
                    string = b""

                subChar = f.read(1)
                flags = f.read(3)
                if flags[:2] == b"\x01\x00":  # text choices
                    components.append(
                        char + subChar + flags + f.read(
                            int.from_bytes(subChar, "big", signed=False) - 5
                        ))
                elif subChar == b"\x06":
                    components.append(
                        char + subChar + flags + f.read(1)
                    )
                elif subChar == b"\x05":
                    components.append(
                        char + subChar + flags
                    )
                else:
                    raise ValueError(
                        f"Unknown escape code {char + subChar + flags[:2]}")
            else:
                string += char
        if string != b"":
            components.append(string.decode(encoding))
        print(components)
        return cls(components)

    def to_bytes(self) -> bytes:
        ...


class BMG():
    """
    Class representing the Nintendo Binary Message Format
    """

    class EscapeCode:
        def __init__(self, escape: int):
            self.escapeCode = escape

    class Encoding(str, Enum):
        SHIFT_JIS = "shift-jis"
        LATIN_1 = "latin-1"

    class SoundID(IntEnum):
        ...

    @dataclass
    class MessageEntry:
        name: str
        message: RichMessage
        soundID: int
        startFrame: int
        endFrame: int

        def __str__(self) -> str:
            return f"{self.name} :: {self.message.get_string()}"

    MAGIC = b"MESGbmg1"

    def __init__(self, isPal: bool, flagSize: int):
        self.flagSize = flagSize

        self.__messages: List[BMG.MessageEntry] = []
        self.__encoding = BMG.Encoding.SHIFT_JIS
        self.__isPal = isPal

    @staticmethod
    def is_data_pal(f: BytesIO) -> bool:
        if f.read(8) != BMG.MAGIC:
            return False

        f.seek(4, 1)
        isPal = read_uint32(f) == 3
        f.seek(-0x10)
        return isPal

    @classmethod
    def from_bytes(cls, f: BytesIO):
        assert f.read(8) == BMG.MAGIC, "File is invalid!"

        size = read_uint32(f)
        sectionNum = read_uint32(f)
        isPal = sectionNum == 3
        if read_uint32(f) == 0x03000000:
            encoding = BMG.Encoding.SHIFT_JIS
        else:
            encoding = BMG.Encoding.LATIN_1

        f.seek(12, 1)  # Padding

        for i in range(sectionNum):
            f.seek(align_int(f.tell(), 32))  # 32 bit section alignment
            sectionMagic = f.read(4)
            sectionSize = read_uint32(f)
            if sectionMagic == b"INF1":
                assert i == 0, f"INF1 found at incorrect section index {i}!"
                messageNum = read_uint16(f)
                packetSize = read_uint16(f)
                f.seek(4, 1) # unknown values

                dataOffsets = []
                strIDOffsets = []
                messageMetaDatas = []
                messages = []
                names = []
                if packetSize == 12:
                    for i in range(messageNum):
                        dataOffsets.append(read_uint32(f))
                        fStart = read_uint16(f)
                        fEnd = read_uint16(f)
                        if isPal:
                            print(hex(f.tell()))
                            strIDOffsets.append(read_uint16(f))
                        soundID = read_ubyte(f)  # BMG.SoundID(read_ubyte(f))
                        messageMetaDatas.append([fStart, fEnd, soundID])
                        f.seek(1 if isPal else 3, 1)
                elif packetSize == 8:
                    raise NotImplementedError("PacketSize 8 not implemented")
                elif packetSize == 4:
                    raise NotImplementedError("PacketSize 4 not implemented")
                else:
                    raise NotImplementedError("PacketSize unknown")
            elif sectionMagic == b"DAT1":
                assert i > 0, f"DAT1 found before INF1!"
                data = f.read(sectionSize - 8)
                for i, offset in enumerate(dataOffsets):
                    if i < len(dataOffsets) - 1:
                        rawMsg = data[offset:dataOffsets[i+1]]
                    else:
                        rawMsg = data[offset:]
                    messages.append(
                        RichMessage.from_bytes(BytesIO(rawMsg), encoding.value)
                    )
            elif sectionMagic == b"STR1":
                assert i > 0, f"STR1 found before INF1!"
                relOfs = f.tell()
                for i, offset in enumerate(strIDOffsets):
                    names.append(read_string(f, offset+relOfs, encoding=encoding.value))


        bmg = cls(isPal, packetSize)
        bmg.encoding = encoding

        for i in range(len(messages)):
            bmg.add_message(
                BMG.MessageEntry(
                    names[i] if isPal else "",
                    messages[i],
                    messageMetaDatas[i][2],
                    messageMetaDatas[i][0],
                    messageMetaDatas[i][1]
                )
            )

        for message in bmg.iter_messages():
            print(message)

    def to_bytes(self, isPal: bool) -> bytes:
        stream = BytesIO(b"\x00" * self.data_size())
        for msg in self.__messages:
            ...

    @property
    def dataSize(self) -> int:
        size = 0x30 if self.__isPal else 0x28
        for msg in self.__messages:
            size += self.flagSize
            if self.__isPal:
                size += len(msg.name)
            size += len(msg.message)
        return align_int(size, 32)

    @property
    def encoding(self) -> Encoding:
        return self.__encoding

    @encoding.setter
    def encoding(self, encoding: Encoding):
        self.__encoding = encoding

    def is_pal(self) -> bool:
        return self.__isPal

    def add_message(self, message: MessageEntry):
        self.__messages.append(message)

    def remove_message(self, message: MessageEntry):
        self.__messages.remove(message)

    def get_message(self, _id: Union[str, int]):
        if isinstance(_id, int):
            if _id >= len(self.__messages):
                return None
            return self.__messages[_id]
        for msg in self.__messages:
            if _id == msg.name:
                return msg

    def iter_messages(self) -> Iterable[MessageEntry]:
        for msg in self.__messages:
            yield msg

    def __len__(self) -> int:
        return len(self.__messages)
