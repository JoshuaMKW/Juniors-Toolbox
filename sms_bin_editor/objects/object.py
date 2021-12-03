from io import BytesIO
from typing import BinaryIO, Iterable, List, Optional, TextIO, Tuple, Union
from sms_bin_editor.objects.template import AttributeType, ObjectAttribute, ObjectTemplate
from sms_bin_editor.utils import jdrama
from sms_bin_editor.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16, write_uint32

KNOWN_GROUP_HASHES = {
    16824, 15406, 28318, 18246,
    43971, 9858, 25289,  # levels
    33769, 49941, 13756, 65459,
    38017, 47488,  # tables
    8719, 22637
}


class ObjectGroupError(Exception):
    ...


class GameObject():
    """
    Class describing a generic game object
    """

    def __init__(self):
        self._name = jdrama.NameRef("(null)")
        self._desc = jdrama.NameRef("(null)1")

        self._parent = None
        self._grouped: List[GameObject] = []

        self._template = ObjectTemplate()
        self._values = []

    @classmethod
    def from_bytes(cls, data: BinaryIO):
        this = cls()

        try:
            objLength = read_uint32(data)
        except Exception:
            return

        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objNameHash = read_uint16(data)
        objNameLength = read_uint16(data)

        objName = jdrama.NameRef(read_string(data, maxlen=objNameLength-1))

        assert hash(objName) == objNameHash and len(
            objName) == objNameLength, f"Object name is corrupted! {hash(objName)} ({objName}) != {objNameHash} (main)"

        this._name = objName

        # -- Desc -- #
        objDescHash = read_uint16(data)
        objDescLength = read_uint16(data)

        objDesc = jdrama.NameRef(read_string(
            data, maxlen=objDescLength-1, encoding="shift-jis"))

        assert hash(objDesc) == objDescHash and len(
            objDesc.encode("shift-jis")) == objDescLength, f"Object desc is corrupted! {hash(objDesc)} ({objDesc}) != {objDescHash} (main)"

        this._desc = objDesc

        # -- Template Specific -- #
        template = ObjectTemplate.from_template(
            ObjectTemplate.TEMPLATE_PATH / f"{this._name}.txt")
        if template is None:
            template = ObjectTemplate()

        nameHash = hash(this._name)
        if nameHash in KNOWN_GROUP_HASHES:
            template.insert(1 if nameHash in {15406, 9858} else 0, ObjectAttribute(
                "Grouped", AttributeType.U32))

        for attribute, value in template.iter_data(data):
            this.create_value(-1, attribute.name, value, attribute.comment)

        groupNum = this.get_value("Grouped")
        if nameHash in KNOWN_GROUP_HASHES and groupNum is not None:
            for i in range(groupNum):
                this.add_to_group(GameObject.from_bytes(data))

        this._parent = None
        return this

    def to_bytes(self) -> bytes:
        """
        Converts this object to raw bytes
        """
        data = BytesIO()

        write_uint32(data, self.get_data_length())
        write_uint16(data, hash(self._name))
        write_uint16(data, len(self._name))
        write_string(data, self._name)
        write_uint16(data, hash(self._desc))
        write_uint16(data, len(self._desc))
        write_string(data, self._desc)
        data.write(self.data)

        if hash(self._name) in KNOWN_GROUP_HASHES:
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
        for attr in self._template:
            attr.write_to(data, self.get_value(attr.name))
        return data

    def clone(self) -> "GameObject":
        """
        Creates a copy of this object
        """
        obj = GameObject()
        obj._name = jdrama.NameRef(self._name)
        obj._desc = jdrama.NameRef(self._desc)
        obj._parent = self._parent
        obj._grouped = self._grouped.copy()
        obj._template = self._template.copy()
        return obj

    def get_data_length(self) -> int:
        """
        Gets the length of this object in bytes
        """
        length = 12 + len(self._name) + len(self._desc) + len(self.data)
        if hash(self._name) in KNOWN_GROUP_HASHES:
            for obj in self._grouped:
                length += obj.get_data_length()
        return length

    def is_value(self, attrname: str) -> bool:
        """
        Check if a named value exists in this object
        """
        if not any([attrname == a.name for a in self._template]):
            return False

        return any(attrname == v[0] for v in self._values)

    def is_group(self) -> bool:
        """
        Check if this object is a group object capable of holding other objects
        """
        return hash(self._name) in KNOWN_GROUP_HASHES and self.is_value("Grouped")

    def get_value(self, attrname: str) -> Union[int, float, str, bytes]:
        """
        Get a value by name from this object
        """
        attrname = attrname.strip()

        if not any([attrname == a.name for a in self._template]):
            return None

        for value in self._values:
            if value[0] == attrname:
                return value[1]

    def get_value_pair_by_index(self, index: int) -> Tuple[str, Union[int, float, str, bytes]]:
        """
        Return a tuple containing the name and value at the specified index
        """
        return self._values[index]

    def set_value(self, attrname: str, value: Union[int, float, str, bytes]) -> bool:
        """
        Set a value by name if it exists in this object

        Returns `True` if successful
        """
        attrname = attrname.strip()

        if not self.is_value(attrname):
            return False

        for val in self._values:
            if val[0] == attrname:
                val[1] = value
                return True
        return False

    def set_value_by_index(self, index: int, value: Union[int, float, str, bytes]):
        """
        Set a value by index if it exists in this object
        """
        self._values[index][1] = value

    def create_value(self, index: int, attrname: str, value: Union[int, float, str, bytes], comment: str = "") -> bool:
        """
        Create a named value for this object if it doesn't exist

        Returns `True` if created
        """
        attrname = attrname.strip()

        if any([a.name == attrname.strip() for a in self._template]):
            return False

        try:
            attribute = ObjectAttribute(
                attrname, AttributeType.type_to_enum(value.__class__), comment)
            self._template.insert(index, attribute)
        except ValueError:
            return False

        for val in self._values:
            if val[0] == attrname:
                val[1] = value
                return True

        if index != -1:
            self._values.insert(index, [attrname, value])
        else:
            self._values.append([attrname, value])
        return True

    def iter_values(self) -> Iterable[Tuple[str, Union[int, float, str, bytes]]]:
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
                f"Cannot add an object ({obj._name}) to {self._name} which is not a Group Object!")

        self._grouped.append(obj)
        obj._parent = self

    def remove_from_group(self, obj: "GameObject") -> bool:
        """
        Remove an object from this group object
        """
        if not self.is_group():
            raise ObjectGroupError(
                f"Cannot remove an object ({obj._name}) from {self._name} which is not a Group Object!")

        try:
            self._grouped.remove(obj)
            obj._parent = None
            return True
        except ValueError:
            return False

    def iter_grouped(self) -> Iterable["GameObject"]:
        """
        Yield all of the grouped objects
        """
        for g in self._grouped:
            yield g

    def __str__(self) -> str:
        header = f"{self._name} ({self._desc})"
        body = ""
        for v in self.iter_values():
            body += f"  {v[0]} = {v[1]}\n"
        return header + " {\n" + body + "}"

    def print_map(self, out: TextIO, indention: int = 0, indentionWidth: int = 2):
        """
        Print a complete map of this object to `out`
        """
        indentedStr = " "*indention*indentionWidth

        out.write(indentedStr + f"{self._name} ({self._desc})" + " {\n")
        values = indentedStr + "  [Values]\n"
        for v in self.iter_values():
            values += indentedStr + f"  {v[0]} = {v[1]}\n"
        out.write(values)
        if self.is_group():
            out.write("\n" + indentedStr + "  [Grouped]\n")
            for g in self.iter_grouped():
                g.print_map(out, indention+1, indentionWidth)
                out.write("\n")
        out.write(indentedStr + "}")
