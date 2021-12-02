from io import BytesIO
from typing import BinaryIO, List, Optional
from sms_bin_editor.objects.template import ObjectAttribute, ObjectTemplate
from sms_bin_editor.utils import jdrama
from sms_bin_editor.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16, write_uint32

KNOWN_GROUP_HASHES = {
    16824, 15406, 28318, 18246,
    43971, 9858, 25289,  # levels
    33769, 49941, 13756, 65459,
    38017, 47488,  # tables
    8719, 22637
}


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

    @classmethod
    def from_bytes(cls, data: BinaryIO, template: ObjectTemplate):
        this = cls()

        objLength = read_uint32(data)
        objEndPos = data.tell() + objLength - 4

        # -- Name -- #
        objNameHash = read_uint16(data)
        objNameLength = read_uint16(data)

        objName = jdrama.NameRef(read_string(data, maxlen=objNameLength))

        assert hash(objName) == objNameHash and len(
            objName) == objNameLength, "Object name is corrupted!"

        this._name = objName

        # -- Desc -- #
        objDescHash = read_uint16(data)
        objDescLength = read_uint16(data)

        objDesc = jdrama.NameRef(read_string(data, maxlen=objDescLength))

        assert hash(objDesc) == objDescHash and len(
            objDesc) == objDescLength, "Object desc is corrupted!"

        this._desc = objDesc

        # -- Template Specific -- #
        template = ObjectTemplate.from_template(ObjectTemplate.TEMPLATE_PATH / f"{this._name}.txt")
        template.iter_data(data)

        # grouped = 0
        #
        # # Check if the object is a group object.
        # if hash(this._name) in KNOWN_GROUP_HASHES:
        #     if hash(this._name) in {15406, 9858}:
        #         values.Add((byte)stream.ReadByte())
        #         values.Add((byte)stream.ReadByte())
        #         values.Add((byte)stream.ReadByte())
        #         values.Add((byte)stream.ReadByte())

        #     byte[] datv = new byte[4]
        #     stream.Read(datv, 0, 4)
        #     grouped = BitConverter.ToInt32(
        #         DataManipulation.SwapEndian(datv), 0)
        # }
        # else
        # {
        #     while (stream.Position < end)
        #         values.Add((byte)stream.ReadByte());
        # }

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

    @ property
    def data(self) -> BytesIO:
        data = BytesIO()
        for attr in self._template:
            attr.write_to(data)
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
