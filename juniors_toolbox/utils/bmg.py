from dataclasses import dataclass, field
from enum import IntEnum
from io import BytesIO
from os import write
from typing import Any, BinaryIO, Iterable, List, Optional, Tuple, Union

from juniors_toolbox.utils import (A_Clonable, A_Serializable, VariadicArgs,
                                   VariadicKwargs)
from juniors_toolbox.utils.iohelper import (align_int, decode_raw_string,
                                            get_likely_encoding, read_string,
                                            read_ubyte, read_uint16,
                                            read_uint32, write_string,
                                            write_ubyte, write_uint16,
                                            write_uint32)


@dataclass
class RichMessage(A_Serializable, A_Clonable):
    components: list = field(default_factory=lambda: [])
    encoding: Optional[str] = None

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

        return "{raw:" + f"0x{cmd[1:].hex().upper()}" + "}"

    @staticmethod
    def rich_to_command(rich: str) -> Optional[bytes]:
        if rich in RichMessage._RICH_TO_COMMAND:
            return RichMessage._RICH_TO_COMMAND[rich]

        try:
            if rich.startswith("{speed:"):
                rich = rich.replace(" ", "")
                speed = int(rich[7:-1])
                return b"\x1A\x06\x00\x00\x00" + speed.to_bytes(1, "big", signed=False)

            if rich.startswith("{option:"):
                command, message = rich.rsplit(":", 1)
                command.replace(" ", "")
                rawmsg = message[:-1].encode()

                option = int(command[8:]).to_bytes(1, "big", signed=False)
                length = (len(rawmsg) + 5).to_bytes(1, "big", signed=False)
                return b"\x1A" + length + b"\x01\x00" + option + rawmsg

            if rich.startswith("{raw:"):
                rich = rich.replace(" ", "")
                rawval = int(rich[5:-1], 16)
                return b"\x1A" + rawval.to_bytes((rawval.bit_length() + 7) // 8, "big", signed=False)
        except Exception:
            pass
        return None

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["RichMessage"]:
        TERMINATING_CHARS = {b"", }
        encoding = kwargs.get("encoding")

        string = b""
        components: List[str | bytes] = []
        _encodingGuess = encoding
        _nullCount = 0
        while (char := data.read(1)) != b"":
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

                cmdLength = data.read(1)
                components.append(
                    char + cmdLength + data.read(cmdLength[0] - 2)
                )
            else:
                string += char
        if string not in TERMINATING_CHARS:
            if _encodingGuess is None:
                _encodingGuess = get_likely_encoding(string)
            components.append(decode_raw_string(string, encoding)[:-1])
        return cls(components, _encodingGuess)

    @classmethod
    def from_rich_string(cls, string: str):
        components: list[str | bytes] = []
        substr = ""
        lPos = string.find("{")
        rPos = string.find("}", lPos)
        nextLPos = string.find("{", lPos+1)
        encoding = None
        while lPos > -1 and rPos > -1:
            isCmdEnclosed = rPos < nextLPos or nextLPos == -1
            mainstr = string[:lPos]
            if mainstr != "":
                if encoding is None:
                    encoding = get_likely_encoding(mainstr.encode())
                components.append(mainstr)
            if isCmdEnclosed:
                substr = string[lPos:rPos+1]
            else:
                substr = string[lPos:nextLPos]
            if substr != "":
                if isCmdEnclosed:
                    # Attempt to convert subtext to a command
                    part = RichMessage.rich_to_command(substr)
                    if part is None:
                        # Pass as raw text
                        components.append(substr)
                    else:
                        # Pass the command
                        components.append(part)
                    string = string[rPos+1:]
                else:
                    # Pass as raw text
                    components.append(substr)
                    string = string[nextLPos:]
                lPos = string.find("{")
                rPos = string.find("}", lPos)
                nextLPos = string.find("{", lPos+1)
        if string != "":
            if encoding is None:
                encoding = get_likely_encoding(string.encode())
            components.append(string)
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
        return data + b"\x00"

    def copy(self, *, deep: bool = False) -> "RichMessage":
        cpy = RichMessage(
            self.components.copy(),
            self.encoding
        )
        return cpy

    def get_rich_text(self) -> str:
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
        return size + 1


class SoundID(IntEnum):
    NOTHING = 69
    PEACH_NORMAL = 0
    PEACH_SURPRISE = 1
    PEACH_WORRY = 2
    PEACH_ANGER_L = 3
    PEACH_APPEAL = 4
    PEACH_DOUBT = 5
    TOADSWORTH_NORMAL = 6
    TOADSWORTH_EXCITED = 7
    TOADSWORTH_ADVICE = 8
    TOADSWORTH_CONFUSED = 9
    TOADSWORTH_ASK = 10
    TOAD_NORMAL = 11
    TOAD_CRY_S = 12
    TOAD_CRY_L = 13
    TOAD_PEACE = 14
    TOAD_SAD_S = 15
    TOAD_ASK = 16
    TOAD_CONFUSED = 17
    TOAD_RECOVER = 18
    TOAD_SAD_L = 19
    MALE_PIANTA_NORMAL = 20
    MALE_PIANTA_LAUGH_D = 21
    MALE_PIANTA_DISGUSTED = 22
    MALE_PIANTA_ANGER_S = 23
    MALE_PIANTA_SURPRISE = 24
    MALE_PIANTA_DOUBT = 25
    MALE_PIANTA_DISPLEASED = 26
    MALE_PIANTA_CONFUSED = 27
    MALE_PIANTA_REGRET = 28
    MALE_PIANTA_PROUD = 29
    MALE_PIANTA_RECOVER = 30
    MALE_PIANTA_INVITING = 31
    MALE_PIANTA_QUESTION = 32
    MALE_PIANTA_LAUGH = 33
    MALE_PIANTA_THANKS = 34
    FEMALE_PIANTA_NORMAL = 35
    FEMALE_PIANTA_REGRET = 36
    FEMALE_PIANTA_INVITING = 37
    FEMALE_PIANTA_LAUGH = 38
    FEMALE_PIANTA_LAUGH_D = 70
    FEMALE_PIANTA_DISGUSTED = 71
    FEMALE_PIANTA_ANGER_S = 72
    FEMALE_PIANTA_SURPRISE = 73
    FEMALE_PIANTA_DOUBT = 74
    FEMALE_PIANTA_DISPLEASED = 75
    FEMALE_PIANTA_CONFUSED = 76
    FEMALE_PIANTA_PROUD = 77
    FEMALE_PIANTA_RECOVER = 78
    FEMALE_PIANTA_QUESTION = 79
    FEMALE_PIANTA_THANKS = 80
    CHILD_MALE_PIANTA_NORMAL = 81
    CHILD_MALE_PIANTA_LAUGH_D = 82
    CHILD_MALE_PIANTA_DISGUSTED = 83
    CHILD_MALE_PIANTA_ANGER_S = 84
    CHILD_MALE_PIANTA_SURPRISE = 85
    CHILD_MALE_PIANTA_DOUBT = 86
    CHILD_MALE_PIANTA_DISPLEASED = 87
    CHILD_MALE_PIANTA_CONFUSED = 88
    CHILD_MALE_PIANTA_REGRET = 89
    CHILD_MALE_PIANTA_PROUD = 90
    CHILD_MALE_PIANTA_RECOVER = 91
    CHILD_MALE_PIANTA_INVITING = 92
    CHILD_MALE_PIANTA_QUESTION = 93
    CHILD_MALE_PIANTA_LAUGH = 94
    CHILD_MALE_PIANTA_THANKS = 95
    CHILD_FEMALE_PIANTA_NORMAL = 96
    CHILD_FEMALE_PIANTA_LAUGH_D = 97
    CHILD_FEMALE_PIANTA_DISGUSTED = 98
    CHILD_FEMALE_PIANTA_ANGER_S = 99
    CHILD_FEMALE_PIANTA_SURPRISE = 100
    CHILD_FEMALE_PIANTA_DOUBT = 101
    CHILD_FEMALE_PIANTA_DISPLEASED = 102
    CHILD_FEMALE_PIANTA_CONFUSED = 103
    CHILD_FEMALE_PIANTA_REGRET = 104
    CHILD_FEMALE_PIANTA_PROUD = 105
    CHILD_FEMALE_PIANTA_RECOVER = 106
    CHILD_FEMALE_PIANTA_INVITING = 107
    CHILD_FEMALE_PIANTA_QUESTION = 108
    CHILD_FEMALE_PIANTA_LAUGH = 109
    CHILD_FEMALE_PIANTA_THANKS = 110
    MALE_NOKI_NORMAL = 39
    MALE_NOKI_REGRET = 40
    MALE_NOKI_LAUGH = 41
    MALE_NOKI_APPEAL = 42
    MALE_NOKI_SUPRISE = 43
    MALE_NOKI_SAD = 44
    MALE_NOKI_ASK = 45
    MALE_NOKI_PROMPT = 46
    MALE_NOKI_THANKS = 47
    FEMALE_NOKI_NORMAL = 48
    FEMALE_NOKI_REGRET = 49
    FEMALE_NOKI_LAUGH = 50
    FEMALE_NOKI_APPEAL = 51
    FEMALE_NOKI_SURPRISE = 52
    FEMALE_NOKI_SAD = 53
    FEMALE_NOKI_ASK = 54
    FEMALE_NOKI_PROMPT = 55
    FEMALE_NOKI_THANKS = 56
    ELDER_NOKI_NORMAL = 57
    ELDER_NOKI_REGRET = 58
    ELDER_NOKI_LAUGH = 59
    ELDER_NOKI_APPEAL = 60
    ELDER_NOKI_SURPRISE = 61
    ELDER_NOKI_SAD = 62
    ELDER_NOKI_ASK = 63
    ELDER_NOKI_PROMPT = 64
    ELDER_NOKI_THANKS = 65
    CHILD_MALE_NOKI_NORMAL = 111
    CHILD_MALE_NOKI_REGRET = 112
    CHILD_MALE_NOKI_LAUGH = 113
    CHILD_MALE_NOKI_APPEAL = 114
    CHILD_MALE_NOKI_SURPRISE = 115
    CHILD_MALE_NOKI_SAD = 116
    CHILD_MALE_NOKI_ASK = 117
    CHILD_MALE_NOKI_PROMPT = 118
    CHILD_MALE_NOKI_THANKS = 119
    CHILD_FEMALE_NOKI_NORMAL = 120
    CHILD_FEMALE_NOKI_REGRET = 121
    CHILD_FEMALE_NOKI_LAUGH = 122
    CHILD_FEMALE_NOKI_APPEAL = 123
    CHILD_FEMALE_NOKI_SURPRISE = 124
    CHILD_FEMALE_NOKI_SAD = 125
    CHILD_FEMALE_NOKI_ASK = 126
    CHILD_FEMALE_NOKI_PROMPT = 127
    CHILD_FEMALE_NOKI_THANKS = 128
    SUNFLOWER_PARENT_JOY = 67
    SUNFLOWER_PARENT_SAD = 68
    TANUKI_NORMAL = 66
    SHADOW_MARIO_PSHOT = 132
    IL_PIANTISSIMO_NORMAL = 133
    IL_PIANTISSIMO_LOST = 134
    ITEM_COLLECT_DELIGHT = 129
    ITEM_NOT_COLLECT = 131
    BGM_FANFARE = 130

    # @classmethod
    # def _missing_(cls, value: int) -> "SoundID":
    #     memberName = f"UNKNOWN_SOUND_{value}"
    #     extend_enum(cls, memberName, value)
    #     return cls(value)

    @classmethod
    def name_to_sound_id(cls, name: str):
        return cls._member_map_[name]


class BMG(A_Serializable, A_Clonable):
    """
    Class representing the Nintendo Binary Message Format
    """
    @dataclass
    class MessageEntry(A_Clonable):
        name: str
        message: RichMessage = RichMessage()
        soundID: SoundID = SoundID.NOTHING
        startFrame: int = 0
        endFrame: int = 0
        _unkflags: bytes = b""

        def copy(self, *, deep: bool = False) -> "BMG.MessageEntry":
            cpy = BMG.MessageEntry(
                self.name,
                self.message.copy(deep=deep),
                self.soundID,
                self.startFrame,
                self.endFrame,
                self._unkflags
            )
            return cpy

        def __str__(self) -> str:
            return f"{self.name} :: {self.message.get_string()}"

    MAGIC = b"MESGbmg1"

    def __init__(self, isStr1Present: bool = True, flagSize: int = 12):
        self.flagSize = flagSize

        self._messages: List[BMG.MessageEntry] = []
        self._isStr1 = isStr1Present

    @staticmethod
    def is_str1_present_f(f: BytesIO) -> bool:
        if f.read(8) != BMG.MAGIC:
            return False

        f.seek(4, 1)
        isPal = read_uint32(f) == 3
        f.seek(-0x10)
        return isPal

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["BMG"]:
        assert data.read(8) == BMG.MAGIC, "File is invalid!"

        size = read_uint32(data) * 32
        data.seek(0, 2)
        assert size == data.tell(), "File size marker doesn't match file size"

        data.seek(12, 0)
        sectionNum = read_uint32(data)
        isPal = sectionNum == 3

        data.seek(16, 1)  # Padding

        for i in range(sectionNum):
            data.seek(align_int(data.tell(), 32))  # 32 bit section alignment
            sectionMagic = data.read(4)
            sectionSize = read_uint32(data)
            if sectionMagic == b"INF1":
                assert i == 0, f"INF1 found at incorrect section index {i}!"
                messageNum = read_uint16(data)
                packetSize = read_uint16(data)
                data.seek(4, 1)  # unknown values

                dataOffsets = []
                strIDOffsets = []
                messageMetaDatas = []
                messages = []
                names = []
                for i in range(messageNum):
                    if packetSize == 12:
                        dataOffsets.append(read_uint32(data))
                        fStart = read_uint16(data)
                        fEnd = read_uint16(data)
                        if isPal:
                            strIDOffsets.append(read_uint16(data))
                        soundID = SoundID(read_ubyte(data))
                        data.seek(1 if isPal else 3, 1)
                        unkFlags = b""
                    elif packetSize == 8:
                        dataOffsets.append(read_uint32(data))
                        soundID = SoundID.NOTHING
                        fStart = 0
                        fEnd = 0
                        unkFlags = data.read(4)
                    elif packetSize == 4:
                        dataOffsets.append(read_uint32(data))
                        soundID = SoundID.NOTHING
                        fStart = 0
                        fEnd = 0
                        unkFlags = b""
                    else:
                        raise NotImplementedError("PacketSize unknown")
                    messageMetaDatas.append([fStart, fEnd, soundID, unkFlags])
            elif sectionMagic == b"DAT1":
                assert i > 0, f"DAT1 found before INF1!"
                block = data.read(sectionSize - 8)
                for i, offset in enumerate(dataOffsets):
                    if i < len(dataOffsets) - 1:
                        rawMsg = block[offset:dataOffsets[i+1]]
                    else:
                        rawMsg = block[offset:]
                    richMsg = RichMessage.from_bytes(BytesIO(rawMsg))
                    if richMsg is not None:
                        messages.append(richMsg)
            elif sectionMagic == b"STR1":
                assert i > 0, f"STR1 found before INF1!"
                relOfs = data.tell()
                for i, offset in enumerate(strIDOffsets):
                    names.append(
                        read_string(data, offset+relOfs)
                    )

        bmg = cls(isPal, packetSize)
        for i in range(len(messages)):
            bmg.add_message(
                BMG.MessageEntry(
                    names[i] if isPal and packetSize == 12 else "",
                    messages[i],
                    messageMetaDatas[i][2],
                    messageMetaDatas[i][0],
                    messageMetaDatas[i][1],
                    messageMetaDatas[i][3]
                )
            )

        return bmg

    def to_bytes(self) -> bytes:
        header = BytesIO(self.MAGIC)
        header.seek(len(self.MAGIC))
        write_uint32(header, self.get_data_size() // 32)
        write_uint32(header, 3 if self.is_str1_present() else 2)
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

        write_uint16(inf1, len(self._messages))
        write_uint16(inf1, self.flagSize)
        write_uint32(inf1, 0x00000100)  # unknown value
        dat1.seek(1, 1)  # idk weird offset thing
        str1.seek(1, 1)  # same here

        for msg in self._messages:
            # INF1
            if self.flagSize == 12:
                write_uint32(inf1, dat1.tell() - 8)
                write_uint16(inf1, msg.startFrame)
                write_uint16(inf1, msg.endFrame)
                if self.is_str1_present():
                    write_uint16(inf1, str1.tell() - 8)
                    write_ubyte(inf1, msg.soundID)
                    inf1.seek(1, 1)
                else:
                    write_ubyte(inf1, msg.soundID)
                    inf1.seek(3, 1)
            elif self.flagSize == 8:
                write_uint32(inf1, dat1.tell() - 8)
                flags = msg._unkflags + b"\x00" * \
                    max(0, 4 - len(msg._unkflags))
                inf1.write(flags)
            elif self.flagSize == 4:
                write_uint32(inf1, dat1.tell() - 8)
            else:
                raise NotImplementedError("PacketSize unknown")

            # DAT1
            dat1.write(msg.message.to_bytes())

            # STR1
            write_string(str1, msg.name)

        data = inf1.getvalue() + dat1.getvalue()
        if self.is_str1_present():
            data += str1.getvalue()

        return header.getvalue() + data

    def copy(self, *, deep: bool = False) -> A_Clonable:
        cpy = BMG()
        cpy.flagSize = self.flagSize
        cpy._isStr1 = self._isStr1

        for msg in self._messages:
            cpy._messages.append(
                msg.copy(deep=deep)
            )

        return cpy

    def get_data_size(self) -> int:
        if self.is_str1_present():
            return 0x20 + self.get_inf1_size() + self.get_dat1_size() + self.get_str1_size()
        else:
            return 0x20 + self.get_inf1_size() + self.get_dat1_size()

    def get_inf1_size(self) -> int:
        return align_int(0x10 + (len(self._messages) * self.flagSize), 32)

    def get_dat1_size(self) -> int:
        return align_int(
            0x9 + sum(
                [msg.message.get_raw_size()
                 for msg in self._messages]
            ), 32
        )

    def get_str1_size(self) -> int:
        return align_int(
            0x9 + sum(
                [len(msg.name.encode())+1
                 for msg in self._messages]
            ),
            32
        )

    def set_str1_present(self, isStr1: bool):
        self._isStr1 = isStr1

    def is_str1_present(self) -> bool:
        return self._isStr1 and self.flagSize == 12

    def add_message(self, message: MessageEntry):
        self._messages.append(message)

    def remove_message(self, message: MessageEntry):
        self._messages.remove(message)

    def get_message(self, _id: Union[str, int]):
        if isinstance(_id, int):
            if _id >= len(self._messages):
                return None
            return self._messages[_id]
        for msg in self._messages:
            if _id == msg.name:
                return msg

    def iter_messages(self) -> Iterable[MessageEntry]:
        for msg in self._messages:
            yield msg

    def __len__(self) -> int:
        return len(self._messages)
