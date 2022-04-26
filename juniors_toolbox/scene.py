from io import BytesIO
from pickle import TRUE
import sys
from pathlib import Path
from typing import BinaryIO, Iterable, List, Optional, TextIO

from juniors_toolbox.objects.object import BaseObject
from juniors_toolbox.rail import Rail, RalData

class SMSScene():
    BIN_PARAM_PATH = Path("Parameters")

    def __init__(self):
        self.reset()

    @classmethod
    def from_path(cls, scene: Path) -> "SMSScene":
        """
        Create a scene from either the scene folder or the scene.bin
        """
        if not scene.is_dir():
            return None

        this = cls()

        objPath = scene / "map/scene.bin"
        tablePath = scene / "map/tables.bin"
        railPath = scene / "map/scene.ral"
        with objPath.open("rb") as f:
            _startPos = f.tell()
            f.seek(0, 2)
            end = f.tell()
            f.seek(_startPos, 0)

            while f.tell() < end:
                this._objects.append(BaseObject.from_bytes(f))
        
        with railPath.open("rb") as f:
            this._raildata = RalData.from_bytes(f)

        with tablePath.open("rb") as f:
            _startPos = f.tell()
            f.seek(0, 2)
            end = f.tell()
            f.seek(_startPos, 0)

            while f.tell() < end:
                this._tables.append(BaseObject.from_bytes(f))

        return this

    def reset(self):
        """
        Reset the scene back to an empty state
        """
        self._objects: List[BaseObject] = []
        self._tables: List[BaseObject] = []
        self._raildata: RalData = None

    def dump(self, out: Optional[TextIO] = None, indentwidth: int = 2):
        """
        Dump a map of this scene to the stream `out`
        """
        for obj in self.iter_objects():
            obj.print_map(out, 0, indentwidth)
        for table in self.iter_tables():
            table.print_map(out, 0, indentwidth)
        for rail in self.iter_rails():
            out.write(rail + "\n")

    def iter_objects(self, deep: bool = False) -> Iterable[BaseObject]:
        for obj in self._objects:
            yield obj
            if deep and obj.is_group():
                yield from obj.iter_grouped(True)

    def get_object(self, name: str, desc: str) -> BaseObject:
        for obj in self.iter_objects(True):
            if obj.name == name and obj.desc == desc:
                return obj

    def iter_tables(self, deep: bool = False) -> Iterable[BaseObject]:
        for obj in self._tables:
            yield obj
            if deep and obj.is_group():
                yield from obj.iter_grouped(True)

    def get_table(self, name: str, desc: str) -> BaseObject:
        for obj in self.iter_tables(True):
            if obj.name == name and obj.desc == desc:
                return obj
        
    def iter_rails(self) -> Iterable[Rail]:
        for rail in self._raildata.iter_rails():
            yield rail

    def get_rail(self, name: str) -> Rail:
        for rail in self._raildata._rails:
            if rail.name == name:
                return name

    def get_rail_by_index(self, idx: int) -> Rail:
        try:
            return self._raildata._rails[idx]
        except IndexError:
            return None

    def set_rail(self, rail: Rail):
        for i, r in enumerate(self._raildata._rails):
            if r.name == rail.name:
                self._raildata._rails[i] = rail
                return
        self._raildata._rails.append(rail)

    def set_rail_by_index(self, idx: int, rail: Rail) -> bool:
        try:
            self._raildata._rails[idx] = rail
            return True
        except IndexError:
            return False

    def rename_rail(self, name: str, new: str) -> bool:
        for r in self._raildata._rails:
            if r.name == name:
                r.name = new
                return True
        return False

    def remove_rail(self, name: str) -> bool:
        for r in self._raildata._rails:
            if r.name == name:
                self._raildata._rails.remove(r)
                return True
        return False

    def __contains__(self, other: BaseObject) -> bool:
        return other in self._objects