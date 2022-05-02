from dataclasses import dataclass, field
import enum
from typing import BinaryIO, Iterable, List, Optional, Tuple, Union
from io import BytesIO

from numpy import array, ndarray

from juniors_toolbox.utils.iohelper import (align_int, read_float, read_sint16, read_string, read_uint32,
                                           write_float, write_sint16, write_string, write_uint16, write_uint32)
from juniors_toolbox.utils import JSYSTEM_PADDING_TEXT, A_Serializable, VariadicArgs, VariadicKwargs


@dataclass
class RailKeyFrame(A_Serializable):
    position: ndarray = array([0, 0, 0])
    unk: ndarray = array([0, 0, 0])
    rotation: ndarray = array([-1, -1, -1])
    speed: int = -1
    connections: List[int] = field(default_factory=lambda: [0]*8)
    periods: List[float] = field(default_factory=lambda: [0]*8)

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
        frame = cls(
            position = array(
                [read_sint16(data),
                 read_sint16(data),
                 read_sint16(data)]
            ),
            unk = array(
                [read_sint16(data),
                 read_sint16(data),
                 read_sint16(data)]
            ),
            rotation = array(
                [read_sint16(data),
                 read_sint16(data),
                 read_sint16(data)]
            ),
            speed = read_sint16(data),
            connections = [read_sint16(data) for _ in range(8)],
            periods = [read_float(data) for _ in range(8)],
        )
        return frame

    def to_bytes(self) -> bytes:
        stream = BytesIO()

        for n in self.position:
            write_sint16(stream, n)

        for n in self.unk:
            write_sint16(stream, n)

        for n in self.rotation:
            write_sint16(stream, n)

        write_sint16(stream, self.speed)

        for n in self.connections:
            write_sint16(stream, n)

        for n in self.periods:
            write_float(stream, n)

        return stream.getvalue()

    def copy(self) -> "RailKeyFrame":
        """
        Return a copy of this frame
        """
        return RailKeyFrame(
            self.position.copy(),
            self.unk.copy(),
            self.rotation.copy(),
            self.speed,
            self.connections.copy(),
            self.periods.copy()
        )

    def size(self) -> int:
        return 68

    def __len__(self) -> int:
        return 68


class Rail(A_Serializable):
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

    def copy(self) -> "Rail":
        copy = Rail(self.name)
        for frame in self._frames:
            copy._frames.append(frame.copy())
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
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
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