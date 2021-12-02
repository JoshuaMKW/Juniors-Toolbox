import struct 
from collections import OrderedDict

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

BTKFILEMAGIC = b"J3D1btk1"
       
class MatrixAnimation(object):
    def __init__(self, index, matindex, name, center):
        self._index = index 
        self.matindex = matindex 
        self.name = name 
        self.center = center
        
        self.scale = {"U": [], "V": [], "W": []}
        self.rotation = {"U": [], "V": [], "W": []}
        self.translation = {"U": [], "V": [], "W": []}
        
        self.tan_inter = [-1] * 9

        self._scale_offsets = {}
        self._rot_offsets = {}
        self._translation_offsets = {}

    def add_scale(self, axis, comp):
        self.scale[axis].append(comp)
    
    def add_rotation(self, axis, comp):
        self.rotation[axis].append(comp)
        
    def add_translation(self, axis, comp):
        self.translation[axis].append(comp)

    # These functions are used for keeping track of the offset
    def _set_scale_offsets(self, axis, val):
        self._scale_offsets[axis] = val

    def _set_rot_offsets(self, axis, val):
        self._rot_offsets[axis] = val

    def _set_translation_offsets(self, axis, val):
        self._translation_offsets[axis] = val
    def has_components(self):
        size = len( scale["U"] ) + len( scale["V"] ) + len( scale["W"] )
        size += len( rotation["U"] ) + len( rotation["V"] ) + len( rotation["W"] )
        size += len( translation["U"] ) + len( translation["V"] ) + len( translation["W"] )
        
        return size
    
    
    
class btk(j3d.basic_animation):
    def __init__(self, loop_mode, anglescale, duration, unknown_address=0, tantype = 1):
        self.animations = []
        self.loop_mode = loop_mode
        self.anglescale = anglescale
        self.duration = duration
        self.unknown_address = unknown_address
        if tantype == 0 or tantype == 1:
            self.tan_type = tantype
        else:
            self.tan_type = 1

    @classmethod
    def from_anim(cls, f):

        size = read_uint32(f)
        #print("Size of btk: {} bytes".format(size))
        sectioncount = read_uint32(f)
        assert sectioncount == 1

        svr_data = f.read(16)
        
        ttk_start = f.tell()
        
        ttk_magic = f.read(4)
        ttk_sectionsize = j3d.read_uint32(f)

        loop_mode = j3d.read_uint8(f)
        angle_scale = j3d.read_sint8(f) 
        rotscale = (2.0**angle_scale) * (180.0 / 32768.0);
        duration = j3d.read_uint16(f)
        btk = cls(loop_mode, angle_scale, duration)


        threetimestexmatanims = read_uint16(f)
        scale_count = read_uint16(f)
        rotation_count = read_uint16(f)
        translation_count = read_uint16(f)
        """
        print("three times texmat anims", threetimestexmatanims)
        print("scale count", scale_count)
        print("rotation count", rotation_count)
        print("translation count", translation_count)
        """
        texmat_anim_offset  = read_uint32(f) + ttk_start    # J3DAnmTransformKeyTable
        index_offset        = read_uint32(f) + ttk_start    # unsigned short
        stringtable_offset  = read_uint32(f) + ttk_start    # 0 terminated strings 
        texmat_index_offset = read_uint32(f) + ttk_start    # unsigned byte
        center_offset       = read_uint32(f) + ttk_start    # Vector with 3 entries
        scale_offset        = read_uint32(f) + ttk_start    # float 
        rotation_offset     = read_uint32(f) + ttk_start    # signed short 
        translation_offset  = read_uint32(f) + ttk_start    # float 


        """
        print("Position:", hex(f.tell()))
        print("tex anim offset", hex(texmat_anim_offset))
        print("index offset", hex(index_offset))
        print("mat name offset", hex(stringtable_offset))
        print("texmat index offset", hex(texmat_index_offset))
        print("center offset", hex(center_offset))
        print("scale offset", hex(scale_offset))
        print("rotation offset", hex(rotation_offset))
        print("translation offset", hex(translation_offset))
        """
        
        anim_count = threetimestexmatanims//3
        #print("Animation count:", anim_count)

        f.seek(0x7C)
        unknown_address = read_uint32(f)
        btk.unknown_address = unknown_address
        # Read indices
        indices = []
        f.seek(index_offset)
        for i in range(anim_count):
            indices.append(read_uint16(f))
        
        # Read matrix indices 
        mat_indices = []
        f.seek(texmat_index_offset)
        for i in range(anim_count):
            mat_indices.append(read_uint8(f))
        
        # Read stringtable 
        f.seek(stringtable_offset)
        stringtable = StringTable.from_file(f)
        
        
        # Read scales 
        scales = []
        f.seek(scale_offset)
        for i in range(scale_count):
            scales.append(read_float(f))
  
        # Read rotations
        rotations = []
        f.seek(rotation_offset)
        for i in range(rotation_count):
            rotations.append((read_sint16(f)))
        
        # Read translations 
        translations = []
        f.seek(translation_offset)
        for i in range(translation_count):
            translations.append(read_float(f))
        
        tangent_type = 0
        
        # Read data per animation
        for i in indices:
            mat_index = mat_indices[i]
            
            # Read center for this animation
            f.seek(center_offset + 12*i)
            center = struct.unpack(">fff", f.read(12))
            
            name = stringtable.strings[i]
            """
            print("================")
            print("anim", i)
            print("mat index", mat_index, "name", name, "center", center)
            """
            f.seek(texmat_anim_offset + i*0x36)
            #print(hex(texmat_anim_offset + i*0x36))
            values = struct.unpack(">"+"H"*27, f.read(0x36))
            
            u_scale, u_rot, u_trans = values[:3], values[3:6], values[6:9]
            v_scale, v_rot, v_trans = values[9:12], values[12:15], values[15:18]
            w_scale, w_rot, w_trans = values[18:21], values[21:24], values[24:27]
            
            matrix_animation = MatrixAnimation(i, mat_index, name, center)
            
            inter_count = 0
            
            for scale, axis in ((u_scale, "U"), (v_scale, "V"), (w_scale, "W")):
                count, offset, tan_type = scale 
                tan_inter = 0
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    comp = j3d.AnimComponent.from_array(offset, j, count, scales, tan_type)
                   
                    if comp.tangentIn == 0:
                        matrix_animation.tan_inter[inter_count] = 1
                    matrix_animation.add_scale(axis, comp)
                if matrix_animation.tan_inter[inter_count] == -1:
                    matrix_animation.tan_inter[inter_count] = 0
                inter_count += 1 
            for rotation, axis in ((u_rot, "U"), (v_rot, "V"), (w_rot, "W")):
                count, offset, tan_type = rotation 
                
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    comp = j3d.AnimComponent.from_array(offset, j, count, rotations, tan_type)
                    comp.convert_rotation(rotscale)
                    
                    if comp.tangentIn != 0:
                        matrix_animation.tan_inter[inter_count] = 0
                    matrix_animation.add_rotation(axis, comp)
                inter_count += 1 
                if matrix_animation.tan_inter[inter_count] == -1:
                    matrix_animation.tan_inter[inter_count] = 0
            for translation, axis in ((u_trans, "U"), (v_trans, "V"), (w_trans, "W")):
                count, offset, tan_type = translation
               
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    comp = j3d.AnimComponent.from_array(offset, j, count, translations, tan_type)
                    if comp.tangentIn != 0:
                        matrix_animation.tan_inter[inter_count] = 0
                    matrix_animation.add_translation(axis, comp)        
                if matrix_animation.tan_inter[inter_count] == -1:
                    matrix_animation.tan_inter[inter_count] = 0
                inter_count += 1 
            #btk.tan_type = tangent_type
            
            """
            print(u_scale, u_rot, u_trans)
            
            print(v_scale, v_rot, v_trans)
            
            print(w_scale, w_rot, w_trans)
            """
            btk.animations.append(matrix_animation)
        btk.tan_type = tangent_type   
        return btk
             
    def get_loading_information(self):
        info = []
        info.append( ["Loop_mode", j3d.loop_mode[self.loop_mode], "Angle Scale:", self.anglescale,
            "Duration:", self.duration, "Unknown:", self.unknown_address, "Tan Type:", j3d.tan_type[self.tan_type] ] )
        info.append( ["Material name", "Tangent Interpolation", "Component"] ) 
        
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []
        
        i = len( info ) 
        
        for anim in self.animations:
            
            things = ["Scale U:", "Scale V:", "Scale W:", "Rotation U:", "Rotation V:", "Rotation W:",
                "Translation U:", "Translation V:", "Translation W:"]
            
            for j in range (len ( things ) ):    
                comp = things[j]
                if j < 5:
                    if j == 0:
                        info.append( [anim.name] )
                    elif j == 1:
                        info.append(["Texture Index"])
                    elif j == 2:
                        info.append([str(anim.matindex)])
                    elif j == 3:
                        info.append(["Center"])
                    elif j == 4:
                        info.append([anim.center])
                else:
                    info.append([""])
                
                if anim.tan_inter[j] == 1:
                    info[-1].append( "SSSS")

                else:
                    info[-1].append( "LLLL")

                
                info[-1].append(comp)
                
                
                comp_dict = {}
                if comp[0:1] == "S":
                    comp_dict = anim.scale
                elif comp[0:1] == "R":
                    comp_dict = anim.rotation
                else: 
                    
                    comp_dict = anim.translation
                    

                array = comp_dict[ comp[-2:-1] ]
                
                #print(array)                          
                
                
                keyframes_dictionary = j3d.combine_dicts(array, keyframes_dictionary) 
            i = len(info)
        
        write_values(info, keyframes_dictionary, 1)
        return info  
     
    @classmethod
    def empty_table(cls, created):
        info = []
        info.append( ["Loop_mode", "", "Angle Scale:", "", "Duration:", created[3], "Unknown:", 0, "Tan Type:", j3d.tan_type[1] ] )
        info.append( ["Material name", "Tangent Interpolation", "Component", "Frame 0", "Frame " + str(created[3]) ] ) 
        
        for i in range( int(created[1]) ):
            info.append( ["Material " + str(i),"SSSS", "Scale U:"] )
            info.append( ["Texture Index", "SSSS", "Scale V:"])
            info.append( ["0", "SSSS", "Scale W:" ] )
            info.append( ["Center", "LLLL", "Rotation U:"])
            info.append( ["(0.5, 0.5, 0.5)", "LLLL", "Rotation V:"] ) 
            info.append( ["", "LLLL", "Rotation W:"] )
            things = ["Translation U:", "Translation V:", "Translation W:"]
            for comp in things:
                info.append( ["", "SSSS", comp] )
        return info
    
    @classmethod
    def single_mat(cls):
        info = []
        info.append( ["Material Name","SSSS", "Scale U:"] )
        info.append( ["Texture Index", "SSSS", "Scale V:"])
        info.append( ["0", "SSSS", "Scale W:" ] )
        info.append( ["Center", "LLLL", "Rotation U:"])
        info.append( ["(0.5, 0.5, 0.5)", "LLLL", "Rotation V:"] ) 
        info.append( ["", "LLLL", "Rotation W:"] )
        things = ["Translation U:", "Translation V:", "Translation W:"]
        for comp in things:
            info.append( ["", "SSSS", comp] )
        return info
    
    @classmethod
    def from_table(cls, f, info):
        btk = cls(int(info[0][1]), int(info[0][3]), int(info[0][5]), int(info[0][7]), int(info[0][9]))
        
        keyframes = []
        
        for i in range(3, len( info[1] ) ):
            if info[1][i] != "":
                text = info[1][i][6:]
                text = int(text)
                keyframes.append(text)
        
        print("keyframes")
        print (keyframes)
        
        num_of_mats =  int ((len(info) - 2 ) / 9)#read all the values
             
        for i in range(num_of_mats): #for each material
            line = 9 * i + 2
            centrum = info[line + 4][0]
            if not isinstance(centrum, tuple):
                print("convert centrum to float tuple")
                centrum = centrum.strip("()")
                centrum = eval(centrum)
                #centrum = tuple(filter(float, centrum.split(",") ) ) 
            assert isinstance(centrum, tuple)
            
            current_anim = MatrixAnimation( i, int( info[line + 2][0] ), info[line][0], centrum)
            
            for j in range(9):  #for each of thing in scale/rot/trans u/v/w/       
                uvw = "UVW"
                uvw = uvw[j%3: j%3 + 1]
                              
                for k in range(3, len(info[line + j])): #for each keyframe
                    if info[line + j][k] != "":
                        comp = j3d.AnimComponent( keyframes[k-3], float(info[line + j][k]))
                        if info[line + j][1].startswith("S"):
                            current_anim.tan_inter[j] = 1
                        else:
                            current_anim.tan_inter[j] = 0        
                                    
                        if j < 3:
                            current_anim.add_scale(uvw, comp)
                            #print("scale " + uvw + " " + str(keyframes[k-4]) + ", " + str( float(info[line + j][k])))
                        elif j < 6:
                            current_anim.add_rotation(uvw, comp)
                           # print("rot " + uvw + " " + str(keyframes[k-4]) + ", " + str( float(info[line + j][k])))
                        else:
                            current_anim.add_translation(uvw, comp)
                           # print("trans " + uvw + " " + str(keyframes[k-4]) + ", " + str( float(info[line + j][k])))
            
            #calculate tangents
            for j in range(9):
                uvw = "UVW"
                uvw = uvw[j%3: j%3 + 1]
                
                if j < 3:
                    current_anim.scale[uvw] = j3d.make_tangents(current_anim.scale[uvw], current_anim.tan_inter[j])
                if j < 6:
                    current_anim.rotation[uvw] = j3d.make_tangents(current_anim.rotation[uvw], current_anim.tan_inter[j])
                else:
                    current_anim.translation[uvw] = j3d.make_tangents(current_anim.translation[uvw], current_anim.tan_inter[j])
            
            
            btk.animations.append(current_anim)
        if f == "":
            print("no saving")
            return btk
        else:
            with open(f, "wb") as f:
                btk.write_btk(f)
                f.close()
  
    def write_btk(self, f):
        
        f.write(BTKFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        j3d.write_uint32(f, 1) # Always a section count of 1
        f.write(b"SVR1" + b"\xFF"*12)

        ttk1_start = f.tell()
        f.write(b"TTK1")

        ttk1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for ttk1 size
        j3d.write_uint8(f, self.loop_mode)
        j3d.write_sint8(f, self.anglescale)
        
        rotscale = (2.0**self.anglescale)*(180.0 / 32768.0)
        
        j3d.write_uint16(f, self.duration)
        j3d.write_uint16(f, len(self.animations)*3) # Three times the matrix animations
        count_offset = f.tell()
        f.write(b"1+1=11")  # Placeholder for scale, rotation and translation count
        data_offsets = f.tell()
        f.write(b"--OnceUponATimeInALandFarAway---")
        f.write(b"\x00"*(0x7C - f.tell()))

        j3d.write_uint32(f, self.unknown_address)

        matrix_anim_start = f.tell()
        f.write(b"\x00"*(0x36*len(self.animations)))
        write_padding(f, multiple=4)

        index_start = f.tell()
        for i in range(len(self.animations)):
            j3d.write_uint16(f, i)

        j3d.write_padding(f, multiple=4)

        stringtable = j3d.StringTable()

        for anim in self.animations:
            stringtable.strings.append(anim.name)

        stringtable_start = f.tell()
        stringtable.write(f, stringtable.strings)

        j3d.write_padding(f, multiple=4)

        matindex_start = f.tell()
        for anim in self.animations:
            j3d.write_uint8(f, anim.matindex)

        j3d.write_padding(f, multiple=4)

        center_start = f.tell()
        for anim in self.animations:
            for val in anim.center:
                write_float(f, val)

        j3d.write_padding(f, multiple=4)


        all_scales = []
        all_rotations = []
        all_translations = []
        for anim in self.animations:
            for axis in "UVW":
                # Set up offset for scale
                if len(anim.scale[axis]) == 1:
                    sequence = [anim.scale[axis][0].value]
                else:
                    sequence = []
                    for comp in anim.scale[axis]:
                        sequence.append(comp.time)
                        sequence.append(comp.value)
                        sequence.append(comp.tangentIn)
                        if self.tan_type == 1 :
                            sequence.append(comp.tangentOut)
                    
                offset = j3d.find_sequence(all_scales,sequence)
                if offset == -1:
                    offset = len(all_scales)
                    all_scales.extend(sequence)
                    
                anim._set_scale_offsets(axis, offset)

                # Set up offset for rotation
                if len(anim.rotation[axis]) == 1:
                    comp = anim.rotation[axis][0]
                    #angle = ((comp.value+180) % 360) - 180
                    sequence = [comp.value/rotscale]
                    #print("seq", sequence)
                else:
                    sequence = []
                    for comp in anim.rotation[axis]:
                        #angle = ((comp.value+180) % 360) - 180
                        sequence.append(comp.time)
                        sequence.append(comp.value/rotscale)
                        sequence.append(comp.tangentIn/rotscale)
                        if self.tan_type == 1 :
                            sequence.append(comp.tangentOut/rotscale)
                    #print("seq", sequence)
                offset = j3d.find_sequence(all_rotations, sequence)
                if offset == -1:
                    offset = len(all_rotations)
                    all_rotations.extend(sequence)
                anim._set_rot_offsets(axis, offset)
                """for comp in anim.rotation[axis]:
                    all_rotations.append(comp.frame)
                    all_rotations.append(comp.value/rotscale)
                    all_rotations.append(comp.tangentIn/rotscale)
                    all_rotations.append(comp.tangentOut/rotscale)

                """

                # Set up offset for translation
                if len(anim.translation[axis]) == 1:
                    sequence = [anim.translation[axis][0].value]
                else:
                    sequence = []
                    for comp in anim.translation[axis]:
                        sequence.append(comp.time)
                        sequence.append(comp.value)
                        sequence.append(comp.tangentIn)
                        if self.tan_type == 1 :
                            sequence.append(comp.tangentOut)
                    
                offset = j3d.find_sequence(all_translations, sequence)
                if offset == -1:
                    offset = len(all_translations)
                    all_translations.extend(sequence)
                anim._set_translation_offsets(axis, offset)
                
                """offset = len(all_translations)
                for comp in anim.translation[axis]:
                    all_translations.append(comp.frame)
                    all_translations.append(comp.value)
                    all_translations.append(comp.tangentIn)
                    all_translations.append(comp.tangentOut)"""

                

        scale_start = f.tell()
        for val in all_scales:
            write_float(f, val)

        j3d.write_padding(f, 4)

        rotations_start = f.tell()
        for val in all_rotations:
            """angle = ((val+180) % 360) - 180  # Force the angle between -180 and 180 degrees
            print(val, "becomes", angle)
            if angle >= 0:
                angle = (angle/180.0)*(2**15-1)
            else:
                angle = (angle/180.0)*(2**15)"""
            j3d.write_sint16(f, int(val))

        j3d.write_padding(f, 4)

        translations_start = f.tell()
        for val in all_translations:
            #print(val)
            write_float(f, val)

        j3d.write_padding(f, 32)

        total_size = f.tell()

        f.seek(matrix_anim_start)
        for anim in self.animations:
            for axis in "UVW":
                j3d.write_uint16(f, len(anim.scale[axis])) # Scale count for this animation
                j3d.write_uint16(f, anim._scale_offsets[axis]) # Offset into scales
                j3d.write_uint16(f, self.tan_type) # Tangent type, 0 = only TangentIn; 1 = TangentIn and TangentOut


                j3d.write_uint16(f, len(anim.rotation[axis])) # Rotation count for this animation
                j3d.write_uint16(f, anim._rot_offsets[axis]) # Offset into rotations
                j3d.write_uint16(f, self.tan_type) # Tangent type, 0 = only TangentIn; 1 = TangentIn and TangentOut


                j3d.write_uint16(f, len(anim.translation[axis])) # Translation count for this animation
                j3d.write_uint16(f, anim._translation_offsets[axis])# offset into translations
                j3d.write_uint16(f, self.tan_type) # Tangent type, 0 = only TangentIn; 1 = TangentIn and TangentOut

        # Fill in all the placeholder values
        f.seek(filesize_offset)
        j3d.write_uint32(f, total_size)

        f.seek(ttk1_size_offset)
        j3d.write_uint32(f, total_size - ttk1_start)

        f.seek(count_offset)
        j3d.write_uint16(f, len(all_scales))
        j3d.write_uint16(f, len(all_rotations))
        j3d.write_uint16(f, len(all_translations))
        # Next come the section offsets

        j3d.write_uint32(f, matrix_anim_start   - ttk1_start)
        j3d.write_uint32(f, index_start         - ttk1_start)
        j3d.write_uint32(f, stringtable_start   - ttk1_start)
        j3d.write_uint32(f, matindex_start      - ttk1_start)
        j3d.write_uint32(f, center_start        - ttk1_start)
        j3d.write_uint32(f, scale_start         - ttk1_start)
        j3d.write_uint32(f, rotations_start     - ttk1_start)
        j3d.write_uint32(f, translations_start  - ttk1_start)
    
    @classmethod
    def match_bmd(cls, info, strings):
        btk = cls.from_table("", info)
        j3d.basic_animation.match_bmd(btk, strings)
        return btk.get_loading_information()
        