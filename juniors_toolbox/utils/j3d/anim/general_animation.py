import struct

import oead
from io import BytesIO

BTPFILEMAGIC = b"J3D1btp1"
BTKFILEMAGIC = b"J3D1btk1"
BRKFILEMAGIC = b"J3D1brk1"
BCKFILEMAGIC = b"J3D1bck1"
BPKFILEMAGIC = b"J3D1bpk1"
BCAFILEMAGIC = b"J3D1bca1"
BLAFILEMAGIC = b"J3D1bla1"
BLKFILEMAGIC = b"J3D1blk1"
BVAFILEMAGIC = b"J3D1bva1"


PADDING = b"This is padding data to align"


def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]


def read_uint16(f):
    return struct.unpack(">H", f.read(2))[0]


def read_sint16(f):
    return struct.unpack(">h", f.read(2))[0]


def read_ubyte(f):
    return struct.unpack(">B", f.read(1))[0]


def read_sbyte(f):
    return struct.unpack(">b", f.read(1))[0]


def read_float(f):
    return struct.unpack(">f", f.read(4))[0]


def write_uint32(f, val):
    f.write(struct.pack(">I", val))


def write_uint16(f, val):
    f.write(struct.pack(">H", val))


def write_sint16(f, val):
    f.write(struct.pack(">h", val))


def write_ubyte(f, val):
    f.write(struct.pack(">B", val))


def write_sbyte(f, val):
    f.write(struct.pack(">b", val))


def write_float(f, val):
    f.write(struct.pack(">f", val))


def write_padding(f, multiple):
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)

    diff = next_aligned - f.tell()

    for i in range(diff):

        pos = i % len(PADDING)
        f.write(PADDING[pos:pos+1])


def write_pad32(f):
    next_aligned_pos = (f.tell() + 0x1F) & ~0x1F

    f.write(b"\x00"*(next_aligned_pos - f.tell()))
    # print(hex(f.tell()))
    # print(hex(next_aligned_pos))


loop_mode = ("Play once", "Play Once - Stop at 1st Frame",
             "Loop", "Mirror once", "Mirror Loop")
tan_type = ("Tan out only", "Tan in and out")


class BasicAnimation(object):
    def __init__(self):
        pass

    def get_children_names(self):
        strings = []

        for animation in self.animations:
            strings.append(animation.name)
        return strings

    @classmethod
    def match_bmd(cls, object, strings):

        i = 0
        while i < len(object.animations):
            anim = object.animations[i]
            if not anim.name in strings:
                object.animations.pop(i)
            else:
                i += 1

        return object


class AnimComponent(object):
    def __init__(self, time, value, tangentIn=0, tangentOut=None, tantype="0"):
        self.time = time
        self.value = value
        self.tangentIn = tangentIn
        self.tanType = tantype

        #self.tan_inter = -1

        if tangentOut is None:
            self.tangentOut = tangentIn
        else:
            self.tangentOut = tangentOut

    def serialize(self):
        return [self.time, self.value, self.tangentIn, self.tangentOut]

    def __repr__(self):
        return "Time: {0}, Val: {1}, TanIn: {2}, TanOut: {3}".format(self.time, self.value, self.tangentIn, self.tangentOut).__repr__()

    def convert_rotation(self, rotscale):
        self.value *= rotscale
        self.tangentIn *= rotscale
        self.tangentOut *= rotscale

    def convert_rotation_inverse(self, rotscale):
        self.value /= rotscale
        self.tangentIn /= rotscale
        self.tangentOut /= rotscale

    @classmethod
    def from_array(cls, offset, index, count, valarray, tanType):
        if count == 1:
            try:
                return cls(0, valarray[offset+index], 0, 0)
            except:
                return cls(0, 1, 0, 0)

        else:
            if tanType == 0:
                try:

                    return cls(valarray[offset + index*3], valarray[offset + index*3 + 1], valarray[offset + index*3 + 2])
                except:
                    return cls(valarray[offset + index*3], valarray[offset + index*3 + 1], 0)
            elif tanType == 1:
                return cls(valarray[offset + index*4], valarray[offset + index*4 + 1], valarray[offset + index*4 + 2], valarray[offset + index*4 + 3])
            else:
                raise RuntimeError("unknown tangent type: {0}".format(tanType))


def combine_dicts(array, keyframes_dictionary):
    thismat_kf = {}

    for value in array:
        thismat_kf[value.time] = value.value

    for k in keyframes_dictionary.keys():  # if there is a keyframe that does not apply to the current material, pad
        if not k in thismat_kf.keys():
            keyframes_dictionary[k].append("")

    for k in thismat_kf.keys():
        if k in keyframes_dictionary:
            keyframes_dictionary[k].append(thismat_kf[k])
        else:
            to_add = []
            for l in range(int(len(keyframes_dictionary[0]) - 1)):
                to_add.append("")
            to_add.append(thismat_kf[k])
            keyframes_dictionary[k] = (to_add)

    return keyframes_dictionary


def write_values(info, keyframes_dictionary, row):
    keys = []

    for i in keyframes_dictionary.keys():
        keys.append(int(i))

    keys.sort()

    for i in keys:  # i is the frame, so for each keyframe

        info[row].append("Frame " + str((int(i))))  # add the header

        k = row + 1  # k in the row index in the table
        for j in keyframes_dictionary[i]:  # j is the value
            #print( len (keyframes_dictionary[i] ) )
            try:
                info[k].append(j)
                k += 1
            except:
                pass


class StringTable(object):
    def __init__(self):
        self.strings = []

    @classmethod
    def from_file(cls, f):
        stringtable = cls()

        start = f.tell()

        string_count = read_uint16(f)
        f.read(2)  # 0xFFFF

        offsets = []

        #print("string count", string_count)

        for i in range(string_count):
            hash = read_uint16(f)
            string_offset = read_uint16(f)

            offsets.append(string_offset)

        for offset in offsets:
            f.seek(start+offset)

            # Read 0-terminated string
            string_start = f.tell()
            string_length = 0

            while f.read(1) != b"\x00":
                string_length += 1

            f.seek(start+offset)

            if string_length == 0:
                stringtable.strings.append("")
            else:
                stringtable.strings.append(
                    f.read(string_length).decode("shift-jis"))

        return stringtable

    @classmethod
    def hash_string(cls, string):
        hash = 0

        for char in string:
            hash *= 3
            hash += ord(char)
            hash = 0xFFFF & hash  # cast to short

        return hash

    @classmethod
    def write(cls, f, strings):
        start = f.tell()
        f.write(struct.pack(">HH", len(strings), 0xFFFF))

        for string in strings:
            hash = StringTable.hash_string(string)

            f.write(struct.pack(">HH", hash, 0xABCD))

        offsets = []

        for string in strings:
            offsets.append(f.tell())
            f.write(string.encode("shift-jis"))
            f.write(b"\x00")

        end = f.tell()

        for i, offset in enumerate(offsets):
            f.seek(start+4 + (i*4) + 2)
            write_uint16(f, offset-start)

        f.seek(end)

# Optional rounding


def opt_round(val, digits):
    if digits is None:
        return val
    else:
        return round(val, digits)

# Find the start of the sequence seq in the list in_list, if the sequence exists


def find_sequence(in_list, seq):
    matchup = 0
    start = -1

    found = False
    started = False

    for i, val in enumerate(in_list):
        if val == seq[matchup]:
            if not started:
                start = i
                started = True

            matchup += 1
            if matchup == len(seq):
                #start = i-matchup
                found = True
                break
        else:
            matchup = 0
            start = -1
            started = False
    if not found:
        start = -1

    return start


def find_single_value(in_list, value):

    return find_sequence(in_list, [value])


def get_bone_transforms(bmd_file):
    with open(bmd_file, "rb") as f:
        s = f.read()
        a = s.find(b'\x4A\x4E\x54\x31')

        f.seek(a + 0x08)
        bone_count = read_uint16(f)
        f.seek(a + 0x0c)
        address = read_uint32(f)
        f.seek(address + a)

        values = []
        for i in range(bone_count):
            this_bone = []
            f.read(4)
            this_bone.append(read_float(f))
            this_bone.append(read_float(f))
            this_bone.append(read_float(f))
            this_bone.append(read_sint16(f))
            this_bone.append(read_sint16(f))
            this_bone.append(read_sint16(f))
            f.read(2)
            this_bone.append(read_float(f))
            this_bone.append(read_float(f))
            this_bone.append(read_float(f))
            f.read(28)
            values.append(this_bone)
        return values


def get_bones_from_bmd(bmd_file):
    strings = []
    with open(bmd_file, "rb") as f:
        s = f.read()
        a = s.find(b'\x4A\x4E\x54\x31')
        # print(a)
        f.seek(a + 0x14)
        address = read_uint32(f)
        # print(address)
        f.seek(address + a)
        strings = StringTable.from_file(f).strings
        print(strings)
        f.close()

    return strings


def get_materials_from_bmd(bmd_file):
    strings = []
    with open(bmd_file, "rb") as f:
        s = f.read()
        a = s.find(b'\x4D\x41\x54\x33')
        # print(a)
        f.seek(a + 0x14)
        address = read_uint32(f)
        # print(address)
        f.seek(address + a)
        strings = StringTable.from_file(f).strings
        print(strings)
        f.close()

    return strings


def get_meshes_from_bmd(bmd_file):
    strings = []
    print("get mesh")
    with open(bmd_file, "rb") as f:
        s = f.read()
        a = s.find(b'\x53\x48\x50\x31')
        print(a)
        f.seek(a + 0x8)
        count = read_uint16(f)
        strings = ["Mesh " + str(i) for i in range(count)]
        print(strings)
        f.close()

    return strings


def read_hierachy(bmd_file):
    children = []

    #bones = get_bones_from_bmd(bmd_file)

    with open(bmd_file, "rb") as f:
        s = f.read()

        # get bone count
        a = s.find(b'\x4A\x4E\x54\x31')
        f.seek(a + 0x8)
        bone_count = read_uint16(f)
        children = [0] * bone_count

        # get size of inf1 section
        a = s.find(b'\x49\x4e\x46\x31')
        f.seek(a + 0x4)
        inf_size = read_uint32(f)

        #
        f.seek(a + 0x14)
        address = read_uint32(f)
        f.seek(address + a)

        stack = [0]
        curr_bone = 0x0
        last_bone = 0x0
        while address < inf_size:
            f.seek(address)
            node = read_uint16(f)
            address += 2
            if node == 0x11 or node == 0x12:
                read_uint16(f)
                address += 2
            elif node == 0x01:
                read_uint16(f)
                address += 2
                curr_bone = last_bone
                stack.append(curr_bone)
                #print("child mode for bone " + bones[curr_bone])
            elif node == 0x02:
                read_uint16(f)
                address += 2

                stack.pop()
                curr_bone = stack[-1]
                #print("return to parent " + bones[curr_bone])
                #curr_bone = prev_bone
            elif node == 0x10:
                children[curr_bone] += 1
                #prev_bone = curr_bone
                last_bone = read_uint16(f)
                address += 2
                #print("at bone " + bones[last_bone] + " - a child of " + bones[curr_bone])

        f.close()
    children[0] = children[0] - 1
    print(children)
    return children


def fix_array(info):
    # the arrays should be pure text
    for i in range(len(info)):
        while len(info[i]) > 0 and info[i][-1] == "":
            info[i].pop(len(info[i]) - 1)
    i = 0
    while i < len(info):
        if len(info[i]) == 0:
            info.pop(i)
        else:
            i += 1

    # fix the header stuff
    for i in range(len(info[0])):
        if info[0][i] in loop_mode:
            info[0][i] = str(loop_mode.index(info[0][i]))
        elif info[0][i] in tan_type:
            info[0][i] = str(tan_type.index(info[0][i]))

    for i in range(2, len(info[1])):
        if str(info[1][i]).isnumeric():
            info[1][i] = "Frame " + info[1][i]

    # print(info)
    return info


def make_tangents(array, inter=0):
    if len(array) == 1:
        return array
    elif inter == 1 or inter == -1:
        for i in range(len(array)):
            array[i].tangentOut = 0
            array[i].tangentIn = 0
    else:
        for i in range(len(array) - 1):
            this_comp = array[i]
            next_comp = array[i + 1]

            tangent = 0
            if next_comp.time != this_comp.time:
                tangent = (next_comp.value - this_comp.value) / \
                    (next_comp.time - this_comp.time)

            array[i].tangentOut = tangent
            array[i+1].tangentIn = tangent

        this_comp = array[-1]
        next_comp = array[0]

        tangent = 0
        if next_comp.time != this_comp.time:
            tangent = (next_comp.value - this_comp.value) / \
                (next_comp.time - this_comp.time)
        #tangent = (next_comp.value - this_comp.value) / (next_comp.time - this_comp.time)

        array[-1].tangentOut = tangent
        array[0].tangentIn = tangent

    #print( array)

    return array


#import statements


def convert_to_a(filepath, info):
    from juniors_toolbox.utils.j3d.anim.bla import bla
    from juniors_toolbox.utils.j3d.anim.blk import blk
    from juniors_toolbox.utils.j3d.anim.bca import bca
    from juniors_toolbox.utils.j3d.anim.bck import BCK

    if filepath.endswith(".bck") or filepath.endswith(".bca"):
        bck = BCK.get_bck(info)
        bca = bca.from_bck(bck)

        return bca
    if filepath.endswith(".blk") or filepath.endswith(".bla"):

        _blk = blk.get_blk(info)
        bla = bla.from_blk(_blk)

        return bla


def import_anim_file(filepath):
    from juniors_toolbox.utils.j3d.anim.bck import BCK

    with open(filepath, "r") as f:
        info = BCK.from_maya_anim(f)
        f.close()
        return info


def import_bvh_file(filepath, as_bca=False):
    from juniors_toolbox.utils.j3d.anim.bca import bca
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    
    with open(filepath, "r") as f:
        info = BCK.from_blender_bvh(f)

        if as_bca:
            info = bca.from_bck(info)

        f.close()
        return info


def import_fbx_file(filepath):
    from juniors_toolbox.utils.j3d.anim.fbx_scripts import import_fbx_file
    animations = import_fbx_file(filepath)

    return animations

    # return bck_file.bck.from_fbx_anim(filepath);


def sort_file(filepath):
    from juniors_toolbox.utils.j3d.anim.bva import BVA
    from juniors_toolbox.utils.j3d.anim.bla import bla
    from juniors_toolbox.utils.j3d.anim.blk import blk
    from juniors_toolbox.utils.j3d.anim.bca import bca
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    from juniors_toolbox.utils.j3d.anim.bpk import bpk
    from juniors_toolbox.utils.j3d.anim.brk import BRK
    from juniors_toolbox.utils.j3d.anim.btk import BTK
    from juniors_toolbox.utils.j3d.anim.btp import btp

    with open(filepath, "rb") as f:
        magic = f.read(8)
        print(magic)

        if magic.startswith(b"Yaz0"):
            decomp = BytesIO()
            oead.yaz0.decompress(f, decomp)
            # print(decomp)
            f = decomp
            f.seek(0)

            magic = f.read(8)
            print(magic)

        if magic == BTPFILEMAGIC:
            return btp.from_data(f)
        elif magic == BTKFILEMAGIC:
            return BTK.from_data(f)
        elif magic == BRKFILEMAGIC:
            return BRK.from_data(f)
        elif magic == BCKFILEMAGIC:
            return BCK.from_data(f)
        elif magic == BPKFILEMAGIC:
            return bpk.from_data(f)
        elif magic == BCAFILEMAGIC:
            return bca.from_data(f)
        elif magic == BLAFILEMAGIC:
            return bla.from_data(f)
        elif magic == BLKFILEMAGIC:
            return blk.from_data(f)
        elif magic == BVAFILEMAGIC:
            return BVA.from_data(f)
        f.close()


def sort_filepath(filepath, information, sound_data=None):
    from juniors_toolbox.utils.j3d.anim.bva import BVA
    from juniors_toolbox.utils.j3d.anim.bla import bla
    from juniors_toolbox.utils.j3d.anim.blk import blk
    from juniors_toolbox.utils.j3d.anim.bca import bca
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    from juniors_toolbox.utils.j3d.anim.bpk import bpk
    from juniors_toolbox.utils.j3d.anim.brk import BRK
    from juniors_toolbox.utils.j3d.anim.btk import BTK
    from juniors_toolbox.utils.j3d.anim.btp import btp

    # print(filepath)
    if filepath.endswith(".btp"):
        return btp.from_table(filepath, information)
    elif filepath.endswith(".btk"):
        return BTK.from_table(filepath, information)
    elif filepath.endswith(".brk"):
        return BRK.from_table(filepath, information)
    elif filepath.endswith(".bck"):
        return BCK.from_table(filepath, information, sound_data)
    elif filepath.endswith(".bpk"):
        return bpk.from_table(filepath, information)
    elif filepath.endswith(".bca"):
        return bca.from_table(filepath, information)
    elif filepath.endswith(".bla"):
        return bla.from_table(filepath, information)
    elif filepath.endswith(".blk"):
        return blk.from_table(filepath, information)
    elif filepath.endswith(".bva"):
        return BVA.from_table(filepath, information)


def create_empty(information):
    from juniors_toolbox.utils.j3d.anim.bva import BVA
    from juniors_toolbox.utils.j3d.anim.bla import bla
    from juniors_toolbox.utils.j3d.anim.blk import blk
    from juniors_toolbox.utils.j3d.anim.bca import bca
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    from juniors_toolbox.utils.j3d.anim.bpk import bpk
    from juniors_toolbox.utils.j3d.anim.brk import BRK
    from juniors_toolbox.utils.j3d.anim.btk import BTK
    from juniors_toolbox.utils.j3d.anim.btp import btp

    table = []
    filepath = information[0]
    if filepath.endswith(".btp"):
        table = btp.empty_table(information)
    elif filepath.endswith(".btk"):
        table = BCK.empty_table(information)
    elif filepath.endswith(".brk"):
        table = BRK.empty_table(information)
    elif filepath.endswith(".bck"):
        table = BCK.empty_table(information)
    elif filepath.endswith(".bpk"):
        table = bpk.empty_table(information)
    elif filepath.endswith(".bca"):
        table = bca.empty_table(information)
    elif filepath.endswith(".bla"):
        table = bla.empty_table(information)
    elif filepath.endswith(".blk"):
        table = blk.empty_table(information)
    elif filepath.endswith(".bva"):
        table = BVA.empty_table(information)
    return table


def match_bmd(filepath, information, strings, filepathh):
    from juniors_toolbox.utils.j3d.anim.bva import BVA
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    from juniors_toolbox.utils.j3d.anim.bpk import bpk
    from juniors_toolbox.utils.j3d.anim.brk import BRK
    from juniors_toolbox.utils.j3d.anim.btk import BTK
    from juniors_toolbox.utils.j3d.anim.btp import btp
    
    # print(filepath)

    if filepath.endswith(".btp"):
        table = btp.match_bmd(information, strings)
    elif filepath.endswith(".btk"):
        table = BTK.match_bmd(information, strings)
    elif filepath.endswith(".brk"):
        table = BRK.match_bmd(information, strings)
    elif filepath.endswith(".bck") or filepath.endswith(".bca"):
        table = BCK.match_bmd(information, strings, filepathh)
    elif filepath.endswith(".bpk"):
        table = bpk.match_bmd(information, strings)
        # elif filepath.endswith(".blk") or filepath.endswith(".bla"):
        #    table = blk_file.blk.match_bmd(information, strings)
    elif filepath.endswith(".bva"):
        table = BVA.match_bmd(information, strings)
    return table


def get_single_mat(extension):
    from juniors_toolbox.utils.j3d.anim.bck import BCK
    from juniors_toolbox.utils.j3d.anim.bpk import bpk
    from juniors_toolbox.utils.j3d.anim.brk import BRK
    from juniors_toolbox.utils.j3d.anim.btk import BTK
    
    if extension == ".bck" or extension == ".bca":
        info = BCK.single_mat()
    elif extension == ".btk":
        info = BTK.single_mat()
    elif extension == ".brk":
        info = BRK.single_mat()
    elif extension == ".bpk":
        info = bpk.single_mat()
    return info


def export_anim(filepath, info, bmd_file):
    from juniors_toolbox.utils.j3d.anim.bck import BCK

    bck = BCK.from_table("", info)
    children = read_hierachy(bmd_file)
    bones = get_bones_from_bmd(bmd_file)
    bck.write_anim(filepath, children, bones)
