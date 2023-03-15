import argparse
from dataclasses import dataclass
from io import BytesIO
import struct
from pathlib import Path
from typing import Any, BinaryIO, Iterable, List, Optional, Union
from juniors_toolbox.utils import A_Clonable, A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.iohelper import get_likely_encoding, read_string, read_uint16, read_uint32, write_string

from juniors_toolbox.utils.jdrama import NameRef
from juniors_toolbox.utils.types import RGBA8, RGB8, Vec3f


class PrmEntry(A_Serializable, A_Clonable):
    _key: NameRef
    _value: Any

    def __init__(self, key: str | NameRef, value: Any):
        if isinstance(key, NameRef):
            self._key = key
        else:
            self._key = NameRef(key)
        self._value = value

    def __str__(self) -> str:
        return f"[PRM] {self._key} = {self._value}"

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["PrmEntry"]:
        data.seek(2, 1)
        _type: type = args[0]
        keyLen = read_uint16(data)
        key = NameRef(read_string(data, maxlen=keyLen))
        valueLen = read_uint32(data)
        rawValue = data.read(valueLen)
        value: Any = None
        if issubclass(_type, int):
            value = int.from_bytes(rawValue, "big", signed=False)
        elif issubclass(_type, bool):
            value = True if rawValue == b"\x01" else False
        elif issubclass(_type, str):
            value = rawValue.decode(get_likely_encoding(rawValue))
        elif issubclass(_type, float):
            value = struct.unpack(">f", rawValue)
        elif issubclass(_type, Vec3f):
            value = Vec3f(*struct.unpack(">fff", rawValue))
        elif issubclass(_type, RGB8):
            value = RGB8.from_tuple(struct.unpack(">bbb", rawValue))
        elif issubclass(_type, RGBA8):
            value = RGBA8.from_tuple(struct.unpack(">bbbb", rawValue))
        entry = cls(key, value)
        return entry

    def to_bytes(self) -> bytes:
        data = self.keyCode.to_bytes(2, "big", signed=False)
        data += self.keyLen.to_bytes(2, "big", signed=False)
        data += self.key.encode("ascii")
        data += self.valueLen.to_bytes(4, "big", signed=False)
        
        v = self._value
        if isinstance(v, int):
            data += v.to_bytes(self.valueLen, "big", signed=(v < 0))
        elif isinstance(v, bool):
            data += b"\x00" if v is False else b"\x01"
        elif isinstance(v, str):
            _io = BytesIO()
            write_string(_io, v)
            data += _io.getvalue()
        elif isinstance(v, float):
            data += struct.pack(">f", v)
        elif isinstance(v, Vec3f):
            data += struct.pack(">fff", v.xyz)
        elif isinstance(v, RGB8):
            data += struct.pack(">bbb", v.tuple())
        elif isinstance(v, RGBA8):
            data += struct.pack(">bbbb", v.tuple())
        else:
            return b""
        
        return data

    def copy(self, *, deep: bool = False) -> "PrmEntry":
        cpy = PrmEntry(
            self.key.copy(deep=deep),
            value=self.value
        )
        return cpy

    @property
    def key(self) -> NameRef:
        return self._key

    @key.setter
    def key(self, k: NameRef):
        self._key = k

    @property
    def keyCode(self) -> int:
        return hash(self._key)

    @property
    def keyLen(self) -> int:
        return len(self._key)

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, v: Any):
        self._value = v

    @property
    def valueLen(self) -> int:
        _v = self._value
        if isinstance(_v, int):
            return 4
        elif isinstance(_v, bool):
            return 1
        elif isinstance(_v, str):
            return len(_v.encode())
        elif isinstance(_v, float):
            return 4
        elif isinstance(_v, bytes):
            return len(_v)
        elif isinstance(_v, Vec3f):
            return 12
        elif isinstance(_v, RGB8):
            return 3
        elif isinstance(_v, RGBA8):
            return 4
        return 0

    def __len__(self) -> int:
        return 4 + self.keyLen + 4 + self.valueLen


class PrmFile(A_Serializable):
    def __init__(self, entries: Optional[Union[PrmEntry, Iterable[PrmEntry]]] = None):
        if entries:
            if isinstance(entries, list):
                self._entries = entries
            else:
                self._entries = [entries]
        else:
            self._entries = []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"

    def __len__(self) -> int:
        return len(self._entries)

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["PrmFile"]:
        offset = 0
        entries = list()

        entryNum = int.from_bytes(data.read(4), "big", signed=False)
        for _ in range(entryNum):
            _entry = PrmEntry.from_bytes(data, int)
            if _entry is not None:
                entries.append(_entry)
                offset += len(_entry)

        prm = cls(entries)
        return prm

    @classmethod
    def from_text(cls, text: str) -> "PrmFile":
        def encode_value(value: str) -> bytes:
            value = value.strip()
            if value.startswith("f32("):
                rawValue = struct.pack(">f", float(
                    value[4:-1].strip().rstrip("f")))
            elif value.startswith("f64("):
                rawValue = struct.pack(">d", float(value[4:-1]))
            elif value.startswith("str("):
                rawValue = value[4:-1].encode("ascii")
            elif value.startswith("\""):
                rawValue = value[1:-1].encode("ascii")
            elif value.startswith("s8("):
                rawValue = int(value[3:-1], 16 if value[3:5]
                            in {"0x", "-0x"} else 10).to_bytes(1, "big", signed=True)
            elif value.startswith("s16("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(2, "big", signed=True)
            elif value.startswith("s32("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(4, "big", signed=True)
            elif value.startswith("s64("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(8, "big", signed=True)
            elif value.startswith("u8("):
                rawValue = int(value[3:-1], 16 if value[3:5]
                            in {"0x", "-0x"} else 10).to_bytes(1, "big", signed=False)
            elif value.startswith("u16("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(2, "big", signed=False)
            elif value.startswith("u32("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(4, "big", signed=False)
            elif value.startswith("u64("):
                rawValue = int(value[4:-1], 16 if value[4:6]
                            in {"0x", "-0x"} else 10).to_bytes(8, "big", signed=False)
            elif value.startswith("bool("):
                _v = int(value[5:-1].lower() == "true")
                rawValue = _v.to_bytes(1, "big", signed=False)
            elif value.startswith("bytes("):
                rawValue = int(
                    value[6:-1], 16).to_bytes(len(value[8:-1]) >> 1, "big", signed=False)
            else:
                raise ValueError(
                    f"Invalid value type found while parsing: {value.split('(')[0]}")
            return rawValue

        entries = list()
        for line in text.splitlines():
            line = line.strip().split("#")[0]
            if line == "":
                continue

            key, _, kvalue = line.split(maxsplit=2)
            if kvalue.startswith("list("):
                value = b""
                for item in kvalue[5:-1].split(","):
                    value += encode_value(item)
            else:
                value = encode_value(kvalue)

            entries.append(PrmEntry(key, value))

        return cls(entries)

    def to_bytes(self) -> bytes:
        data = len(self).to_bytes(4, "big", signed=False)

        for entry in self.iter_entries():
            data += entry.to_bytes()

        return data

    def to_text(self) -> str:
        text = ""

        for entry in self.iter_entries():
            if type(entry.value) == int:
                if entry.valueLen == 1:
                    text += f"{entry.key}\t\t=  u8(0x{entry.value:02X})\n"
                elif entry.valueLen == 2:
                    text += f"{entry.key}\t\t=  u16(0x{entry.value:04X})\n"
                elif entry.valueLen == 4:
                    text += f"{entry.key}\t\t=  u32(0x{entry.value:08X})\n"
                elif entry.valueLen == 8:
                    text += f"{entry.key}\t\t=  u64(0x{entry.value:016X})\n"
            elif type(entry.value) == bool:
                text += f"{entry.key}\t\t=  bool({entry.value})\n"
            elif type(entry.value) == str:
                text += f"{entry.key}\t\t=  str({entry.value})\n"
            elif type(entry.value) == float:
                text += f"{entry.key}\t\t=  float({entry.value})\n"
            elif type(entry.value) == Vec3f:
                text += f"{entry.key}\t\t=  Vec3f({entry.value})\n"
            elif type(entry.value) == RGB8:
                text += f"{entry.key}\t\t=  RGB({entry.value})\n"
            elif type(entry.value) == RGBA8:
                text += f"{entry.key}\t\t=  RGBA({entry.value})\n"

        return text.strip()

    def add_entry(self, entry: PrmEntry):
        self._entries.append(entry)

    def remove_entry(self, entry: PrmEntry):
        self._entries.remove(entry)

    def iter_entries(self) -> Iterable[PrmEntry]:
        for entry in self._entries:
            yield entry


def decode_all(path: Path, dest: Path, suffix: str = ".prm"):
    startPath = path

    def decode(path: Path, dest: Path, suffix: str):
        nonlocal startPath
        if path.is_dir():
            for p in path.iterdir():
                decode(p, dest, suffix)
        elif path.is_file():
            if path.suffix != suffix:
                print(f"[PRM-PARSER] (Invalid Extension) Ignoring {path}")
                return

            with path.open("rb") as f:
                prm = PrmFile.from_bytes(f)

            if prm is None:
                return

            if not dest.is_file() and dest.suffix == "":
                dest.mkdir(parents=True, exist_ok=True)
                try:
                    dest = dest / \
                        path.relative_to(startPath).with_suffix(suffix)
                except ValueError:
                    dest = dest.with_name(path.name).with_suffix(suffix)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)

            dest.write_bytes(prm.to_bytes())
        else:
            print(f"[PRM-PARSER] (Path Not Found) Ignoring {path}")

    decode(path, dest, suffix)


def encode_all(path: Path, dest: Path, suffix: str = ".prm"):
    startPath = path

    def encode(path: Path, dest: Path, suffix: str):
        nonlocal startPath
        if path.is_dir():
            for p in path.iterdir():
                encode(p, dest, suffix)
        elif path.is_file():
            if path.suffix != ".txt":
                print(f"[PRM-PARSER] (Invalid Extension) Ignoring {path}")
                return

            prm = PrmFile.from_text(path.read_text())
            if not dest.is_file() and dest.suffix == "":
                dest.mkdir(parents=True, exist_ok=True)
                try:
                    dest = dest / \
                        path.relative_to(startPath).with_suffix(suffix)
                except ValueError:
                    dest = (dest / path.name).with_suffix(suffix)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)

            dest.write_bytes(prm.to_bytes())
        else:
            print(f"[PRM-PARSER] (Path Not Found) Ignoring {path}")

    encode(path, dest, suffix)


def init_template(dest: Path):
    intEntry = PrmEntry("OurIntEntry", 800)
    boolEntry = PrmEntry("OurBoolEntry", False)
    strEntry = PrmEntry("OurStrEntry", "Example string")
    floatEntry = PrmEntry("OurFloatEntry", 3.14159265358979323846)
    bytesEntry = PrmEntry("OurBytesEntry", b"\x00\xD0\xC0\xDE")

    prm = PrmFile({intEntry, boolEntry, strEntry, floatEntry, bytesEntry})
    print(prm.to_text())
    dest.mkdir(parents=True, exist_ok=True)
    dest.write_text(prm.to_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='.prm parser for SMS modding',
                                     description='Create/Edit/Save/Extract .prm files',
                                     allow_abbrev=False)

    parser.add_argument('path', help='input file/folder')
    parser.add_argument("job",
                        help="Job to execute. Valid jobs are `c' (Compile), `d' (Decompile), and `i' (Init)",
                        choices=["c", "d", "i"])
    parser.add_argument('--dest',
                        help='Where to create/dump contents to',
                        metavar='filepath')

    args = parser.parse_args()

    path = Path(args.path)
    if args.dest:
        dest = Path(args.dest)
        if dest.suffix == "":
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
    elif path.is_file():
        dest = path.with_suffix(".prm")
    else:
        dest = path / "out"

    if args.job == "i":
        init_template(path)
    elif args.job == "d":
        decode_all(path, dest)
    elif args.job == "c":
        encode_all(path, dest)
    else:
        parser.print_help()
