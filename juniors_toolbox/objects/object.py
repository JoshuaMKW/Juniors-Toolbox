from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, TextIO, Tuple, Union
from attr import field

from numpy import array
from juniors_toolbox.objects.value import A_Member, MemberComment, MemberStruct, MemberValue, QualifiedName, ValueType
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Transform, Vec3f
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs, jdrama
from juniors_toolbox.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16, write_uint32


class ObjectGroupError(Exception):
    ...


class ObjectCorruptedError(Exception):
    ...


class A_SceneObject(jdrama.NameRef, ABC):
    """
    Class describing a generic scene object
    """
    TEMPLATE_PATH = Path("Templates")
    
    _KNOWN_GROUP_HASHES = {
        16824, 15406, 28318, 18246,
        43971, 9858, 25289,  # levels
        33769, 49941, 13756, 65459,
        38017, 47488,  # tables
        8719, 22637
    }

    @staticmethod
    def is_data_group(data: BinaryIO) -> bool:
        _pos = data.tell()
        data.seek(4, 1)
        nhash = read_uint16(data)
        data.seek(_pos, 0)
        return nhash in A_SceneObject._KNOWN_GROUP_HASHES

    @staticmethod
    def is_name_group(name: str) -> bool:
        return jdrama.get_key_code(name) in A_SceneObject._KNOWN_GROUP_HASHES

    def __init__(self, nameref: str, subkind: str = "Default"):
        super().__init__(nameref)
        self.key = jdrama.NameRef("(null)")
        self._members: List[A_Member] = []
        self._parent: Optional[GroupObject] = None

        self.init_members(subkind)

    def get_explicit_name(self) -> str:
        """
        Return the described name of this object
        """
        return f"{self.get_nameref()} ({self.key})"

    def get_map_graph(self) -> str:
        header = f"{self.get_nameref()} ({self.key})"
        body = ""
        for v in self.get_members():
            body += f"  {v.name} = {v.value}\n"
        return header + " {\n" + body + "}"

    def get_parent(self) -> Optional["GroupObject"]:
        """
        Get this object's parent group object
        """
        return self._parent

    def get_member(self, name: QualifiedName) -> Optional[A_Member]:
        """
        Get a `Value` by name from this object
        """
        def get(member: A_Member, name: QualifiedName) -> Optional[A_Member]:
            for child in member.get_children():
                if child.get_qualified_name() == name:
                    return child
                if child.get_qualified_name().scopes(name):
                    return get(child, name)
            return None

        for member in self._members:
            m = get(member, name)
            if m is not None:
                return m

        return None

    def get_members(self) -> Iterable[A_Member]:
        return self._members

    def get_member_by_index(self, index: int) -> A_Member:
        """
        Return a `Value` at the specified index
        """
        return self._members[index]

    def set_member(self, attrname: str, value: Any) -> bool:
        """
        Set a `Value` by name if it exists in this object

        Returns `True` if successful
        """

        attrname = attrname.strip()

        if not self.has_member(attrname):
            return False

        for val in self._members:
            if val.name == attrname:
                val.value = value
                return True
        return False

    def set_member_by_index(self, index: int, value: Any):
        """
        Set a member by index if it exists in this object
        """
        val = self._members[index]
        val.value = value

    def get_member_data(self) -> BytesIO:
        """
        Get the raw data of this object's values
        """
        data = BytesIO()
        for member in self.get_members():
            member.save(data)
        return data

    def has_member(self, membername: str) -> bool:
        """
        Check if a named value exists in this object
        """
        return any(membername == m.name for m in self._members)

    def init_members(self, subkind: str = "Default") -> bool:
        """
        Initialize the members of this object from the json template data

        `subKind`: Subset of this obj used for unique Wizard entries

        Returns True if successful
        """
        self._members = []

        templateFile = self.TEMPLATE_PATH / f"{self.get_nameref()}.json"
        if not templateFile.is_file():
            return False

        with templateFile.open("r") as tf:
            templateInfo: dict = json.load(tf)

        objname, objdata = templateInfo.popitem()
        memberInfo: Dict[str, dict] = objdata["Members"]
        wizardInfo: Dict[str, dict] = objdata["Wizard"]

        for name, info in memberInfo.items():
            kind = ValueType(info["Type"].strip())
            repeat = info["ArraySize"]
            defaultValue = wizardInfo[subkind][name]

            if kind == ValueType.STRUCT:
                ...
            else:

                if kind == ValueType.TRANSFORM:
                    defaultValue = Transform(
                        Vec3f(*defaultValue[0]),
                        Vec3f(*defaultValue[1]),
                        Vec3f(*defaultValue[2])
                    )
                elif kind == ValueType.VECTOR3:
                    defaultValue = Vec3f(*defaultValue)
                elif kind == ValueType.C_RGB8:
                    defaultValue = RGB8.from_tuple(defaultValue)
                elif kind == ValueType.C_RGBA8:
                    defaultValue = RGBA8.from_tuple(defaultValue)
                elif kind == ValueType.C_RGB32:
                    defaultValue = RGB32.from_tuple(defaultValue)

                member = MemberValue(
                    name, defaultValue, kind
                )

            self._members.append(member)

        return True

    def create_member(
        self, *,
        index: int,
        qualifiedName: QualifiedName,
        value: Any,
        type: ValueType,
        strict: bool = False
    ) -> Optional[A_Member]:
        """
        Create a named value for this object if it doesn't exist

        Returns the created member or None if it already exists

        `strict`: If true, disallow enumerating the name for unique values
        """
        if value is None:
            return None

        memberName = qualifiedName[-1]
        member: A_Member
        if type == ValueType.STRUCT:
            member = MemberStruct(memberName, value)
        elif type == ValueType.COMMENT:
            member = MemberComment(memberName, value)
        else:
            member = MemberValue(memberName, value, type)

        for i in range(100):
            parentMember = self.get_member(QualifiedName(*qualifiedName[:-1]))
            member.name = memberName
            if parentMember is None:
                if not self.has_member(memberName):
                    if index != -1:
                        self._members.insert(index, member)
                    else:
                        self._members.append(member)
                    return member
            else:
                if not parentMember.has_child(memberName):
                    parentMember.add_child(member)
                    return member

            if strict:
                return None

            member.name = f"{memberName}{i}"

        self._members.append(member)
        return member

    @abstractmethod
    def add_to_group(self, obj: "BaseObject", /):
        """
        Add an object as a child to this object
        """
        ...

    @abstractmethod
    def remove_from_group(self, obj: "BaseObject", /):
        """
        Remove a child object from this object
        """
        ...

    @abstractmethod
    def iter_grouped_children(
        self, *, deep: bool = False) -> Iterable["BaseObject"]: ...

    @abstractmethod
    def get_data_size(self) -> int: ...

    @abstractmethod
    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        ...

    @abstractmethod
    def print_map(self, out: TextIO, *, indention: int = 0, indentionWidth: int = 2):
        """
        Print a complete map of this object to `out`
        """
        ...
        

class BaseObject(A_SceneObject):
    """
    Class describing a generic game object
    """

    def __init__(self, nameref: str):
        super().__init__(nameref)

        self._grouped: List[BaseObject] = []

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["BaseObject"]:
        objLength = read_uint32(data)
        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objName = jdrama.NameRef.from_bytes(data)
        if objName is None:
            return None

        # -- Desc -- #
        objKey = jdrama.NameRef.from_bytes(data)
        if objKey is None:
            return None

        thisObj = cls(objName.get_nameref())
        thisObj.key = objKey

        for member in thisObj.get_members():
            member.load(data)

        thisObj._parent = None
        return thisObj

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()
        nameref = self.get_nameref()
        keyref = self.key.get_nameref()

        write_uint32(data, self.get_data_size())
        write_uint16(data, hash(nameref))
        write_uint16(data, len(nameref))
        write_string(data, nameref)
        write_uint16(data, hash(keyref))
        write_uint16(data, len(keyref))
        write_string(data, keyref)
        data.write(self.get_member_data().getvalue())

        return data.getvalue()

    def copy(self, *, deep: bool = False) -> "BaseObject":
        cls = self.__class__

        _copy = cls(self.get_nameref())
        _copy.key = self.key.copy(deep=deep)

        if self._parent:
            _copy._parent = self._parent.copy(deep=deep)

        for i, member in enumerate(self.get_members()):
            if deep:
                self.create_member(
                    index=i,
                    qualifiedName=member.get_qualified_name(),
                    value=member.value,
                    type=member.type,
                    strict=True
                )
            else:
                self._members.append(member)
        
        return _copy

    def clone(self) -> "BaseObject":
        """
        Creates a copy of this object
        """
        obj = BaseObject(self.get_nameref())
        obj.key = jdrama.NameRef(self.key.get_nameref())
        obj._parent = self._parent
        obj._grouped = self._grouped.copy()
        return obj

    def get_data_size(self) -> int:
        """
        Gets the length of this object in bytes
        """
        return 12 + len(self.get_nameref()) + len(self.key) + len(self.get_member_data().getbuffer())

    def is_value(self, attrname: str) -> bool:
        """
        Check if a named value exists in this object
        """
        return any(attrname == v.name for v in self._members)

    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        return False

    def add_to_group(self, obj: "BaseObject", /):
        raise ObjectGroupError(
            f"Cannot add an object ({obj.get_nameref()}) to {self.get_nameref()} which is not a Group Object!")

    def remove_from_group(self, obj: "BaseObject", /):
        raise ObjectGroupError(
            f"Cannot remove an object ({obj.get_nameref()}) from {self.get_nameref()} which is not a Group Object!")

    def iter_grouped_children(self, *, deep: bool = False) -> Iterable["BaseObject"]:
        return []

    def search(self, name: str, /) -> Optional["BaseObject"]:
        return None

    def print_map(self, out: TextIO, *, indention: int = 0, indentionWidth: int = 2):
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_nameref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        for member in self.get_members():
            values += indentedStr + f"  {member.name} = {member.value}\n"
        out.write(values)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseObject):
            nameEQ = super().__eq__(other)
            descEQ = self.key == other.key
            return nameEQ and descEQ
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, BaseObject):
            nameNEQ = super().__ne__(other)
            descNEQ = self.key != other.key
            return nameNEQ and descNEQ
        return NotImplemented

    def __contains__(self, other: Union[str, "BaseObject"]) -> bool:
        return False


class GroupObject(BaseObject):
    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["GroupObject"]:
        objLength = read_uint32(data)
        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objName = jdrama.NameRef.from_bytes(data)
        if objName is None:
            return None

        # -- Desc -- #
        objKey = jdrama.NameRef.from_bytes(data)
        if objKey is None:
            return None

        thisObj = cls(objName.get_nameref())
        thisObj.key = objKey

        nameHash = hash(thisObj.get_nameref())

        # GroupNum gets assigned to in the future load loop
        groupNum = thisObj.create_member(
            index=int(nameHash in {15406, 9858}),
            qualifiedName=QualifiedName("Grouped"),
            value=0,
            type=ValueType.U32,
            strict=True,
        )

        for member in thisObj.get_members():
            member.load(data)

        if groupNum is not None:
            for _ in range(groupNum.value):
                obj = BaseObject.from_bytes(data)
                if obj is not None:
                    thisObj.add_to_group(obj)

        thisObj._parent = None
        return thisObj

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()
        nameref = self.get_nameref()
        keyref = self.key.get_nameref()

        write_uint32(data, self.get_data_size())
        write_uint16(data, hash(nameref))
        write_uint16(data, len(nameref))
        write_string(data, nameref)
        write_uint16(data, hash(keyref))
        write_uint16(data, len(keyref))
        write_string(data, keyref)
        data.write(self.get_member_data().getvalue())

        write_uint32(data, len(self._grouped))
        for obj in self._grouped:
            data.write(obj.to_bytes())

        return data.getvalue()

    def copy(self, *, deep: bool = False) -> "GroupObject":
        cls = self.__class__

        _copy = cls(self.get_nameref())
        _copy.key = self.key.copy(deep=deep)
        
        if self._parent:
            _copy._parent = self._parent.copy(deep=deep)

        for child in self.iter_grouped_children():
            if deep:
                self.add_to_group(child.copy(deep=True))
            self.add_to_group(child)

        for i, member in enumerate(self.get_members()):
            if deep:
                self.create_member(
                    index=i,
                    qualifiedName=member.get_qualified_name(),
                    value=member.value,
                    type=member.type,
                    strict=True
                )
            else:
                self._members.append(member)
        
        return _copy

    def is_group(self) -> bool:
        return True

    def get_data_size(self) -> int:
        """
        Gets the length of this object in bytes
        """
        length = 12 + len(self.get_nameref()) + len(self.key) + len(self.get_member_data().getbuffer())
        for obj in self._grouped:
            length += obj.get_data_size()
        return length

    def add_to_group(self, obj: "BaseObject", /):
        self._grouped.append(obj)
        obj._parent = self

    def remove_from_group(self, obj: "BaseObject", /):
        try:
            self._grouped.remove(obj)
            obj._parent = None
        except ValueError:
            pass

    def iter_grouped_children(self, *, deep: bool = False) -> Iterable["BaseObject"]:
        """
        Yield all of the grouped objects
        """
        for g in self._grouped:
            yield g
            if deep and g.is_group():
                yield from g.iter_grouped_children()

    def search(self, name: str, /) -> Optional["BaseObject"]:
        for subobj in self.iter_grouped_children():
            if super(BaseObject, subobj).__eq__(name):
                return subobj
        return None

    def print_map(self, out: TextIO, *, indention: int = 0, indentionWidth: int = 2):
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_nameref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        for member in self.get_members():
            values += indentedStr + f"  {member.name} = {member.value}\n"
        out.write(values)
        if self.is_group():
            out.write("\n" + indentedStr + "  [Grouped]\n")
            for g in self.iter_grouped_children():
                g.print_map(
                    out,
                    indention=indention+1,
                    indentionWidth=indentionWidth
                )
                out.write("\n")
        out.write(indentedStr + "}")

    def __contains__(self, other: Union[str, "BaseObject"]) -> bool:
        if not self.is_group():
            return False
        if isinstance(other, BaseObject):
            return other in self._grouped
        return any([g == other for g in self._grouped])


class ObjectFactory:
    @staticmethod
    def create_object(nameref: jdrama.NameRef, /) -> A_SceneObject:
        name = nameref.get_nameref()
        if A_SceneObject.is_name_group(name):
            return GroupObject(name)
        return BaseObject(name)

    @staticmethod
    def create_object_f(data: BinaryIO, /) -> Optional[A_SceneObject]:
        if A_SceneObject.is_data_group(data):
            return GroupObject.from_bytes(data)
        return BaseObject.from_bytes(data)