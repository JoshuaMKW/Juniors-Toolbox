from dataclasses import dataclass, field
import enum
from math import sqrt
from typing import BinaryIO, Iterable, List, Optional, Tuple, Union
from io import BytesIO

from numpy import array, ndarray
from juniors_toolbox.objects.value import MemberValue, ValueType

from juniors_toolbox.utils.iohelper import (align_int, read_float, read_sint16, read_string, read_uint32,
                                            write_float, write_sint16, write_string, write_uint16, write_uint32)
from juniors_toolbox.utils import JSYSTEM_PADDING_TEXT, A_Clonable, A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.types import Vec3f


class RailKeyFrame(A_Serializable, A_Clonable):
    def __init__(self, x: int = 0, y: int = 0, z: int = 0, *, flags: int = 0) -> None:
        super().__init__()
        self.posX = MemberValue("PositionX", x, ValueType.S16)
        self.posY = MemberValue("PositionY", y, ValueType.S16)
        self.posZ = MemberValue("PositionZ", z, ValueType.S16)

        self.connectionCount = MemberValue("Connections", 0, ValueType.S16)

        self.flags = MemberValue("Flags", flags, ValueType.U32)

        self.values = MemberValue("Value{i}", -1, ValueType.S16)
        self.values.set_array_size(4)

        self.connections = MemberValue("Connection{i}", 0, ValueType.S16)
        self.connections.set_array_size(8)

        self.periods = MemberValue("Period{i}", 0, ValueType.F32)
        self.periods.set_array_size(8)

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
        posX = read_sint16(data)
        posY = read_sint16(data)
        posZ = read_sint16(data)
        connectionCount=read_sint16(data)
        flags=read_uint32(data)

        frame = cls(
            posX,
            posY,
            posZ,
            flags=flags
        )

        frame.connectionCount.set_value(connectionCount)

        for i in range(4):
            frame.values[i].set_value(read_sint16(data))

        for i in range(8):
            frame.connections[i].set_value(read_sint16(data))

        for i in range(8):
            frame.periods[i].set_value(read_float(data))

        return frame

    def to_bytes(self) -> bytes:
        stream = BytesIO()

        write_sint16(stream, self.posX.get_value())
        write_sint16(stream, self.posY.get_value())
        write_sint16(stream, self.posZ.get_value())

        write_sint16(stream, self.connectionCount.get_value())
        write_uint32(stream, self.flags.get_value())

        for i in range(4):
            write_sint16(stream, self.values[i].get_value())

        for i in range(8):
            write_sint16(stream, self.connections[i].get_value())

        for i in range(8):
            write_float(stream, self.periods[i].get_value())

        return stream.getvalue()

    def copy(self, *, deep: bool = False) -> "RailKeyFrame":
        """
        Return a copy of this frame
        """
        _copy = RailKeyFrame(
            self.posX.get_value(),
            self.posY.get_value(),
            self.posZ.get_value(),
            flags=self.flags.get_value()
        )
        for i in range(_copy.values.get_array_size()):
            _copy.values[i].set_value(
                self.values[i].get_value()
            )
        for i in range(_copy.connections.get_array_size()):
            _copy.connections[i].set_value(
                self.connections[i].get_value()
            )
        for i in range(_copy.periods.get_array_size()):
            _copy.periods[i].set_value(
                self.periods[i].get_value()
            )
        return _copy

    def add_connection(self, connection: int) -> bool:
        if self.connectionCount.get_value() >= 8:
            return False
        self.connections[self.connectionCount.get_value()] = connection
        self.connectionCount.set_value(self.connectionCount.get_value() + 1)
        return True

    def set_period_from(self, connection: int, connected: "RailKeyFrame"):
        if connection not in range(8):
            raise ValueError(f"Connection ({connection}) is beyond the array size")

        thisPos = Vec3f(
            self.posX.get_value(),
            self.posY.get_value(),
            self.posZ.get_value()
        )
        thatPos = Vec3f(
            connected.posX.get_value(),
            connected.posY.get_value(),
            connected.posZ.get_value()
        )
        diff = thisPos - thatPos
        self.periods[connection].set_value(sqrt(diff.dot(diff)))

    def size(self) -> int:
        return 68

    def __len__(self) -> int:
        return 68


class Rail(A_Serializable, A_Clonable):
    def __init__(self, name: str, frames: Optional[List[RailKeyFrame]] = None):
        if frames is None:
            frames = []

        self.name = name
        self._frames = frames

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["Rail"]:
        """
        Returns a Rail from the given data
        """
        size = read_uint32(data)
        if size == 0:
            return None

        namePos = read_uint32(data)
        dataPos = read_uint32(data)
        _oldPos = data.tell()  # Preserve position

        this = cls(read_string(data, offset=namePos))

        data.seek(dataPos)
        for _ in range(size):
            this._frames.append(RailKeyFrame.from_bytes(data))

        data.seek(_oldPos)
        return this

    def to_bytes(self) -> bytes:
        """
        Stores the data form of this Rail
        """
        data = BytesIO()
        self.save(data, 0, 0, 0)
        return data.getvalue()

    def iter_frames(self) -> Iterable[RailKeyFrame]:
        for frame in self._frames:
            yield frame

    def swap_frames(self, idx1: int, idx2: int) -> bool:
        """
        Swaps two frames in this rail

        Returns True if successful
        """
        try:
            frame1 = self._frames[idx1]
            frame2 = self._frames[idx2]
            self._frames[idx1] = frame2
            self._frames[idx2] = frame1
            return True
        except IndexError:
            return False

    def insert_frame(self, idx: int, frame: RailKeyFrame) -> bool:
        """
        Inserts a frame into this rail at `idx`

        Returns True if successful
        """
        try:
            self._frames.insert(idx, frame)
            return True
        except IndexError:
            return False

    def remove_frame(self, frame: RailKeyFrame) -> bool:
        """
        Removes a frame from this rail
        """
        self._frames.remove(frame)
        return True

    def remove_frame_by_index(self, idx: int) -> bool:
        """
        Removes a frame at `idx` from this rail
        """
        try:
            self._frames.pop(idx)
            return True
        except IndexError:
            return False

    def copy(self, *, deep: bool = False) -> "Rail":
        copy = Rail(self.name)
        for frame in self._frames:
            copy._frames.append(frame.copy(deep=deep))
        return copy

    def save(self, data: BinaryIO, headerloc: int, nameloc: int, dataloc: int):
        """
        Stores the data form of this Rail
        """
        data.seek(headerloc, 0)
        write_uint32(data, len(self._frames))
        write_uint32(data, nameloc)
        write_uint32(data, dataloc)

        data.seek(nameloc, 0)
        write_string(data, self.name)

        data.seek(dataloc)
        for frame in self._frames:
            data.write(frame.to_bytes())

    def size(self) -> int:
        return self.header_size() + self.name_size() + self.data_size()

    def header_size(self) -> int:
        return 12

    def name_size(self) -> int:
        return len(self.name) + 1

    def data_size(self) -> int:
        return 68 * len(self._frames)

    def __len__(self) -> int:
        return self.size()


class RalData(A_Serializable):
    def __init__(self, rails: Optional[List[Rail]] = None):
        if rails is None:
            rails = []

        self._rails = rails

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["RalData"]:
        this = cls()
        while (rail := Rail.from_bytes(data)) is not None:
            this._rails.append(rail)
        return this

    def to_bytes(self) -> bytes:
        headerloc = self.header_start()
        nameloc = self.name_start()
        dataloc = self.data_start()

        data = BytesIO()
        for rail in self._rails:
            rail.save(data, headerloc, nameloc, dataloc)
            headerloc += rail.header_size()
            nameloc += rail.name_size()
            dataloc += rail.data_size()

        data.seek(headerloc)
        data.write(b"\x00"*12)
        return data.getvalue()

    def iter_rails(self) -> Iterable[Rail]:
        for frame in self._rails:
            yield frame

    def get_rail(self, name: str) -> Optional[Rail]:
        for rail in self._rails:
            if rail.name == name:
                return rail
        return None

    def get_rail_by_index(self, idx: int) -> Optional[Rail]:
        try:
            return self._rails[idx]
        except IndexError:
            return None

    def set_rail(self, rail: Rail):
        for i, r in enumerate(self._rails):
            if r.name == rail.name:
                self._rails[i] = rail
                return
        self._rails.append(rail)

    def set_rail_by_index(self, idx: int, rail: Rail) -> bool:
        try:
            self._rails[idx] = rail
            return True
        except IndexError:
            return False

    def rename_rail(self, name: str, new: str) -> bool:
        for r in self._rails:
            if r.name == name:
                r.name = new
                return True
        return False

    def remove_rail(self, name: str) -> bool:
        for r in self._rails:
            if r.name == name:
                self._rails.remove(r)
                return True
        return False

    def size(self) -> int:
        return align_int(sum([r.size() for r in self._rails]), 32)

    def header_start(self) -> int:
        return 0

    def name_start(self) -> int:
        return sum([r.header_size() for r in self._rails]) + 12

    def data_start(self) -> int:
        return align_int(sum([r.header_size() + r.name_size() for r in self._rails]), 4) + 12

    def __len__(self) -> int:
        return self.size()

    def __contains__(self, other: Union[str, Rail]) -> bool:
        if isinstance(other, Rail):
            return other in self._rails
        return any([r.name == other for r in self._rails])
