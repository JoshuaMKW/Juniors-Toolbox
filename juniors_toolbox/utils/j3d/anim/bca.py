from io import BytesIO
import struct
from typing import BinaryIO

from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs, write_jsystem_padding, j3d
from juniors_toolbox.utils.iohelper import read_float, read_sbyte, read_sint16, read_uint16, read_uint32, write_float, write_sbyte, write_sint16, write_ubyte, write_uint16, write_uint32
from juniors_toolbox.utils.j3d.anim.general_animation import BCAFILEMAGIC, BasicAnimation, find_sequence

BTKFILEMAGIC = b"J3D1bca1"

class BoneEntry():
    def __init__(self, value):
        self.value = value
        
    def convert_rotation(self, rotscale):
        self.value *= rotscale 

    def convert_rotation_inverse(self, rotscale):
        self.value /= rotscale 

     
    @classmethod
    def from_array(cls, offset, index, count, valarray):
        return cls(valarray[offset+index])
        
    def serialize(self):
        return self.value
    def __repr__(self):
        return "{0} ".format(self.value).__repr__()


class BoneAnim():
    def __init__(self):
        self.scale = {"X": [], "Y": [], "Z": []}
        self.rotation = {"X": [], "Y": [], "Z": []}
        self.translation = {"X": [], "Y": [], "Z": []}
        
        self.name = ""
        self.tan_inter = []
        
        self._scale_offsets = {}
        self._rot_offsets = {}
        self._translation_offsets = {}


    def add_scale(self, axis, comp):
        self.scale[axis].append(comp)
    
    def add_rotation(self, axis, comp):
        self.rotation[axis].append(comp)
        
    def add_translation(self, axis, comp):
        self.translation[axis].append(comp)
        
    def _set_scale_offsets(self, axis, val):
        self._scale_offsets[axis] = val

    def _set_rot_offsets(self, axis, val):
        self._rot_offsets[axis] = val

    def _set_translation_offsets(self, axis, val):
        self._translation_offsets[axis] = val
       

class BCA(BasicAnimation):
    def __init__(self, loop_mode=0, anglescale=0, duration=1):
        self.loop_mode = loop_mode
        self.duration = duration
        self.anglescale = anglescale
        self.animations = []
    
    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
        size = read_uint32(data)
        #print("Size of btk: {} bytes".format(size))
        sectioncount = read_uint32(data)
        assert sectioncount == 1

        svr_data = data.read(16)
        
        anf_start = data.tell()
        
        anf_magic = data.read(4)
        anf_sectionsize = read_uint32(data)

        loop_mode = read_sbyte(data)
        filler = read_sbyte(data)
        anglescale = 0
        rotScale = (2.0**anglescale) * (180.0 / 32768.0)
        #rotScale = 1
        duration = read_uint16(data)
        
        bca = cls(loop_mode, anglescale, duration)
        
        
        #print(hex(data.tell()))
        jointAnimCount = read_uint16(data)
        #print(jointAnimCount)
        scaleFloatCount = read_uint16(data)
        rotationShortsCount = read_uint16(data)
        translateFloatCount = read_uint16(data)
        #print(hex(data.tell()))
        jointAnimationEntriesOffset = read_uint32(data) + anf_start
        scaleFloatsOffset = read_uint32(data) + anf_start
        rotationShortsOffset = read_uint32(data) + anf_start
        translateFloatsOffset = read_uint32(data) + anf_start
        
        scaleDefault = None 
        rotationDefault = None 
        translateDefault = None 
        
        scaleFloats = []
        rotationShorts = []
        translateFloats = []
        #print("jointanims:", hex(jointAnimationEntriesOffset), "count:", jointAnimCount)
        #print("scalefloats:", hex(scaleFloatsOffset))
        #print("rotations:", hex(rotationShortsOffset))
        #print("translate floats:", hex(translateFloatsOffset))
        # Scale value bank
        data.seek(scaleFloatsOffset)
        #print("Scale count:", scaleFloatCount)
        for i in range(scaleFloatCount): 
            scaleFloats.append(read_float(data))
        
        # Rotation value bank
        #print("Rotation count:", rotationShortsCount)
        data.seek(rotationShortsOffset)
        for i in range(rotationShortsCount): 
            rotationShorts.append(read_sint16(data))
            
        # Translate value bank
        data.seek(translateFloatsOffset)
        #print("Translation count:", translateFloatCount)
        #print(hex(translateFloatsOffset), translateFloatCount)
        
        for i in range(translateFloatCount): 
            translateFloats.append(read_float(data))
        
        animations = []
        
        data.seek(jointAnimationEntriesOffset)
        for i in range(jointAnimCount):
            jointanim = BoneAnim()
            
            values = struct.unpack(">"+"H"*18, data.read(0x24))
                
            x_scale, x_rot, x_trans = values[:2], values[2:4], values[4:6]
            y_scale, y_rot, y_trans = values[6:8], values[8:10], values[10:12]
            z_scale, z_rot, z_trans = values[12:14], values[14:16], values[16:18]
            # Scale
            countX, offsetX = x_scale
            countY, offsetY = y_scale
            countZ, offsetZ = z_scale 
            
            #print("Scale")
            
            for j in range(countX):
                jointanim.add_scale("X", BoneEntry.from_array(offsetX, j, countX, scaleFloats))
                
            for j in range(countY):
                jointanim.add_scale("Y", BoneEntry.from_array(offsetY, j, countY, scaleFloats))
                
            for j in range(countZ):
                jointanim.add_scale("Z", BoneEntry.from_array(offsetZ, j, countZ, scaleFloats))
            
            # Rotation 
            countX, offsetX = x_rot
            countY, offsetY = y_rot
            countZ, offsetZ = z_rot
            
            #print("Rotation")
            for j in range(countX):
                comp = BoneEntry.from_array(offsetX, j, countX, rotationShorts)
                comp.convert_rotation(rotScale)
                jointanim.add_rotation("X", comp)
                
            for j in range(countY):
                comp = BoneEntry.from_array(offsetY, j, countY, rotationShorts)
                comp.convert_rotation(rotScale)
                jointanim.add_rotation("Y", comp)
                
            for j in range(countZ):
                comp = BoneEntry.from_array(offsetZ, j, countZ, rotationShorts)
                comp.convert_rotation(rotScale)
                jointanim.add_rotation("Z", comp)
                
            # Translate
            countX, offsetX, = x_trans
            countY, offsetY, = y_trans
            countZ, offsetZ, = z_trans
            
            #print("Translation")
            for j in range(countX):
                jointanim.add_translation("X", BoneEntry.from_array(offsetX, j, countX, translateFloats))
                
            for j in range(countY):
                jointanim.add_translation("Y", BoneEntry.from_array(offsetY, j, countY, translateFloats))
                
            for j in range(countZ):
                jointanim.add_translation("Z", BoneEntry.from_array(offsetZ, j, countZ, translateFloats))
                
            animations.append(jointanim)
        
        bca.animations = animations
        return bca
        
    def get_children_names(self):
        joints = []
        for i in range( len( self.animations )):
            if self.animations[i].name != "":
                joints.append( self.animations[i].name)
            else:
                joints.append("Joint " + str(i) )
        return joints           
    
    def get_loading_information(self):
        info = []
        info.append( [ "Loop Mode:", j3d.loop_mode[self.loop_mode], "Angle Scale:", self.anglescale, "Duration:", self.duration] )
        info.append( ["Joint Number", "Tangent Interpolation (Unused)","Component"])
        
        for i in range(self.duration):
            info[1].append("Frame " + str(i) )
        
        i = len( info ) 
        
        count = 0
        
        for anim in self.animations:
            info.append( ["Joint " + str(count)] )
            things = ["Scale X:", "Scale Y:", "Scale Z:", "Rotation X:", "Rotation Y:", "Rotation Z:",
                "Translation X:", "Translation Y:", "Translation Z:"]
            
            for j in range (len ( things ) ):    
                comp = things[j]
                if j == 0:
                    info[i].append("LLLL")
                    info[i].append(comp)
                    """    
                    elif j == 1:
                        if anim.tan_inter == 0:
                            info.append( ["LLLL", comp] )
                        elif anim.tan_inter == 1:
                            info.append( ["SSSS", comp] )
                    """
                else:
                    info.append( ["", "LLLL", comp] )
                
                comp_dict = {}
                if comp[0:1] == "S":
                    comp_dict = anim.scale
                elif comp[0:1] == "R":
                    comp_dict = anim.rotation
                else: 
                    comp_dict = anim.translation
                    

                array = comp_dict[ comp[-2:-1] ]
                
                for value in array:
                    info[i + j].append(value.value)
                

            i = len(info)
            
            count += 1         

        return info  
     
    @classmethod
    def empty_table(cls, created):
        info = []
        info.append( ["Loop_mode", "", "Angle Scale:", "", "Duration:", created[3], "Tan Type:", j3d.tan_type[1] ] )
        info.append( ["Bone Name", "Tangent Interpolation", "Component"] )

        for i in range( int(created[3])):
            info[1].append("Frame " + str(i) )
        
        for i in range( int(created[1]) ):
            info.append( ["Joint " + str(i),"SSSS", "Scale X:"] )

            
            things = [ [ "", "SSSS", "Scale Y:"], ["", "SSSS", "Scale Z:"],
                        ["", "LLLL", "Rotation X:"],["", "LLLL", "Rotation Y:"], ["", "LLLL", "Rotation Z:"],
                        ["", "SSSS", "Translation X:"],["", "SSSS", "Translation Y:"], ["", "SSSS", "Translation Z:"] ]
            for comp in things:
                info.append( comp )
        return info          
     
    @classmethod
    def from_table(cls, f, info):
        bca = cls(int(info[0][1]), int(info[0][3]), int(info[0][5]))
       
        
        for i in range( int( len(info) / 9 )   ): #for each bone
            line = 9 * i + 2
            current_anim = BoneAnim()
            
            for j in range(9):  #for each of thing in scale/rot/trans x/y/z/       
                xyz = "XYZ"
                xyz = xyz[j%3: j%3 + 1]
                              
                for k in range(2, len(info[line + j])): #for frame
                    if info[line + j][k] != "":
                        comp = BoneEntry(float(info[line + j][k]))
                                       
                        if j < 3:
                            current_anim.add_scale(xyz, comp)
                            #print("scale " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
                        elif j < 6:
                            """
                            if comp.value < -180:
                                comp = comp + 360
                            elif comp.value > 180:
                                comp = comp - 360
                            """
                            current_anim.add_rotation(xyz, comp)
                            #print("rot " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
                        else:
                            current_anim.add_translation(xyz, comp)
                            #print("trans " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
           
            bca.animations.append(current_anim)
        if f == "":
            return bca
        else:
            with open(f, "wb") as f:
                bca.write_bca(f)
                f.close()
            
    def to_bytes(self) -> bytes:
        f = BytesIO()
        f.write(BCAFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)
        
        anf1_start = f.tell()
        f.write(b"ANF1")
        
        anf1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for anf1 size
        write_ubyte(f, self.loop_mode)
        #write_sbyte(f, self.anglescale)
        write_sbyte(f, -1)
        
        rotscale = (2.0**self.anglescale)*(180.0 / 32768.0)
        
        write_uint16(f, self.duration)
        
        #counts
        
        write_uint16(f, len( self.animations ))
        
        #0x30        
      
        count_offset = f.tell()
        f.write(b"1+1=11")  # Placeholder for scale, rotation and translation count
        
        data_offsets = f.tell()
        f.write(b"toadettebestgirl") #placeholder for offsets
        
        write_jsystem_padding(f, multiple=32)
        bone_anim_start = f.tell()
        
        f.write(b"\x00"*(0x24*len(self.animations))) #placeholder for stuff
        
        write_jsystem_padding(f, multiple=32)
        
        all_scales = []
        all_rotations = []
        all_translations = []
        for anim in self.animations:
            for axis in "XYZ":
                # Set up offset for scale
                if len(anim.scale[axis]) == 1:
                    sequence = [anim.scale[axis][0].value]
                else:
                    sequence = []
                    for comp in anim.scale[axis]:
                       
                        sequence.append(comp.value)

                    
                offset = find_sequence(all_scales,sequence)
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
                        sequence.append(comp.value/rotscale)
                    #print("seq", sequence)
                offset = find_sequence(all_rotations, sequence)
                if offset == -1:
                    offset = len(all_rotations)
                    all_rotations.extend(sequence)
                anim._set_rot_offsets(axis, offset)

                # Set up offset for translation
                if len(anim.translation[axis]) == 1:
                    sequence = [anim.translation[axis][0].value]
                else:
                    sequence = []
                    for comp in anim.translation[axis]:
                        sequence.append(comp.value)
                    
                offset = find_sequence(all_translations, sequence)
                if offset == -1:
                    offset = len(all_translations)
                    all_translations.extend(sequence)
                anim._set_translation_offsets(axis, offset)
     
                

        scale_start = f.tell()
        for val in all_scales:
            write_float(f, val)

        write_jsystem_padding(f, 32)

        rotations_start = f.tell()
        for val in all_rotations:
            write_sint16(f, int(val))

        write_jsystem_padding(f, 32)

        translations_start = f.tell()
        for val in all_translations:
            #print(val)
            write_float(f, val)

        write_jsystem_padding(f, 32)

        total_size = f.tell()

        f.seek(bone_anim_start)
        for anim in self.animations:
            for axis in "XYZ":
                write_uint16(f, len(anim.scale[axis])) # Scale count for this animation
                write_uint16(f, anim._scale_offsets[axis]) # Offset into scales
               
                write_uint16(f, len(anim.rotation[axis])) # Rotation count for this animation
                write_uint16(f, anim._rot_offsets[axis]) # Offset into rotations
                
                write_uint16(f, len(anim.translation[axis])) # Translation count for this animation
                write_uint16(f, anim._translation_offsets[axis])# offset into translations


        # Fill in all the placeholder values
        f.seek(filesize_offset)
        write_uint32(f, total_size)

        f.seek(anf1_size_offset)
        write_uint32(f, total_size - anf1_start)

        f.seek(count_offset)
        write_uint16(f, len(all_scales))
        write_uint16(f, len(all_rotations))
        write_uint16(f, len(all_translations))
        # Next come the section offsets

        write_uint32(f, bone_anim_start     - anf1_start)
        write_uint32(f, scale_start         - anf1_start)
        write_uint32(f, rotations_start     - anf1_start)
        write_uint32(f, translations_start  - anf1_start)

        return f.getvalue()
    
    
    @classmethod
    def from_bck(cls, bck):
        bca = cls(bck.loop_mode, bck.anglescale, bck.duration)
        
        for joint_anim in bck.animations:
            new_bone_anim = BoneAnim()
            
            if len( joint_anim.scale["X"] ) < bck.duration:
                val_array = interpolate( joint_anim.scale["X"], joint_anim.tan_inter[0] )
                new_bone_anim.scale["X"] = val_array
            else:
                new_bone_anim.scale["X"] = joint_anim.scale["X"]
            
            if len( joint_anim.scale["Y"] ) < bck.duration:
                val_array = interpolate( joint_anim.scale["Y"], joint_anim.tan_inter[1])
                new_bone_anim.scale["Y"] = val_array
            else:
                new_bone_anim.scale["Y"] = joint_anim.scale["Y"]
            
            if len( joint_anim.scale["Z"] ) < bck.duration:   
                val_array = interpolate( joint_anim.scale["Z"], joint_anim.tan_inter[2])
                new_bone_anim.scale["Z"] = val_array
            else:
                new_bone_anim.scale["Z"] = joint_anim.scale["Z"]
                
            rotscale = (2.0**bck.anglescale)*(180.0 / 32768.0)
            
            if len( joint_anim.rotation["X"] ) < bck.duration:  
                val_array = interpolate( joint_anim.rotation["X"], joint_anim.tan_inter[3])
                new_bone_anim.rotation["X"] = val_array
            else:
                new_bone_anim.rotation["X"] = joint_anim.rotation["X"]
            #for entry in new_bone_anim.rotation["X"]:
                #entry.convert_rotation(rotscale)
                #pass
            
            if len( joint_anim.rotation["Y"] ) < bck.duration:  
                val_array = interpolate( joint_anim.rotation["Y"], joint_anim.tan_inter[4])
                new_bone_anim.rotation["Y"] = val_array
            else:
                new_bone_anim.rotation["Y"] = joint_anim.rotation["Y"]            
            #for entry in new_bone_anim.rotation["Y"]:
                #entry.convert_rotation(rotscale)
                #pass
            
            if len( joint_anim.rotation["Z"] ) < bck.duration:  
                val_array = interpolate( joint_anim.rotation["Z"], joint_anim.tan_inter[5])
                new_bone_anim.rotation["Z"] = val_array
            else:
                new_bone_anim.rotation["Z"] = joint_anim.rotation["Z"]            

            #for entry in new_bone_anim.rotation["Z"]:
                #entry.convert_rotation(rotscale)   
                #pass
            
            if len( joint_anim.translation["X"] ) < bck.duration:  
                val_array = interpolate( joint_anim.translation["X"] , joint_anim.tan_inter[6])
                new_bone_anim.translation["X"] = val_array
            else:
                new_bone_anim.translation["X"] = joint_anim.translation["X"]
            
            if len( joint_anim.translation["Y"] ) < bck.duration:  
                val_array = interpolate( joint_anim.translation["Y"], joint_anim.tan_inter[7] )
                new_bone_anim.translation["Y"] = val_array
            else:
                new_bone_anim.translation["Y"] = joint_anim.translation["Y"]
                
            if len( joint_anim.translation["Z"] ) < bck.duration:  
                val_array = interpolate( joint_anim.translation["Z"], joint_anim.tan_inter[8] )
                new_bone_anim.translation["Z"] = val_array
            else:
                new_bone_anim.translation["Z"] = joint_anim.translation["Z"]
            
            bca.animations.append(new_bone_anim)
        
        return bca
        
        
def interpolate(entry_array, tantype = 0):

    all_values = []
    
    if len( entry_array) == 1:
        return entry_array

    for i in range( len( entry_array ) - 1):
        some_values = []
        if tantype == 0:
            some_values = inter_helper(entry_array[i], entry_array[i + 1])
        else:
            some_values = inter_cubic( entry_array[i], entry_array[i + 1] )
        for value in some_values:
            all_values.append(value)
    
    all_values.append( entry_array[-1] )
    
    return all_values
    
def inter_helper(start, end):
    values = []
    for i in range(end.time - start.time):
        comp = BoneEntry( start.value + (i / (end.time - start.time)) * (end.value - start.value))
        values.append( comp )
    #print (values)
    return values
    
def inter_cubic(start, end):
    values = []
    for i in range(end.time - start.time):
        deriv = (end.value - start.value) / (end.time - start.time)
        a = 2 * start.value - 2 * end.value  + 2 * deriv
        b = -3 * start.value + 3 * end.value - 3 * deriv
        c = deriv
        d = start.value
        x = (i / (end.time - start.time)) 
        comp = BoneEntry( a * x **3 + b * x **2 + c * x + d  )
        values.append( comp )
    print("generated cubic values")
    print (values)
    return values