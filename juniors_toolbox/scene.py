import sys
from pathlib import Path
from typing import BinaryIO, Iterable, List, Optional, TextIO

from juniors_toolbox.objects.object import A_SceneObject, ObjectFactory
from juniors_toolbox.rail import Rail, RalData
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.jdrama import NameRef


class ObjectHierarchy(A_Serializable):
    def __init__(self) -> None:
        self.reset()

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **
                   kwargs: VariadicKwargs) -> Optional["ObjectHierarchy"]:
        this = cls()

        _startPos = data.tell()
        data.seek(0, 2)
        end = data.tell()
        data.seek(_startPos, 0)

        while data.tell() < end:
            obj = ObjectFactory.create_object_f(data)
            if obj is not None:
                this._objects.append(obj)

    def to_bytes(self) -> bytes:
        data = b""
        for obj in self._objects:
            data += obj.to_bytes()
        return data

    def iter_objects(self, deep: bool = False) -> Iterable[A_SceneObject]:
        """
        Iterate over all objects in this hierarchy
        """
        for obj in self._objects:
            yield obj
            if deep and obj.is_group():
                yield from obj.iter_grouped_children(deep=True)

    def get_object(self, name: str, desc: str) -> Optional[A_SceneObject]:
        """
        Get an object by its name and description
        """
        for obj in self.iter_objects(True):
            if obj.get_ref() == name and obj.key.get_ref() == desc:
                return obj
        return None

    def add_object(self, obj: A_SceneObject, parent: Optional[A_SceneObject] = None) -> None:
        """
        Add an object to this hierarchy
        """
        if parent is None:
            self._objects.append(obj)
        else:
            parent.add_to_group(obj)

    def remove_object(self, name: str, desc: str) -> None:
        """
        Remove an object by its name and description
        """
        for obj in self.iter_objects(True):
            if obj.get_ref() == name and obj.key.get_ref() == desc:
                self._objects.remove(obj)
                return

    def get_object_count(self) -> int:
        """
        Get the number of objects in this hierarchy
        """
        return sum(1 for _ in self.iter_objects(deep=True))

    def get_unique_object_refs(self, *, alphanumeric: bool = False) -> list[str]:
        """
        Get a list of unique object references in this hierarchy
        """
        refs = []
        for obj in self.iter_objects(deep=True):
            if obj.get_ref() not in refs:
                refs.append(obj.get_ref())
        if alphanumeric:
            refs.sort()
        return refs

    def reset(self) -> None:
        self._objects: List[A_SceneObject] = []


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

        objPath = scene / "map/scene.bin"
        tablePath = scene / "map/tables.bin"
        railPath = scene / "map/scene.ral"

        this = cls()

        if not objPath.exists() or not tablePath.exists() or not railPath.exists():
            return None

        with objPath.open("rb") as f:
            this._objects = ObjectHierarchy.from_bytes(f)

        with tablePath.open("rb") as f:
            this._tables = ObjectHierarchy.from_bytes(f)

        with railPath.open("rb") as f:
            this._raildata = RalData.from_bytes(f)

        return this

    def to_path(self, scene: Path) -> bool:
        """
        Write the scene to a folder
        """
        if not scene.is_dir():
            return False

        objPath = scene / "map/scene.bin"
        tablePath = scene / "map/tables.bin"
        railPath = scene / "map/scene.ral"

        with objPath.open("wb") as f:
            f.write(self._objects.to_bytes())

        with tablePath.open("wb") as f:
            f.write(self._tables.to_bytes())

        with railPath.open("wb") as f:
            f.write(self._raildata.to_bytes())

        return True

    def get_object_hierarchy(self) -> ObjectHierarchy:
        return self._objects

    def get_table_hierarchy(self) -> ObjectHierarchy:
        return self._tables

    def get_rail_data(self) -> RalData:
        return self._raildata

    def get_unique_manager_refs(self, *, alphanumeric: bool = False) -> list[str]:
        """
        Get a list of unique manager references in this scene
        """
        uniqueRefs = self.get_unique_object_refs(alphanumeric=alphanumeric)
        uniqueManagerRefs = []
        for ref in uniqueRefs:
            if ref.endswith("Manager"):
                uniqueManagerRefs.append(ref)
        return uniqueManagerRefs

    def save_objects(self, scene: Path) -> bool:
        """
        Save the objects in this scene to the given path
        """
        if scene.suffix == ".bin":
            objPath = scene
        else:
            if not scene.is_dir():
                return False
            objPath = scene / "map/scene.bin"

        if not objPath.parent.exists():
            return False

        with objPath.open("wb") as f:
            f.write(super().to_bytes())

        return True

    def save_tables(self, scene: Path) -> bool:
        """
        Save the tables in this scene to the given path
        """
        if scene.suffix == ".bin":
            tablePath = scene
        else:
            if not scene.is_dir():
                return False
            tablePath = scene / "map/tables.bin"

        if not tablePath.parent.exists():
            return False

        with tablePath.open("wb") as f:
            for obj in self.iter_tables(deep=True):
                f.write(obj.to_bytes())

        return True

    def save_rails(self, scene: Path) -> bool:
        """
        Save the rails in this scene to the given path
        """
        if scene.suffix == ".ral":
            railPath = scene
        else:
            if not scene.is_dir():
                return False
            railPath = scene / "map/scene.ral"

        if not railPath.parent.exists():
            return False

        with railPath.open("wb") as f:
            f.write(self._raildata.to_bytes())

        return True

    def reset(self) -> None:
        """
        Reset the scene back to an empty state
        """
        self._objects: ObjectHierarchy = ObjectHierarchy()
        self._tables: ObjectHierarchy = ObjectHierarchy()
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
