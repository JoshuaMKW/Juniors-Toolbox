from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from pipes import Template
from struct import Struct
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, TextIO, Tuple, Union
from attr import field

from numpy import array
from juniors_toolbox.objects.template import ValueType
from juniors_toolbox.objects.value import A_Member, MemberComment, MemberStruct, MemberValue, QualifiedName
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Transform, Vec3f
from juniors_toolbox.utils import A_Serializable, jdrama
from juniors_toolbox.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16, write_uint32

KNOWN_GROUP_HASHES = {
    16824, 15406, 28318, 18246,
    43971, 9858, 25289,  # levels
    33769, 49941, 13756, 65459,
    38017, 47488,  # tables
    8719, 22637
}


class ObjectGroupError(Exception):
    ...


class ObjectCorruptedError(Exception):
    ...


class A_SceneObject(jdrama.NameRef, ABC):
    """
    Class describing a generic scene object
    """
    TEMPLATE_PATH = Path("Templates")

    def __init__(self, nameref: str, subkind: str = "Default"):
        super().__init__(nameref)
        self.key = jdrama.NameRef("(null)")
        self._members: List[A_Member] = []
        self._parent: A_SceneObject = None

        self.init_members(subkind)

    def get_map_graph(self) -> str:
        header = f"{self.get_nameref()} ({self.key})"
        body = ""
        for v in self.get_members():
            body += f"  {v[0]} = {v[1]}\n"
        return header + " {\n" + body + "}"

    def get_parent(self) -> "GroupObject":
        """
        Get this object's parent group object
        """
        return self._parent

    def get_members(self) -> Iterable[A_Member]:
        return self._members

    def get_member_data(self) -> BytesIO:
        """
        Get the raw data of this object's values
        """
        data = BytesIO()
        for member in self.iter_values():
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

    def get_member(self, attrname: str) -> A_Member:
        """
        Get a `Value` by name from this object
        """
        attrname = attrname.strip()

        for member in self._members:
            if member.name == attrname:
                return member

    def get_member_by_index(self, index: int) -> A_Member:
        """
        Return a `Value` at the specified index
        """
        return self._members[index]

    def set_member(self, attrname: str, value: object) -> bool:
        """
        Set a `Value` by name if it exists in this object

        Returns `True` if successful
        """

        attrname = attrname.strip()

        if not self.has_member(attrname):
            return False

        for val in self._members:
            if val.name == attrname:
                klass = val.type.to_type()
                if issubclass(klass, Vec3f):
                    val.value = value
                else:
                    val.value = klass(value)
                return True
        return False

    def set_member_by_index(self, index: int, value: object):
        """
        Set a member by index if it exists in this object
        """
        val = self._members[index]
        klass = val.type.to_type()
        if issubclass(klass, Vec3f):
            val.value = value
        else:
            val.value = klass(value)

    def create_member(
        self, *,
        index: int,
        qualifiedName: QualifiedName,
        value: object,
        type: ValueType,
        strict: bool = False
    ) -> A_Member:
        """
        Create a named value for this object if it doesn't exist

        Returns the created member or None if it already exists

        `strict`: If true, disallow enumerating the name for unique values
        """
        if value is None:
            return None

        memberName = qualifiedName[-1]
        if type == ValueType.STRUCT:
            member = MemberStruct(qualifiedName[-1], value, type)
        elif type == ValueType.COMMENT:
            member = MemberComment(qualifiedName[-1], value, type)
        else:
            member = MemberValue(qualifiedName[-1], value, type)

        for i in range(100):
            parentMember: MemberStruct = self.get_member(qualifiedName[:-1])
            if parentMember is None:
                if not self.has_member(memberName):
                    if index != -1:
                        self._members.insert(index, member)
                    else:
                        self._members.append(member)
                    return member
            else:
                if parentMember.has_child(memberName):
                    parentMember._children[memberName] = member
                    return member

            if strict:
                return None

            member.name = f"{qualifiedName[-1]}{i}"

    def get_member(self, name: QualifiedName) -> A_Member:
        def get(member: A_Member, name: QualifiedName) -> A_Member:
            for child in member.get_children():
                if child.get_qualified_name() == name:
                    return child
                if child.get_qualified_name().scopes(name):
                    return get(child, name)
            return None

        for member in self._members:
            m = get(self, member, name)
            if m is not None:
                return m

        return None

    @abstractmethod
    def add_to_group(self, obj: "BaseObject"):
        """
        Add an object as a child to this object
        """
        ...

    @abstractmethod
    def remove_from_group(self, obj: "BaseObject"):
        """
        Remove a child object from this object
        """
        ...

    @abstractmethod
    def iter_grouped_children(
        self, deep: bool = False) -> Iterable["BaseObject"]: ...

    @abstractmethod
    def get_data_size(self) -> int: ...

    @abstractmethod
    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
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
    def from_bytes(cls, data: BinaryIO, *args, **kwargs):
        objLength = read_uint32(data)
        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objNameHash = read_uint16(data)
        objNameLength = read_uint16(data)

        objName = jdrama.NameRef(read_string(data, maxlen=objNameLength-1))

        if hash(objName) != objNameHash or len(objName.encode()) != objNameLength:
            raise ObjectCorruptedError(
                f"Object name is corrupted! {hash(objName)} ({objName}) != {objNameHash}")

        # -- Desc -- #
        objDescHash = read_uint16(data)
        objDescLength = read_uint16(data)

        objDesc = jdrama.NameRef(read_string(
            data, maxlen=objDescLength-1, encoding="shift-jis"))

        if hash(objDesc) != objDescHash or len(objDesc.encode("shift-jis")) != objDescLength:
            raise ObjectCorruptedError(
                f"Object desc is corrupted! {hash(objDesc)} ({objDesc}) != {objDescHash}")

        thisObj = cls(objName)
        thisObj.key = objDesc

        # -- Template Specific -- #
        template = ObjectTemplate.from_template(
            ObjectTemplate.TEMPLATE_PATH / f"{thisObj.get_nameref}.json"
        )

        if template is None:
            template = ObjectTemplate()

        nameHash = hash(thisObj.name)
        if nameHash in KNOWN_GROUP_HASHES:
            template.add_attribute(ObjectAttribute(
                "Grouped", ValueType.U32), int(nameHash in {15406, 9858}))

        def gen_attr(attr: ObjectAttribute, nestedNamePrefix: str = "") -> dict:
            def construct(index: int) -> dict:
                char = "abcdefghijklmnopqrstuvwxyz"[index]
                name = attr.get_formatted_name(char, index)

                if isStruct:
                    for subattr in attr.iter_attributes():
                        for attrdata in gen_attr(subattr, f"{nestedNamePrefix}{name}."):
                            thisObj.create_member(
                                attrdata["index"],
                                attrdata['name'],
                                attrdata["value"],
                                attrdata["type"],
                                attrdata["comment"]
                            )

                else:
                    instances.append({
                        "index": -1,
                        "name": f"{nestedNamePrefix}{name}",
                        "value": attr.read_from(data),
                        "type": attr.type,
                        "comment": attr.comment
                    })

            isStruct = attr.is_struct()
            if attr.is_count_referenced():
                count = thisObj.get_value(attr.countRef.name).value
            else:
                count = attr.countRef

            instances = []
            if count == -1:
                i = 0
                while data.tell() < objEndPos:
                    x = data.tell()
                    construct(i)
                    i += 1
                return instances

            for i in range(count):
                if data.tell() >= objEndPos:
                    break
                construct(i)
            return instances

        for attribute in template.iter_attributes():
            for attrdata in gen_attr(attribute):
                thisObj.create_member(
                    attrdata["index"],
                    attrdata["name"],
                    attrdata["value"],
                    attrdata["type"],
                    attrdata["comment"]
                )

        groupNum = thisObj.get_value("Grouped")
        if nameHash in KNOWN_GROUP_HASHES and groupNum is not None:
            for _ in range(groupNum.value):
                thisObj.add_to_group(BaseObject.from_bytes(data))

        thisObj._parent = None
        return thisObj

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()

        write_uint32(data, self.get_data_length())
        write_uint16(data, hash(self))
        write_uint16(data, len(self.get_nameref()))
        write_string(data, self.get_nameref())
        write_uint16(data, hash(self.key))
        write_uint16(data, len(self.key))
        write_string(data, self.key)
        data.write(self.get_member_data().getvalue())

        if hash(self) in KNOWN_GROUP_HASHES:
            write_uint32(data, len(self._grouped))
            for obj in self._grouped:
                data.write(obj.to_bytes())

        return data.getvalue()

    def copy(self, *, deep: bool = False) -> "A_SceneObject":
        cls = self.__class__

        _copy = cls(self.get_nameref())
        _copy.key = self.key.copy(deep=deep)
        _copy._parent = self._parent.copy(deep=deep)
        if deep:
            ...

    def clone(self) -> "BaseObject":
        """
        Creates a copy of this object
        """
        obj = BaseObject(self.get_nameref())
        obj.key = jdrama.NameRef(self.key)
        obj._parent = self._parent
        obj._grouped = self._grouped.copy()
        return obj

    def get_data_length(self) -> int:
        """
        Gets the length of this object in bytes
        """
        return 12 + len(self.get_nameref()) + len(self.key) + len(self.data)

    def is_value(self, attrname: str) -> bool:
        """
        Check if a named value exists in this object
        """
        return any(attrname == v.name for v in self._values)

    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        return False

    def add_to_group(self, obj: "BaseObject"):
        raise ObjectGroupError(
            f"Cannot add an object ({obj.get_nameref()}) to {self.get_nameref()} which is not a Group Object!")

    def remove_from_group(self, obj: "BaseObject"):
        raise ObjectGroupError(
            f"Cannot remove an object ({obj.get_nameref()}) from {self.get_nameref()} which is not a Group Object!")

    def iter_grouped_children(self, deep: bool = False) -> Iterable["BaseObject"]:
        return []

    def search(self, name: str) -> "BaseObject":
        return None

    def print_map(self, out: TextIO, indention: int = 0, indentionWidth: int = 2):
        """
        Print a complete map of this object to `out`
        """
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_nameref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        with open("sussy.baka", "a") as f:
            f.write(self.get_nameref() + "\n")
            for v in self.get_member():
                f.write(f" {v[0]} {v[1]}\n")
                values += indentedStr + f"  {v[0]} = {v[1]}\n"
        out.write(values + indentedStr + "}")

    def get_explicit_name(self) -> str:
        """
        Return the described name of this object
        """
        return f"{self.get_nameref()} ({self.key})"

    def __eq__(self, other: "BaseObject") -> bool:
        nameEQ = super().__eq__(other)
        descEQ = self.key == other.key
        return nameEQ and descEQ

    def __ne__(self, other: "BaseObject") -> bool:
        nameNEQ = super().__ne__(other)
        descNEQ = self.key != other.key
        return nameNEQ and descNEQ

    def __contains__(self, other: Union[str, "BaseObject"]) -> bool:
        return False


class GroupObject(BaseObject):
    @classmethod
    def from_bytes(cls, data: BinaryIO, *args, **kwargs):
        objLength = read_uint32(data)
        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objNameHash = read_uint16(data)
        objNameLength = read_uint16(data)

        objName = jdrama.NameRef(read_string(data, maxlen=objNameLength-1))

        if hash(objName) != objNameHash or len(objName.encode()) != objNameLength:
            raise ObjectCorruptedError(
                f"Object name is corrupted! {hash(objName)} ({objName}) != {objNameHash}")

        # -- Desc -- #
        objDescHash = read_uint16(data)
        objDescLength = read_uint16(data)

        objDesc = jdrama.NameRef(read_string(
            data, maxlen=objDescLength-1, encoding="shift-jis"))

        if hash(objDesc) != objDescHash or len(objDesc.encode("shift-jis")) != objDescLength:
            raise ObjectCorruptedError(
                f"Object desc is corrupted! {hash(objDesc)} ({objDesc}) != {objDescHash}")

        thisObj = cls(objName)
        thisObj.key = objDesc

        nameHash = hash(thisObj)
        if nameHash in KNOWN_GROUP_HASHES:
            thisObj.create_member(
                index=int(nameHash in {15406, 9858}),
                qualifiedName=QualifiedName("Grouped"),
                value=0,
                type=ValueType.U32,
                strict=True,
            )

        def gen_attr(attr: ObjectAttribute, nestedNamePrefix: str="") -> dict:
            def construct(index: int) -> dict:
                char="abcdefghijklmnopqrstuvwxyz"[index]
                name=attr.get_formatted_name(char, index)

                if isStruct:
                    for subattr in attr.iter_attributes():
                        for attrdata in gen_attr(subattr, f"{nestedNamePrefix}{name}."):
                            thisObj.create_member(
                                attrdata["index"],
                                attrdata['name'],
                                attrdata["value"],
                                attrdata["type"],
                                attrdata["comment"]
                            )

                else:
                    instances.append({
                        "index": -1,
                        "name": f"{nestedNamePrefix}{name}",
                        "value": attr.read_from(data),
                        "type": attr.type,
                        "comment": attr.comment
                    })

            isStruct = attr.is_struct()
            if attr.is_count_referenced():
                count = thisObj.get_value(attr.countRef.name).value
            else:
                count = attr.countRef

            instances = []
            if count == -1:
                i = 0
                while data.tell() < objEndPos:
                    x = data.tell()
                    construct(i)
                    i += 1
                return instances

            for i in range(count):
                if data.tell() >= objEndPos:
                    break
                construct(i)
            return instances

        for attribute in template.iter_attributes():
            for attrdata in gen_attr(attribute):
                thisObj.create_member(
                    attrdata["index"],
                    attrdata["name"],
                    attrdata["value"],
                    attrdata["type"],
                    attrdata["comment"]
                )

        groupNum = thisObj.get_value("Grouped")
        if nameHash in KNOWN_GROUP_HASHES and groupNum is not None:
            for _ in range(groupNum.value):
                thisObj.add_to_group(BaseObject.from_bytes(data))

        thisObj._parent = None
        return thisObj

    def is_group(self) -> bool:
        return True

    def get_data_length(self) -> int:
        """
        Gets the length of this object in bytes
        """
        length = 12 + len(self.get_nameref()) + len(self.key) + len(self.data)
        for obj in self._grouped:
            length += obj.get_data_length()
        return length

    def add_to_group(self, obj: "BaseObject"):
        self._grouped.append(obj)
        obj._parent = self

    def remove_from_group(self, obj: "BaseObject"):
        try:
            self._grouped.remove(obj)
            obj._parent = None
        except ValueError:
            pass

    def iter_grouped_children(self, deep: bool = False) -> Iterable["BaseObject"]:
        """
        Yield all of the grouped objects
        """
        for g in self._grouped:
            yield g
            if deep and g.is_group():
                yield from g.iter_grouped_children()

    def search(self, name: str) -> "BaseObject":
        for subobj in self.iter_grouped_children():
            if super(BaseObject, subobj).__eq__(name):
                return subobj

    def print_map(self, out: TextIO, indention: int = 0, indentionWidth: int = 2):
        """
        Print a complete map of this object to `out`
        """
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.get_nameref()} ({self.key})" + " {\n")
        values = indentedStr + "  [Values]\n"
        with open("sussy.baka", "a") as f:
            f.write(self.get_nameref() + "\n")
            for v in self.iter_values():
                f.write("  " + v[0] + " " + str(v[1]) + "\n")
                values += indentedStr + f"  {v[0]} = {v[1]}\n"
        out.write(values)
        if self.is_group():
            out.write("\n" + indentedStr + "  [Grouped]\n")
            for g in self.iter_grouped_children():
                g.print_map(out, indention+1, indentionWidth)
                out.write("\n")
        out.write(indentedStr + "}")

    def __contains__(self, other: Union[str, "BaseObject"]) -> bool:
        if not self.is_group():
            return False
        if isinstance(other, BaseObject):
            return other in self._grouped
        return any([g == other for g in self._grouped])
