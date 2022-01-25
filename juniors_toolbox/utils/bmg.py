from dataclasses import dataclass, field
from enum import Enum, IntEnum
from io import BytesIO
from os import write
from pathlib import Path
import struct
import sys
from typing import Iterable, List, Optional, Tuple, Union

from numpy import inf

from juniors_toolbox.utils.iohelper import align_int, decode_raw_string, get_likely_encoding, read_string, read_ubyte, read_uint16, read_uint32, write_string, write_ubyte, write_uint16, write_uint32


@dataclass
class RichMessage:
    components: list = field(default_factory=lambda: [])
    encoding: str = None

    _RICH_TO_COMMAND = {
        "{text:slow}":           b"\x1A\x05\x00\x00\x00",
        "{text:end_close}":      b"\x1A\x05\x00\x00\x01",
        "{ctx:bananas}":         b"\x1A\x06\x02\x00\x04\x00",
        "{ctx:coconuts}":        b"\x1A\x06\x02\x00\x04\x01",
        "{ctx:pineapples}":      b"\x1A\x06\x02\x00\x04\x02",
        "{ctx:durians}":         b"\x1A\x06\x02\x00\x04\x03",
        "{color:white}":         b"\x1A\x06\xFF\x00\x00\x00",
        "{color:red}":           b"\x1A\x06\xFF\x00\x00\x02",
        "{color:blue}":          b"\x1A\x06\xFF\x00\x00\x03",
        "{color:yellow}":        b"\x1A\x06\xFF\x00\x00\x04",
        "{color:green}":         b"\x1A\x06\xFF\x00\x00\x05",
        "{record:race_pianta}":  b"\x1A\x05\x02\x00\x00",
        "{record:race_gelato}":  b"\x1A\x05\x02\x00\x01",
        "{record:crate_time}":   b"\x1A\x05\x02\x00\x02",
        "{record:bcoin_shines}": b"\x1A\x05\x02\x00\x03",
        "{record:race_noki}":    b"\x1A\x05\x02\x00\x06",
    }

    _COMMAND_TO_RICH = {
        b"\x1A\x05\x00\x00\x00":     "{text:slow}",
        b"\x1A\x05\x00\x00\x01":     "{text:end_close}",
        b"\x1A\x06\x02\x00\x04\x00": "{ctx:bananas}",
        b"\x1A\x06\x02\x00\x04\x01": "{ctx:coconuts}",
        b"\x1A\x06\x02\x00\x04\x02": "{ctx:pineapples}",
        b"\x1A\x06\x02\x00\x04\x03": "{ctx:durians}",
        b"\x1A\x06\xFF\x00\x00\x00": "{color:white}",
        b"\x1A\x06\xFF\x00\x00\x02": "{color:red}",
        b"\x1A\x06\xFF\x00\x00\x03": "{color:blue}",
        b"\x1A\x06\xFF\x00\x00\x04": "{color:yellow}",
        b"\x1A\x06\xFF\x00\x00\x05": "{color:green}",
        b"\x1A\x05\x02\x00\x00":     "{record:race_pianta}",
        b"\x1A\x05\x02\x00\x01":     "{record:race_gelato}",
        b"\x1A\x05\x02\x00\x02":     "{record:crate_time}",
        b"\x1A\x05\x02\x00\x03":     "{record:bcoin_shines}",
        b"\x1A\x05\x02\x00\x06":     "{record:race_noki}",
    }

    @staticmethod
    def command_to_rich(cmd: bytes) -> str:
        if cmd in RichMessage._COMMAND_TO_RICH:
            return RichMessage._COMMAND_TO_RICH[cmd]

        if cmd.startswith(b"\x1A\x06\x00\x00\x00"):
            return "{speed:" + str(cmd[-1]) + "}"

        if cmd[2:4] == b"\x01\x00":
            return "{option:" + str(cmd[4]) + ":" + decode_raw_string(cmd[5:]) + "}"

    @staticmethod
    def rich_to_command(rich: str) -> bytes:
        if rich in RichMessage._RICH_TO_COMMAND:
            return RichMessage._RICH_TO_COMMAND[rich]

        if rich.startswith("{speed:"):
            rich = rich.replace(" ", "")
            speed = int(rich[7:-1])
            return b"\x1A\x06\x00\x00\x00" + speed.to_bytes(1, "big", signed=False)
            
        if rich.startswith("{option:"):
            command, message = rich.rsplit(":", 1)
            command.replace(" ", "")
            message = message[:-1].encode() + b"\x00"

            option = int(command[8:]).to_bytes(1, "big", signed=False)
            length = len(message).to_bytes(1, "big", signed=False)
            return b"\x1A" + length + b"\x01\x00" + option + message

    @classmethod
    def from_bytes(cls, f: BytesIO, encoding: Optional[str] = None):
        TERMINATING_CHARS = {b"", }

        string = b""
        components = []
        _encodingGuess = encoding
        _nullCount = 0
        while (char := f.read(1)) != b"":
            if char == b"\x00":
                _nullCount += 1
            else:
                _nullCount = 0

            if _nullCount > 1:
                break

            if char == b"\x1A":
                if string not in TERMINATING_CHARS:
                    if _encodingGuess is None:
                        _encodingGuess = get_likely_encoding(string)
                    components.append(decode_raw_string(string, encoding))
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
        if string not in TERMINATING_CHARS:
            if _encodingGuess is None:
                _encodingGuess = get_likely_encoding(string)
            components.append(decode_raw_string(string, encoding))
        return cls(components, _encodingGuess)

    @classmethod
    def from_rich_string(cls, string: str):
        components = []
        substr = ""
        lPos = string.find("{")
        rPos = string.find("}", lPos)
        encoding = None
        while lPos > -1 and rPos > -1:
            mainstr = string[:lPos]
            if mainstr != "":
                if encoding is None:
                    encoding = get_likely_encoding(mainstr.encode())
                components.append(mainstr)
            substr = string[lPos:rPos+1]
            if substr != "":
                part = RichMessage.rich_to_command(substr)
                if part is None:
                    part = substr
                components.append(part)
                string = string[rPos+1:]
                lPos = string.find("{")
                rPos = string.find("}", lPos)
        if string != "":
            if encoding is None:
                encoding = get_likely_encoding(string.encode())
            components.append(string+"\x00")
        return RichMessage(components, encoding)   

    def to_bytes(self) -> bytes:
        data = b""
        for cmp in self.components:
            if isinstance(cmp, str):
                if self.encoding:
                    data += cmp.encode(self.encoding)
                else:
                    data += cmp.encode()
            else:
                data += cmp
        return data

    def get_rich_text(self) -> str:
        # TODO: Construct formatting system from encoded instructions
        string = ""
        for cmp in self.components:
            if isinstance(cmp, str):
                string += cmp.replace("\x00", "")
            else:
                string += RichMessage.command_to_rich(cmp)
        return string

    def get_string(self) -> str:
        string = ""
        for cmp in self.components:
            if isinstance(cmp, str):
                string += cmp
        return string

    def get_raw_size(self) -> int:
        size = 0
        for cmp in self.components:
            if isinstance(cmp, str):
                if self.encoding:
                    size += len(cmp.encode(self.encoding))
                else:
                    size += len(cmp.encode())
            else:
                size += len(cmp)
        return size


class SoundID(IntEnum):
    ...


class BMG():
    """
    Class representing the Nintendo Binary Message Format
    """
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

        size = read_uint32(f) * 32
        f.seek(0, 2)
        assert size == f.tell(), "File size marker doesn't match file size"

        f.seek(12, 0)
        sectionNum = read_uint32(f)
        isPal = sectionNum == 3

        f.seek(16, 1)  # Padding

        for i in range(sectionNum):
            f.seek(align_int(f.tell(), 32))  # 32 bit section alignment
            sectionMagic = f.read(4)
            sectionSize = read_uint32(f)
            if sectionMagic == b"INF1":
                assert i == 0, f"INF1 found at incorrect section index {i}!"
                messageNum = read_uint16(f)
                packetSize = read_uint16(f)
                f.seek(4, 1)  # unknown values

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
                        RichMessage.from_bytes(BytesIO(rawMsg))
                    )
            elif sectionMagic == b"STR1":
                assert i > 0, f"STR1 found before INF1!"
                relOfs = f.tell()
                for i, offset in enumerate(strIDOffsets):
                    names.append(read_string(
                        f, offset+relOfs))

        bmg = cls(isPal, packetSize)
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

        return bmg

    def to_bytes(self) -> bytes:
        header = BytesIO(self.MAGIC)
        header.seek(len(self.MAGIC))
        write_uint32(header, self.get_data_size() // 32)
        write_uint32(header, 3 if self.is_pal() else 2)
        header.write(b"\x00" * 16)  # padding

        inf1Size = self.get_inf1_size()
        dat1Size = self.get_dat1_size()
        str1Size = self.get_str1_size()
        inf1 = BytesIO(b"INF1" + b"\x00"*(inf1Size-4))
        dat1 = BytesIO(b"DAT1" + b"\x00"*(dat1Size-4))
        str1 = BytesIO(b"STR1" + b"\x00"*(str1Size-4))
        inf1.seek(4)
        dat1.seek(4)
        str1.seek(4)
        write_uint32(inf1, inf1Size)
        write_uint32(dat1, dat1Size)
        write_uint32(str1, str1Size)

        write_uint16(inf1, len(self.__messages))
        write_uint16(inf1, self.flagSize)
        write_uint32(inf1, 0x00000100)  # unknown value
        dat1.seek(1, 1)  # idk weird offset thing
        str1.seek(1, 1)  # same here

        for msg in self.__messages:
            # INF1
            write_uint32(inf1, dat1.tell() - 8)
            write_uint16(inf1, msg.startFrame)
            write_uint16(inf1, msg.endFrame)
            if self.is_pal():
                write_uint16(inf1, str1.tell() - 8)
                write_ubyte(inf1, msg.soundID)
                inf1.seek(1, 1)
            else:
                write_ubyte(inf1, msg.soundID)
                inf1.seek(3, 1)

            # DAT1
            dat1.write(msg.message.to_bytes())

            # STR1
            write_string(str1, msg.name)

        data = inf1.getvalue() + dat1.getvalue()
        if self.is_pal():
            data += str1.getvalue()

        return header.getvalue() + data

    def get_data_size(self) -> int:
        if self.is_pal():
            return 0x20 + self.get_inf1_size() + self.get_dat1_size() + self.get_str1_size()
        else:
            return 0x20 + self.get_inf1_size() + self.get_dat1_size()

    def get_inf1_size(self) -> int:
        return align_int(0x10 + (len(self.__messages) * self.flagSize), 32)

    def get_dat1_size(self) -> int:
        return align_int(
            0x9 + sum(
                [msg.message.get_raw_size()
                 for msg in self.__messages]
            ), 32
        )

    def get_str1_size(self) -> int:
        return align_int(
            0x9 + sum(
                [len(msg.name.encode())+1
                 for msg in self.__messages]
            ), 32
        )

    def set_pal(self, isPal: bool):
        self.__isPal = isPal

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
