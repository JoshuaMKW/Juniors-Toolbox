from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
import json
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, Iterable, List, Optional, TextIO, Tuple, Union

from numpy import array
from juniors_toolbox.gui.templates import Template, ToolboxTemplates
from juniors_toolbox.objects.value import A_Member, MemberComment, MemberEnum, MemberStruct, MemberValue, QualifiedName, ValueType
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
        return f"{self.get_ref()} ({self.key})"

    def get_map_graph(self) -> str:
        header = f"{self.get_ref()} ({self.key})"
        body = ""
        for v in self.get_members():
            body += f"  {v.get_formatted_name()} = {v.get_value()}\n"
        return header + " {\n" + body + "}"

    def get_simple_data(self) -> bytes:
        data = BytesIO()
        write_uint32(data, self.get_data_size())
        data.write(super().to_bytes())
        data.write(self.key.to_bytes())
        data.write(self.get_member_data().getvalue())
        return data.getvalue()

    def get_simple_data_size(self) -> int:
        return 12 + len(self.get_ref()) + len(self.key) + len(self.get_member_data().getbuffer())

    def get_offset_of(self, name: QualifiedName, relative: bool = True) -> int:
        """
        Get the real offset of a member
        """
        def _member_offset(member: A_Member, offset: int) -> int:
            for child in member.get_children():
                if child.get_qualified_name() == name:
                    return offset
                if child.get_qualified_name().scopes(name):
                    return _member_offset(child, offset)
                offset += child.get_data_size()
            return -1

        offset = 0
        if not relative:
            data = BytesIO()
            write_uint32(data, self.get_data_size())
            data.write(super().to_bytes())
            data.write(self.key.to_bytes())
            offset += len(data.getvalue())

        for member in self.get_members():
            if member.get_qualified_name() == name:
                return offset
            if member.get_qualified_name().scopes(name):
                return _member_offset(member, offset)
            offset += member.get_data_size()
        return -1

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
                for i in range(child.get_array_size()):
                    arraychild = child[i]
                    if arraychild.get_qualified_name() == name:
                        return child
                    if arraychild.get_qualified_name().scopes(name):
                        return get(child, name)
            return None

        for member in self._members:
            if member.get_qualified_name() == name:
                return member
            child = get(member, name)
            if child is not None:
                return child

        return None

    def get_members(self, includeArrays: bool = True) -> Iterable[A_Member]:
        """
        Get the members of this object

        If `includeArrays` is true, also yield array-bound instances of each member
        """
        if includeArrays is False:
            for member in self._members:
                yield member
            return
        else:
            for member in self._members:
                for i in range(member.get_array_size()):
                    yield member[i]

    def get_member_by_index(self, index: int, arrayindex: int = 0) -> A_Member:
        """
        Return a `Value` at the specified index
        """
        return self._members[index][arrayindex]

    def set_member(self, name: QualifiedName, value: Any) -> bool:
        """
        Set a `Value` by name if it exists in this object

        Returns `True` if successful
        """
        if not self.has_member(name):
            return False

        for member in self.get_members():
            if member.get_qualified_name() == name:
                member.set_value(value)
                return True

        return False

    def set_member_by_index(self, index: int, value: Any, arrayindex: int = 0):
        """
        Set a member by index if it exists in this object
        """
        member = self._members[index][arrayindex]
        member.set_value(value)

    def get_member_data(self) -> BytesIO:
        """
        Get the raw data of this object's values
        """
        data = BytesIO()
        for member in self.get_members(includeArrays=False):
            if member.get_formatted_name() == "PoleLength" and self.get_ref() == "MapObjBase" and self.key.get_ref() != "AirportPole":
                continue
            member.save(data)
        return data

    def has_member(self, name: QualifiedName) -> bool:
        """
        Check if a named value exists in this object
        """
        for member in self._members:
            for i in range(member.get_array_size()):
                if member[i].get_qualified_name() == name:
                    return True

        return False

    def init_members(self, subkind: str = "Default") -> bool:
        """
        Initialize the members of this object from the json template data

        `subKind`: Subset of this obj used for unique Wizard entries

        Returns True if successful
        """
        self._members = []

        templateManager = ToolboxTemplates.get_instance()
        template = templateManager.get_template(self.get_ref())
        if template is None:
            return False

        wizardInfo = template.get_wizard(subkind)
        if wizardInfo is None:
            try:
                _iter = template.iter_wizards()
                wizardInfo = next(_iter)[1]
            except StopIteration:
                return False

        def _init_struct_member(name: str, template: Template, minfo: dict[str, Any], winfo: dict[str, Any]) -> A_Member:
            kind = ValueType(minfo["Type"].strip())
            defaultValue = winfo[name]

            repeat = minfo["ArraySize"]
            if isinstance(repeat, str):
                repeatRef = self.get_member(QualifiedName(repeat))
                if repeatRef is None:
                    raise ObjectCorruptedError(
                        f"Failed to find array reference `{repeat}` for object `{self.get_ref()}` (NOT FOUND)")
                if repeatRef.is_struct():
                    raise ObjectCorruptedError(
                        f"Failed to find array reference `{repeat}` for object `{self.get_ref()}` (NON VALUE)")
            else:
                repeatRef = repeat

            if kind == ValueType.UNKNOWN:
                memberStruct = MemberStruct(name)
                memberStruct.set_array_size(repeatRef)  # type: ignore
                memberType = minfo["Type"].strip()
                struct = template.get_struct(memberType)
                _enumInfo = template.get_enum(memberType)
                if struct is not None:
                    wizard = winfo[name]
                    for sname, sinfo in struct.items():
                        memberStruct.add_child(
                            _init_struct_member(sname, template, sinfo, wizard))
                    return memberStruct
                elif _enumInfo is not None:
                    memberEnum = MemberEnum(
                        name,
                        defaultValue,
                        ValueType.ENUM,
                        enumInfo=_enumInfo
                    )
                    memberEnum.set_array_size(repeatRef)  # type: ignore
                    return memberEnum
                else:
                    raise KeyError(
                        f"Type referenced by {self.get_ref()}::{name} does not exist! (Try adding it to Structs or Enums)")
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
                member.set_array_size(repeatRef)  # type: ignore

            return member

        for name, info in template.iter_members():
            self._members.append(_init_struct_member(
                name, template, info, wizardInfo))

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
            member = MemberStruct(memberName)
        elif type == ValueType.COMMENT:
            member = MemberComment(memberName, value)
        else:
            member = MemberValue(memberName, value, type)

        for i in range(100):
            parentMember = self.get_member(QualifiedName(*qualifiedName[:-1]))
            if parentMember is None:
                if not self.has_member(qualifiedName):
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

            member._name = f"{memberName}{i}"

        self._members.append(member)
        return member

    @abstractmethod
    def copy(self, *, deep: bool = False) -> "A_SceneObject": ...

    @abstractmethod
    def add_to_group(self, obj: "A_SceneObject", /):
        """
        Add an object as a child to this object
        """
        ...

    @abstractmethod
    def remove_from_group(self, obj: "A_SceneObject", /):
        """
        Remove a child object from this object
        """
        ...

    @abstractmethod
    def iter_grouped_children(
        self, *, deep: bool = False) -> Iterable["A_SceneObject"]: ...

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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(\"{self.get_ref()} ({self.key.get_ref()})\")"


class MapObject(A_SceneObject):
    """
    Class describing a map object
    """

    def __init__(self, nameref: str, subkind: str = "Default"):
        super().__init__(nameref, subkind)

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["MapObject"]:
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

        if objName.get_ref() == "CubeGeneralInfo":
            pass

        thisObj = cls(objName.get_ref())
        thisObj.key = objKey

        for member in thisObj.get_members(includeArrays=False):
            if member._type == ValueType.COMMENT:
                continue
            fileOffset = data.tell()
            if fileOffset >= objEndPos:
                break
            member.load(data, objEndPos)

        thisObj._parent = None
        return thisObj

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        return self.get_simple_data()

    def copy(self, *, deep: bool = False) -> "MapObject":
        cls = self.__class__

        _copy = cls(self.get_ref())
        _copy.key = self.key.copy(deep=deep)

        if self._parent:
            _copy._parent = self._parent

        for member in self.get_members():
            copyMember = _copy.get_member(member.get_qualified_name())
            if copyMember is not None:
                copyMember.set_value(member.get_value())
            else:
                _copy._members.append(member)

        return _copy

    def get_data_size(self) -> int:
        """
        Gets the length of this object in bytes
        """
        return self.get_simple_data_size()

    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        return False

    def add_to_group(self, obj: "A_SceneObject", /):
        raise ObjectGroupError(
            f"Cannot add an object ({obj.get_ref()}) to {self.get_ref()} which is not a Group Object!")

    def remove_from_group(self, obj: "A_SceneObject", /):
        raise ObjectGroupError(
            f"Cannot remove an object ({obj.get_ref()}) from {self.get_ref()} which is not a Group Object!")

    def iter_grouped_children(self, *, deep: bool = False) -> Iterable["A_SceneObject"]:
        return []

    def search(self, name: str, /) -> Optional["A_SceneObject"]:
        return None

    def print_map(self, out: TextIO, *, indention: int = 0, indentionWidth: int = 2):
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_ref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        for member in self.get_members():
            values += indentedStr + \
                f"  {member.get_formatted_name()} = {member._value}\n"
        out.write(values)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, A_SceneObject):
            nameEQ = super().__eq__(other)
            descEQ = self.key == other.key
            return nameEQ and descEQ
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, A_SceneObject):
            nameNEQ = super().__ne__(other)
            descNEQ = self.key != other.key
            return nameNEQ and descNEQ
        return NotImplemented

    def __contains__(self, other: Union[str, "MapObject"]) -> bool:
        return False

    def __hash__(self) -> int:
        return super().__hash__()


class GroupObject(A_SceneObject):
    def __init__(self, nameref: str, subkind: str = "Default"):
        super().__init__(nameref, subkind)
        self._grouped: List[A_SceneObject] = []

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

        thisObj = cls(objName.get_ref())
        thisObj.key = objKey

        nameHash = hash(thisObj)

        # GroupNum gets assigned to in the future load loop
        groupNum = thisObj.create_member(
            index=int(nameHash in {15406, 9858}),
            qualifiedName=QualifiedName("Grouped"),
            value=0,
            type=ValueType.U32,
            strict=True,
        )

        for member in thisObj.get_members(includeArrays=False):
            if member._type == ValueType.COMMENT:
                continue
            arraySize = member.get_array_size()
            arrayNum = 0
            for i in range(arraySize):
                if data.tell() >= objEndPos:
                    break
                member[i].load(data)
                arrayNum = i
            member.set_array_size(arrayNum+1)

        if groupNum is not None:
            groupNum._readOnly = True
            for _ in range(groupNum._value):
                if data.tell() >= objEndPos:
                    break
                obj = ObjectFactory.create_object_f(data)
                if obj is not None:
                    thisObj.add_to_group(obj)

        thisObj._parent = None
        return thisObj

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()
        data.write(self.get_simple_data())

        for obj in self._grouped:
            data.write(obj.to_bytes())

        return data.getvalue()

    def copy(self, *, deep: bool = False) -> "GroupObject":
        cls = self.__class__

        _copy = cls(self.get_ref())
        _copy.key = self.key.copy(deep=deep)

        if self._parent:
            _copy._parent = self._parent

        for child in self.iter_grouped_children():
            _copy.add_to_group(child.copy(deep=deep))

        for member in self.get_members():
            copyMember = _copy.get_member(member.get_qualified_name())
            if copyMember is not None:
                copyMember.set_value(member.get_value())
            else:
                _copy._members.append(member)

        return _copy

    def is_group(self) -> bool:
        return True

    def get_data_size(self) -> int:
        """
        Gets the length of this object in bytes
        """
        length = self.get_simple_data_size()
        for obj in self._grouped:
            length += obj.get_data_size()
        return length

    def add_to_group(self, obj: "A_SceneObject", /):
        self._grouped.append(obj)
        obj._parent = self
        self.set_member(QualifiedName("Grouped"), len(self._grouped))

    def remove_from_group(self, obj: "A_SceneObject", /):
        try:
            self._grouped.remove(obj)
            obj._parent = None
            self.set_member(QualifiedName("Grouped"), len(self._grouped))
        except ValueError:
            pass

    def iter_grouped_children(self, *, deep: bool = False) -> Iterable["A_SceneObject"]:
        """
        Yield all of the grouped objects
        """
        for g in self._grouped:
            yield g
            if deep and g.is_group():
                yield from g.iter_grouped_children(deep=True)

    def search(self, name: str, /) -> Optional["A_SceneObject"]:
        for subobj in self.iter_grouped_children():
            if super(A_SceneObject, subobj).__eq__(name):
                return subobj
        return None

    def print_map(self, out: TextIO, *, indention: int = 0, indentionWidth: int = 2):
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_ref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        for member in self.get_members():
            values += indentedStr + \
                f"  {member.get_formatted_name()} = {member._value}\n"
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

    def __contains__(self, other: Union[str, "A_SceneObject"]) -> bool:
        if not self.is_group():
            return False
        if isinstance(other, A_SceneObject):
            return other in self._grouped
        return any([g == other for g in self._grouped])

    def __hash__(self) -> int:
        return super().__hash__()


class ObjectFactory:
    @staticmethod
    def create_object(nameref: jdrama.NameRef, /) -> A_SceneObject:
        name = nameref.get_ref()
        if A_SceneObject.is_name_group(name):
            return GroupObject(name)
        return MapObject(name)

    @staticmethod
    def create_object_f(data: BinaryIO, /) -> Optional[A_SceneObject]:
        if A_SceneObject.is_data_group(data):
            return GroupObject.from_bytes(data)
        return MapObject.from_bytes(data)
