from io import BytesIO
from pickle import TRUE
import sys
from pathlib import Path
from typing import BinaryIO, Iterable, List, Optional, TextIO

from juniors_toolbox.objects.object import A_SceneObject, MapObject, ObjectFactory
from juniors_toolbox.rail import Rail, RalData
from juniors_toolbox.utils.iohelper import write_uint16, write_uint32

class SMSScene():
    BIN_PARAM_PATH = Path("Parameters")

    def __init__(self) -> None:
        self.reset()

    @classmethod
    def from_path(cls, scene: Path) -> Optional["SMSScene"]:
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
                obj = ObjectFactory.create_object_f(f)
                if obj is not None:
                    this._objects.append(obj)
        
        with railPath.open("rb") as f:
            this._raildata = RalData.from_bytes(f)

        with tablePath.open("rb") as f:
            _startPos = f.tell()
            f.seek(0, 2)
            end = f.tell()
            f.seek(_startPos, 0)

            while f.tell() < end:
                obj = ObjectFactory.create_object_f(f)
                if obj is not None:
                    this._tables.append(obj)

        return this

    def iter_objects(self, deep: bool = False) -> Iterable[A_SceneObject]:
        for obj in self._objects:
            yield obj
            if deep and obj.is_group():
                yield from obj.iter_grouped_children(deep=True)

    def get_object(self, name: str, desc: str) -> Optional[A_SceneObject]:
        for obj in self.iter_objects(True):
            if obj.get_ref() == name and obj.key.get_ref() == desc:
                return obj
        return None

    def iter_tables(self, deep: bool = False) -> Iterable[A_SceneObject]:
        for obj in self._tables:
            yield obj
            if deep and obj.is_group():
                yield from obj.iter_grouped_children(deep=True)

    def get_table(self, name: str, desc: str) -> Optional[A_SceneObject]:
        for obj in self.iter_tables(True):
            if obj.get_ref() == name and obj.key.get_ref() == desc:
                return obj
        return None
        
    def iter_rails(self) -> Iterable[Rail]:
        for rail in self._raildata.iter_rails():
            yield rail

    def get_rail(self, name: str) -> Optional[Rail]:
        for rail in self._raildata._rails:
            if rail.name == name:
                return rail
        return None

    def get_rail_by_index(self, idx: int) -> Optional[Rail]:
        try:
            return self._raildata._rails[idx]
        except IndexError:
            return None

    def set_rail(self, rail: Rail) -> None:
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

    def get_object_count(self) -> int:
        """
        Get the number of objects in this scene
        """
        i = 0
        for _ in self.iter_objects(deep=True):
            i += 1
        return i

    def get_unique_object_refs(self) -> list[str]:
        refs = []
        for obj in self.iter_objects(deep=True):
            if obj.get_ref() not in refs:
                refs.append(obj.get_ref())
        return refs

    def get_unique_object_manager_refs(self) -> list[str]:
        uniqueRefs = self.get_unique_object_refs()
        uniqueManagerRefs = []
        for ref in uniqueRefs:
            if ref.endswith("Manager"):
                uniqueManagerRefs.append(ref)
        return uniqueManagerRefs

    def get_table_count(self) -> int:
        i = 0
        for _ in self.iter_objects(deep=True):
            i += 1
        return i

    def get_unique_table_refs(self) -> list[str]:
        refs = []
        for obj in self.iter_tables(deep=True):
            if obj.get_ref() not in refs:
                refs.append(obj.get_ref())
        return refs

    def get_rail_count(self) -> int:
        """
        Get the number of rails in this scene
        """
        i = 0
        for _ in self.iter_rails():
            i += 1
        return i

    def save_objects(self, scene: Path) -> bool:
        if scene.suffix == ".bin":
            objPath = scene
        else:
            if not scene.is_dir():
                return False
            objPath = scene / "map/scene.bin"

        if not objPath.parent.exists():
            return False

        with objPath.open("wb") as f:
            for obj in self.iter_objects():
                f.write(obj.to_bytes())

        return True

    def reset(self) -> None:
        """
        Reset the scene back to an empty state
        """
        self._objects: List[A_SceneObject] = []
        self._tables: List[A_SceneObject] = []
        self._raildata = RalData()

    def dump(self, out: Optional[TextIO] = None, indentwidth: int = 2) -> None:
        """
        Dump a map of this scene to the stream `out`
        """
        if out is None:
            out = sys.stdout

        for obj in self.iter_objects():
            obj.print_map(
                out,
                indention=0,
                indentionWidth=indentwidth
            )
        for table in self.iter_tables():
            table.print_map(
                out,
                indention=0,
                indentionWidth=indentwidth
            )
        for rail in self.iter_rails():
            out.write(rail.name + "\n")

    def __contains__(self, other: A_SceneObject) -> bool:
        return other in self._objects