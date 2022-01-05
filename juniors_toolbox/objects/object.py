from io import BytesIO
from struct import Struct
from typing import Any, BinaryIO, Iterable, List, Optional, TextIO, Tuple, Union

from numpy import array
from juniors_toolbox.objects.template import AttributeType, ObjectAttribute, ObjectTemplate
from juniors_toolbox.utils.types import RGBA, Vec3f
from juniors_toolbox.utils import jdrama
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


class GameObject():
    """
    Class describing a generic game object
    """

    def __init__(self):
        self.name = jdrama.NameRef("(null)")
        self.desc = jdrama.NameRef("(null)1")

        self._parent = None
        self._grouped: List[GameObject] = []

        self._template = ObjectTemplate()
        self._values = []

    @classmethod
    def from_bytes(cls, data: BinaryIO):
        this = cls()

        try:
            objLength = read_uint32(data)
        except Exception:  # FIXME: MAJOR HACK, REMOVE EXCEPT BLOCK WHEN FIXED
            return

        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objNameHash = read_uint16(data)
        objNameLength = read_uint16(data)

        objName = jdrama.NameRef(read_string(data, maxlen=objNameLength-1))

        if hash(objName) != objNameHash or len(objName.encode()) != objNameLength:
            raise ObjectCorruptedError(
                f"Object name is corrupted! {hash(objName)} ({objName}) != {objNameHash}")

        this.name = objName

        # -- Desc -- #
        objDescHash = read_uint16(data)
        objDescLength = read_uint16(data)

        objDesc = jdrama.NameRef(read_string(
            data, maxlen=objDescLength-1, encoding="shift-jis"))

        if hash(objDesc) != objDescHash or len(objDesc.encode("shift-jis")) != objDescLength:
            raise ObjectCorruptedError(
                f"Object desc is corrupted! {hash(objDesc)} ({objDesc}) != {objDescHash}")

        this.desc = objDesc

        # -- Template Specific -- #
        template = ObjectTemplate.from_template(
            ObjectTemplate.TEMPLATE_PATH / f"{this.name}.txt")
        if template is None:
            template = ObjectTemplate()

        nameHash = hash(this.name)
        if nameHash in KNOWN_GROUP_HASHES:
            template.add_attribute(ObjectAttribute(
                "Grouped", AttributeType.U32), int(nameHash in {15406, 9858}))

        def gen_attr(t: ObjectAttribute, nestedNamePrefix: str = "") -> dict:
            def construct(index: int) -> dict:
                char = "abcdefghijklmnopqrstuvwxyz"[i]
                if isStruct:
                    parentName = ObjectAttribute.get_formatted_name(
                        t.name, char, i)
                    for attr in t.iter_attributes():
                        for attrdata in gen_attr(attr, parentName + "."):
                            this.create_value(
                                attrdata["index"],
                                f"{nestedNamePrefix}{parentName}.{attrdata['name']}",
                                attrdata["value"],
                                attrdata["comment"]
                            )

                else:
                    instances.append({
                        "index": -1,
                        "name": ObjectAttribute.get_formatted_name(
                            t.name, char, i),
                        "value": t.read_from(data),
                        "comment": t.comment
                    })
            isStruct = t.is_struct()
            if t.is_count_referenced():
                count = this.get_value(t.countRef.name)
            else:
                count = t.countRef

            instances = []
            if count == -1:
                i = 0
                while True:
                    if data.tell() >= objEndPos:
                        return instances
                    print(data.tell(), objEndPos)
                    construct(i)
                    i += 1

            for i in range(count):
                construct(i)
            return instances

        for attribute in template.iter_attributes():
            for attrdata in gen_attr(attribute):
                this.create_value(
                    attrdata["index"],
                    attrdata["name"],
                    attrdata["value"],
                    attrdata["comment"]
                )

        groupNum = this.get_value("Grouped")
        if nameHash in KNOWN_GROUP_HASHES and groupNum is not None:
            for _ in range(groupNum):
                this.add_to_group(GameObject.from_bytes(data))

        this._parent = None
        return this

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()

        write_uint32(data, self.get_data_length())
        write_uint16(data, hash(self.name))
        write_uint16(data, len(self.name))
        write_string(data, self.name)
        write_uint16(data, hash(self.desc))
        write_uint16(data, len(self.desc))
        write_string(data, self.desc)
        data.write(self.data)

        if hash(self.name) in KNOWN_GROUP_HASHES:
            write_uint32(data, len(self._grouped))
            for obj in self._grouped:
                data.write(obj.to_bytes())

        return data.getvalue()

    @property
    def data(self) -> BytesIO:
        """
        Get the raw data of this object's values
        """
        data = BytesIO()
        for attr in self._template.iter_attributes():
            attr.write_to(data, self.get_value(attr.name))
        return data

    def clone(self) -> "GameObject":
        """
        Creates a copy of this object
        """
        obj = GameObject()
        obj.name = jdrama.NameRef(self.name)
        obj.desc = jdrama.NameRef(self.desc)
        obj._parent = self._parent
        obj._grouped = self._grouped.copy()
        obj._template = self._template.copy()
        return obj

    def get_data_length(self) -> int:
        """
        Gets the length of this object in bytes
        """
        length = 12 + len(self.name) + len(self.desc) + len(self.data)
        if hash(self.name) in KNOWN_GROUP_HASHES:
            for obj in self._grouped:
                length += obj.get_data_length()
        return length

    def is_value(self, attrname: str) -> bool:
        """
        Check if a named value exists in this object
        """
        if not any([attrname == a.name for a in self._template.iter_attributes()]):
            return False

        return any(attrname == v[0] for v in self._values)

    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        return hash(self.name) in KNOWN_GROUP_HASHES  # and self.is_value("Grouped")

    def get_value(self, attrname: str) -> Union[int, float, str, bytes, RGBA]:
        """
        Get a value by name from this object
        """
        attrname = attrname.strip()

        if not attrname in self._template:
            return None

        for value in self._values:
            if value[0] == attrname:
                return value[1]

    def get_value_pair_by_index(self, index: int) -> Tuple[str, Union[int, float, str, bytes, RGBA]]:
        """
        Return a tuple containing the name and value at the specified index
        """
        return self._values[index]

    def set_value(self, attrname: str, value: Union[int, float, str, bytes, RGBA, Vec3f]) -> bool:
        """
        Set a value by name if it exists in this object

        Returns `True` if successful
        """

        attrname = attrname.strip()

        if not self.is_value(attrname):
            return False

        for val in self._values:
            print(val)
            if val[0] == attrname:
                if isinstance(val[1], Vec3f):
                    val[1] = value
                else:
                    print(val[1])
                    print(value)
                    print(val[1].__class__)
                    val[1] = val[1].__class__(value)
                    #print(val[0], val[1].value)
                return True
        return False

    def set_value_by_index(self, index: int, value: Union[int, float, str, bytes, RGBA, Vec3f]):
        """
        Set a value by index if it exists in this object
        """
        self._values[index][1] = value

    def create_value(self, index: int, attrname: str, value: Union[int, float, str, bytes, RGBA, Vec3f], comment: str = "", strict: bool = False) -> bool:
        """
        Create a named value for this object if it doesn't exist

        Returns `True` if created

        `strict`: If true, disallow enumerating the name for unique values
        """
        if value is None:
            return False
            
        attrname = attrname.strip()
        easyname = attrname

        isStructMember = "." in attrname

        isVeryUnique = True
        if strict:
            if any([a.name == easyname.strip() for a in self._template.iter_attributes()]):
                return False
        else:
            i = 0
            while any([a[0] == easyname.strip() for a in self._values]):
                i += 1
                isVeryUnique = False
                easyname = f"{attrname}{i}"

        attrname = easyname
        if isinstance(value, RGBA):
            print(attrname, isVeryUnique)

        if isVeryUnique:
            try:
                scopedNames = attrname.split(".")
                nestingDepth = len(scopedNames)
                nestingDepth = 1 # FIXME: fix scoping lookup issue
                attribute = ObjectAttribute(
                    attrname, AttributeType.type_to_enum(value.__class__), comment)
                if nestingDepth == 1:
                    self._template.add_attribute(attribute, index)
                else:
                    attr = self._template.get_attribute(scopedNames[0])
                    for i, name in enumerate(scopedNames[1:], start=2):
                        print(attr, name, i, nestingDepth)
                        if attr is None:
                            return False

                        if not attr.is_struct():
                            return False

                        if i == nestingDepth:
                            attr._subattrs.append(attribute)

                        attr = attr.get_attribute(scopedNames[name])
                        
            except ValueError as e:
                print(e)
                return False

        for val in self._values:
            if val[0] == attrname:
                val[1] = value
                return True

        if isinstance(value, list):
            print("asuhsauhsuh")

        if index != -1:
            self._values.insert(index, [attrname, value])
        else:
            self._values.append([attrname, value])
        return True

    def iter_values(self) -> Iterable[Tuple[str, Union[int, float, str, bytes, list, RGBA]]]:
        """
        Yield all of this object's values
        """
        for v in self._values:
            yield v

    def get_parent(self) -> "GameObject":
        """
        Get this object's parent group object
        """
        return self._parent

    def add_to_group(self, obj: "GameObject"):
        """
        Add an object to this group object
        """
        if not self.is_group():
            raise ObjectGroupError(
                f"Cannot add an object ({obj.name}) to {self.name} which is not a Group Object!")

        self._grouped.append(obj)
        obj._parent = self

    def remove_from_group(self, obj: "GameObject") -> bool:
        """
        Remove an object from this group object
        """
        if not self.is_group():
            raise ObjectGroupError(
                f"Cannot remove an object ({obj.name}) from {self.name} which is not a Group Object!")

        try:
            self._grouped.remove(obj)
            obj._parent = None
            return True
        except ValueError:
            return False

    def iter_grouped(self, deep: bool = False) -> Iterable["GameObject"]:
        """
        Yield all of the grouped objects
        """
        for g in self._grouped:
            yield g
            if deep and g.is_group():
                yield from g.iter_grouped()

    def print_map(self, out: TextIO, indention: int = 0, indentionWidth: int = 2):
        """
        Print a complete map of this object to `out`
        """
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self.name} ({self.desc})" + " {\n")
        values = indentedStr + "  [Values]\n"
        with open("sussy.baka", "a") as f:
            f.write(self.name + "\n")
            for v in self.iter_values():
                f.write("  " + v[0] + " " + str(v[1]) + "\n")
                values += indentedStr + f"  {v[0]} = {v[1]}\n"
        out.write(values)
        if self.is_group():
            out.write("\n" + indentedStr + "  [Grouped]\n")
            for g in self.iter_grouped():
                g.print_map(out, indention+1, indentionWidth)
                out.write("\n")
        out.write(indentedStr + "}")

    def get_explicit_name(self) -> str:
        """
        Return the described name of thie object
        """
        return f"{self.name} ({self.desc})"

    def __str__(self) -> str:
        header = f"{self.name} ({self.desc})"
        body = ""
        for v in self.iter_values():
            body += f"  {v[0]} = {v[1]}\n"
        return header + " {\n" + body + "}"

    def __contains__(self, other: Union[str, "GameObject"]) -> bool:
        if not self.is_group():
            return False
        if isinstance(other, GameObject):
            return other in self._grouped
        return any([g.name == other for g in self._grouped])
