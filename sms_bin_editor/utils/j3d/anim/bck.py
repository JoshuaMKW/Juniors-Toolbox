import struct 
from collections import OrderedDict

import sys, inspect

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d


BCKFILEMAGIC = b"J3D1bck1"

class bone_anim(object):
    def __init__(self):
        self.scale = {"X": [], "Y": [], "Z": []}
        self.rotation = {"X": [], "Y": [], "Z": []}
        self.translation = {"X": [], "Y": [], "Z": []}
        self.name = ""
        
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
        
    def _set_scale_offsets(self, axis, val):
        self._scale_offsets[axis] = val

    def _set_rot_offsets(self, axis, val):
        self._rot_offsets[axis] = val

    def _set_translation_offsets(self, axis, val):
        self._translation_offsets[axis] = val
        
    @classmethod 
    def get_empty_bone_anim(cls, name, values = [1.0, 1.0, 1.0, 0, 0, 0, 0, 0, 0], angle_scale = 0):
        new_anim = bone_anim()
        new_anim.name = name;

            
        new_anim.add_scale("X", j3d.AnimComponent(0, values[0] ))
        new_anim.add_scale("Y", j3d.AnimComponent(0, values[1]))
        new_anim.add_scale("Z", j3d.AnimComponent(0, values[2]))
        new_anim.add_rotation("X", j3d.AnimComponent(0, values[3]))
        new_anim.add_rotation("Y", j3d.AnimComponent(0, values[4]))
        new_anim.add_rotation("Z", j3d.AnimComponent(0, values[5]))
        new_anim.add_translation("X", j3d.AnimComponent(0, values[6]))
        new_anim.add_translation("Y", j3d.AnimComponent(0, values[7]))
        new_anim.add_translation("Z", j3d.AnimComponent(0, values[8]))
        
        
        return new_anim


class bck(j3d.basic_animation):

    def __init__(self, loop_mode = 0, anglescale = 0, duration = 1, tantype = 1):
        self.loop_mode = loop_mode
        self.anglescale = anglescale
        self.duration = duration
        self.sound = None
        
        self.animations = []
    
        if tantype == 0 or tantype == 1:
            self.tan_type = tantype
        else:
            self.tan_type = 1
    
    @classmethod
    def from_anim(cls, f):
        size = j3d.read_uint32(f)
        
        sectioncount = j3d.read_uint32(f)
        assert sectioncount == 1
        
        svr_data = f.read(12)
        sound = j3d.read_uint32(f)
        #print("sound " + str(sound) )
        
        ank_start = f.tell()
        ank_magic = f.read(4) #ank1
        ank_size = j3d.read_uint32(f)
        
        loop_mode = j3d.read_uint8(f)
        angle_scale = j3d.read_sint8(f) 
        rotscale = (2.0**angle_scale) * (180.0 / 32768.0);
        duration = j3d.read_uint16(f)
        bck = cls(loop_mode, angle_scale, duration, 1)
        
        bone_count = read_uint16(f)
        scale_count = read_uint16(f)
        rotation_count = read_uint16(f)
        trans_count = read_uint16(f)
        
        bone_offset = read_uint32(f) + ank_start
        scale_offset = read_uint32(f) + ank_start
        rotation_offset = read_uint32(f) + ank_start
        trans_offset = read_uint32(f) + ank_start
        
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
        trans = []
        f.seek(trans_offset)
        for i in range(trans_count):
            trans.append(read_float(f))
        
        tangent_type = 0
        
        f.seek(bone_offset)
        for i in range(bone_count):
            values = struct.unpack(">"+"H"*27, f.read(0x36))
            
            x_scale, x_rot, x_trans = values[:3], values[3:6], values[6:9]
            y_scale, y_rot, y_trans = values[9:12], values[12:15], values[15:18]
            z_scale, z_rot, z_trans = values[18:21], values[21:24], values[24:27]
            
            bone_animation = bone_anim()
            
            inter_count = 0
            
            #default tangent interpolation is smooth
            for scale, axis in ((x_scale, "X"), (y_scale, "Y"), (z_scale, "Z")):
                count, offset, tan_type = scale 
   
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    #print( offset, j, count,tan_type, len(scales) )
                    comp = j3d.AnimComponent.from_array(offset, j, count, scales, tan_type)
                    if comp.tangentIn == 0:
                        bone_animation.tan_inter[inter_count] = 1
              
                    bone_animation.add_scale(axis, comp)
                    #print(comp)
                if bone_animation.tan_inter[inter_count] == -1:
                    bone_animation.tan_inter[inter_count] = 0
                inter_count += 1
            
            for rotation, axis in ((x_rot, "X"), (y_rot, "Y"), (z_rot, "Z")):
                count, offset, tan_type = rotation 
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    comp = j3d.AnimComponent.from_array(offset, j, count, rotations, tan_type)
                    comp.convert_rotation(rotscale)
                    if comp.tangentIn != 0:
                        bone_animation.tan_inter[inter_count] = 0
                   
                    bone_animation.add_rotation(axis, comp)
                    #print(comp)
                if bone_animation.tan_inter[inter_count] == -1:
                    bone_animation.tan_inter[inter_count] = 1
                inter_count += 1   
                    
            for translation, axis in ((x_trans, "X"), (y_trans, "Y"), (z_trans, "Z")):
                count, offset, tan_type = translation
                tangent_type = max(tan_type, tangent_type)
                for j in range(count):
                    comp = j3d.AnimComponent.from_array(offset, j, count, trans, tan_type)
                    if comp.tangentIn == 0:
                        bone_animation.tan_inter[inter_count] = 1
                    bone_animation.add_translation(axis, comp)
                    #print(comp)
                if bone_animation.tan_inter[inter_count] == -1:
                    bone_animation.tan_inter[inter_count] = 0
                inter_count += 1   
            bck.animations.append(bone_animation)
        bck.tan_type = tangent_type
        
        if sound != 0xffffffff:
            f.seek(sound)
            num_entries = j3d.read_uint16(f)
            f.read(6)
            
            sound_entries = []
            
            for i in range(num_entries):
            
                sound_id = j3d.read_uint32(f)
                start_time = j3d.read_float(f)
                end_time = j3d.read_float(f)
                coarse_pitch = j3d.read_float(f)
                flags = j3d.read_uint32(f)
                volume = j3d.read_uint8(f)
                fine_pitch = j3d.read_uint8(f)
                loop_count = j3d.read_uint8(f)
                pan = j3d.read_uint8(f)
                unk_byte = j3d.read_uint8(f)
                
                f.read(0x7)
                
                entry = sound_entry(sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte)
                sound_entries.append(entry)
                
            bck.sound = sound_entries
            
        
        return bck
    
    @classmethod
    def from_maya_anim(cls, filepath):
        lines = filepath.readlines()
        duration = int( lines[6][lines[6].find(" "): lines[6].find(";")] )
        #duration -= int( lines[5][lines[5].find(" "): lines[5].find(";")] )
        max_angle = 0
        
        print (duration)
        i = 7
        bck = cls(1, 1, duration)
        
        current_bone = lines[i].split()[3]
        
        #iterate through all the lines
        while ( i < len(lines) ):
        
            # make a new bone
            new_bone_name = lines[i].split()[3]
            current_bone = new_bone_name
            new_bone = bone_anim()
            new_bone.name = new_bone_name
            bck.animations.append(new_bone)
            
            # while it is the same bone animation
            while(new_bone_name == current_bone):
                current_bone = new_bone_name
                
                #jump to keys for the entry  
                
                values = lines[i].split()
                thing = values[2]
                
                i += 8     
                
                tan_inter_index = 0
                tan_inter_type = 1
   
                if thing.startswith("r"):
                    tan_inter_index += 3
                elif thing.startswith("t"):
                    tan_inter_index += 6
   
                if thing.endswith("Y"):
                    tan_inter_index += 1
                elif thing.endswith("Z"):
                    tan_inter_index += 2
   
                #read the keyframes
                while( not "}" in lines[i]):
                    values = lines[i].split()
                    
                    new_entry = j3d.AnimComponent(int(values[0]), float(values[1]))
                    
                    
                    
                    if values[2].lower() in ["linear", "fixed"]:
                        tan_inter_type = 0
                    
                    if len(thing) == 6:
                        new_bone.add_scale( thing[-1], new_entry )
                    elif len(thing) == 7:
                        max_angle = max( abs(max_angle), abs(new_entry.value) )
                        new_bone.add_rotation( thing[-1], new_entry )
                    elif thing.startswith("translate"):
                        new_bone.add_translation( thing[-1], new_entry )        
                        
                    
                    
                    i += 1
                
                i += 2
                
                if( i < len(lines) ):
                    new_bone_name = lines[i].split()[3]
                else:
                    new_bone_name = current_bone + "asdf"
                new_bone.tan_inter[tan_inter_index] = tan_inter_type
        
        bck.anglescale = int( max_angle / 180) ;
        
        for anim in bck.animations :
            for axis in {"X", "Y", "Z"} :
                if len( anim.scale[axis] ) == 0:
                    new_entry = j3d.AnimComponent(0, 1.0)
                    anim.add_scale(axis, new_entry)
                if len( anim.rotation[axis] ) == 0:
                    new_entry = j3d.AnimComponent(0, 0)
                    anim.add_rotation(axis, new_entry)
                if len( anim.translation[axis] ) == 0:
                    new_entry = j3d.AnimComponent(0, 0)
                    anim.add_translation(axis, new_entry)

        
        
        return bck
  
    @classmethod 
    def from_blender_bvh(cls, filepath):
        import re
        lines = filepath.read().splitlines()
        lines = [ line for line in lines if line != ""]
        
        
        #process motion
        try:
            motion_index = lines.index("MOTION")
            motion_line = motion_index
        except:
            return
        
        motion_index += 1
        #print( lines[motion_index] )
        duration_regex = "^Frames: (\d+)$"
        m = re.match(duration_regex, lines[motion_index])
        if m is None:
            return
        bck = cls( duration = int(m.group(1)) )
        motion_index += 2
        
        all_values = []
        
        while motion_index < len(lines):
            curr_values = lines[motion_index].split()
            #print( curr_values)
            all_values.append(curr_values)
            motion_index += 1
        all_values =[[row[i] for row in all_values] for i in range(len(all_values[0]))]
        
        #turn the array into a bunch of animcomponents
        for i in range( len(all_values) ):
            for j in range( len(all_values[i] ) ):
                all_values[i][j] = j3d.AnimComponent(j, all_values[i][j])
        #print( all_values)
        
        #process the bones
        assert( lines[0] == "HIERARCHY" )  

        hierachy_index = 1
        values_index = 0
        max_rotation = 0
        
        
        while hierachy_index < motion_line:
            #print(hierachy_index)
            bone_regex = "^\s*(ROOT|JOINT) (\S*)$"
            m = re.match(bone_regex, lines[hierachy_index])
            
            if m is None:
                return bck
            curr_bone = bone_anim()
            curr_bone.name = m.group(2)
            #print(curr_bone.name)
            
            curr_bone.add_scale( "X", j3d.AnimComponent(0, 1.0) )
            curr_bone.add_scale( "Y", j3d.AnimComponent(0, 1.0) )
            curr_bone.add_scale( "Z", j3d.AnimComponent(0, 1.0) )
            
            
            hierachy_index += 3 #to get to channels
            channels = lines[hierachy_index]
            for axis in ["Xposition", "Yposition", "Zposition", "Xrotation", "Yrotation", "Zrotation"]:
                if channels.find(axis) != -1:
                    #the particular channel is in there
                    if axis.find("position") != -1:
                        #if the axis is a position
                        for comp in all_values[values_index]:
                            curr_bone.add_translation( axis[0], comp)
                        values_index += 1
                    else:
                        #if the axis is a rotation
                        for comp in all_values[values_index]:
                            curr_bone.add_rotation( axis[0], comp)
                            max_rotation = max(float(comp.value), max_rotation)    
                        values_index += 1
                else:
                    if axis.find("position") != -1:
                        curr_bone.add_translation( axis[0], j3d.AnimComponent(0, 0.0) )
                    else:
                        curr_bone.add_rotation( axis[0], j3d.AnimComponent(0, 0.0) )   
            
            
            hierachy_index += 1
            
            if lines[hierachy_index].strip() == "End Site":
                hierachy_index += 3
            while lines[hierachy_index].strip() == "}":
                hierachy_index += 1
            
            bck.animations.append(curr_bone)
        
        bck.anglescale = int( max_rotation / 180) ;
        
        return bck
        
    
    def from_fbx_anim(self):
         
        return self.get_loading_information()

    
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
        info.append( [ "Loop Mode:", j3d.loop_mode[self.loop_mode], "Angle Scale:", self.anglescale, "Duration:", self.duration, "Tan Type:", self.tan_type] )
        
        info.append( ["Bone Name", "Tangent Interpolation", "Component"])
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []
        
        i = len( info ) 
        
        count = 0
        
        for anim in self.animations:
            if anim.name == "":
                info.append( ["Joint " + str(count)] )
            else:
                info.append( [anim.name] )
            things = ["Scale X:", "Scale Y:", "Scale Z:", "Rotation X:", "Rotation Y:", "Rotation Z:",
                "Translation X:", "Translation Y:", "Translation Z:"]
            #print(anim.tan_inter)
            for j in range (len ( things ) ):    # for each srt xyz component
                comp = things[j]
                if j == 0:
                    if anim.tan_inter[j] == 1:
                        info[i].append( "SSSS")                     
                    else:
                        info[i].append( "LLLL" )
                    info[i].append(comp)
                    """
                    elif j == 1:
                        if anim.tan_inter == 0:
                            info.append( ["LLLL", comp] )
                        elif anim.tan_inter == 1:
                            info.append( ["SSSS", comp] ) """
                else:
                    if anim.tan_inter[j] == 1:
                        
                        info.append( ["", "SSSS", comp] )
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
                
                #print(array)                          
                 
                
                keyframes_dictionary = j3d.combine_dicts(array, keyframes_dictionary)
            i = len(info)
            
            count += 1
            
        write_values(info, keyframes_dictionary, 1)
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
    def single_mat(cls):
        info = []
        info.append([ "Joint #", "SSSS", "Scale X:"])
        things = [ [ "", "SSSS", "Scale Y:"], ["", "SSSS", "Scale Z:"],
                        ["", "LLLL", "Rotation X:"],["", "LLLL", "Rotation Y:"], ["", "LLLL", "Rotation Z:"],
                        ["", "SSSS", "Translation X:"],["", "SSSS", "Translation Y:"], ["", "SSSS", "Translation Z:"] ]
        for comp in things:
            info.append( comp )
        return info
    
    @classmethod
    def from_table(cls, f, info, sound_data = None):
        #print("loop mode " + str( info[0][1] ) )
        bck = cls(int(info[0][1]), int(info[0][3]), int(info[0][5]))
        
        #print(sound_data)
        bck.sound = sound_data
        if len(info[0]) >= 7 and info[0][7] != "":
            bck.tan_type = int( info[0][7] )
        
        keyframes = []
        
        for i in range(3, len( info[1] ) ):
            if info[1][i] != "":
                text = info[1][i][6:]
                
                text = int(text)
                keyframes.append(text)
        
        #print("keyframes")
        #print (keyframes)
        
        for i in range( int( len(info) / 9 )   ): #for each bone
            line = 9 * i + 2
            current_anim = bone_anim()
            
            current_anim.name = info[line][0]
            """
            if info[line + 1][0].startswith("S"):
                current_anim.tan_inter = 1
            """
            for j in range(9):  #for each of thing in scale/rot/trans x/y/z/       
                xyz = "XYZ"
                xyz = xyz[j%3: j%3 + 1]
                              
                for k in range(3, len(info[line + j])): #for each keyframe
                    if info[line + j][k] != "":
                        try:
                            comp = j3d.AnimComponent( keyframes[k-3], float(info[line + j][k]))
                            
                        except:
                            comp = j3d.AnimComponent( bck.duration, float(info[line + j][k]) )
                        
                        if info[line + j][1].startswith("S"):
                            current_anim.tan_inter[j] = 1
                        else:
                            current_anim.tan_inter[j] = 0                                               
                        
                        if j < 3:
                            current_anim.add_scale(xyz, comp)
                            #print("scale " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
                        elif j < 6:
                            """if comp.value < -180 * bck.anglescale:
                                comp.value = comp.value + 360 * bck.anglescale
                            elif comp.value > 180 * bck.anglescale:
                                comp.value = comp.value - 360 * bck.anglescale"""
                            current_anim.add_rotation(xyz, comp)
                            #print("rot " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
                        else:
                            current_anim.add_translation(xyz, comp)
                            #print("trans " + xyz + " " + str(keyframes[k-2]) + ", " + str( float(info[line + j][k])))
            
             #calculate tangents
           
            for j in range(9):
                xyz = "XYZ"
                xyz = xyz[j%3: j%3 + 1]
                if j < 3:
                    current_anim.scale[xyz] = j3d.make_tangents(current_anim.scale[xyz], current_anim.tan_inter[j])
                if j < 6:
                    current_anim.rotation[xyz] = j3d.make_tangents(current_anim.rotation[xyz], current_anim.tan_inter[j])
                else:
                    current_anim.translation[xyz] = j3d.make_tangents(current_anim.translation[xyz], current_anim.tan_inter[j])
            
            bck.animations.append(current_anim)
        if f == "":
            #print("no saving")
            return bck
        else:
            with open(f, "wb") as f:
                bck.write_bck(f)
                f.close()
   
    
    def write_bck(self, f):
        f.write(BCKFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        j3d.write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)

        ank1_start = f.tell()
        f.write(b"ANK1")
        
        ttk1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for ttk1 size
        j3d.write_uint8(f, self.loop_mode)
        j3d.write_sint8(f, self.anglescale)
        
        rotscale = (2.0**self.anglescale)*(180.0 / 32768.0)
        
        j3d.write_uint16(f, self.duration)
        
        j3d.write_uint16(f, len( self.animations ))
        
        #0x30        
      
        count_offset = f.tell()
        f.write(b"1+1=11")  # Placeholder for scale, rotation and translation count
        
        data_offsets = f.tell()
        f.write(b"toadettebestgirl") #placeholder for offsets
        
        write_padding(f, multiple=32)
        bone_anim_start = f.tell()
        
        f.write(b"\x00"*(0x36*len(self.animations))) #placeholder for stuff
        
        write_padding(f, multiple=32)
        
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
     
                

        scale_start = f.tell()
        for val in all_scales:
            write_float(f, val)

        j3d.write_padding(f, 32)

        rotations_start = f.tell()
        for val in all_rotations:
            
            val = int(val)
            if val <= -32767:
                val = -32767
            elif val > 32767:
                val = 32767
            
            #try:
            j3d.write_sint16(f, val )
            """except:
                print(val)"""

        j3d.write_padding(f, 32)

        translations_start = f.tell()
        for val in all_translations:
            #print(val)
            write_float(f, val)

        j3d.write_padding(f, 32)

        total_size = f.tell()

        f.seek(bone_anim_start)
        for anim in self.animations:
            for axis in "XYZ":
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
        j3d.write_uint32(f, total_size - ank1_start)

        f.seek(count_offset)
        j3d.write_uint16(f, len(all_scales))
        j3d.write_uint16(f, len(all_rotations))
        j3d.write_uint16(f, len(all_translations))
        # Next come the section offsets

        j3d.write_uint32(f, bone_anim_start     - ank1_start)
        j3d.write_uint32(f, scale_start         - ank1_start)
        j3d.write_uint32(f, rotations_start     - ank1_start)
        j3d.write_uint32(f, translations_start  - ank1_start)
    
        
    
        if self.sound is not None and self.sound:
            print("write sound")
            #print( len(self.sound) )
            
            f.seek(0x1c)
            j3d.write_uint32(f, total_size)
            
            f.seek(total_size)
            j3d.write_uint16( f, len(self.sound) )
            j3d.write_uint8(f,  0xc)
            f.write(b"\x00"*5)
            
            for entry in self.sound:
                j3d.write_uint32(f, int(entry.sound_id))
                j3d.write_float(f, float(entry.start_time))
                j3d.write_float(f, float(entry.end_time))
                j3d.write_float(f, float(entry.coarse_pitch))
                j3d.write_uint32(f, int(entry.flags))
                j3d.write_uint8(f, int(entry.volume))
                j3d.write_uint8(f, int(entry.fine_pitch))
                j3d.write_uint8(f, int(entry.loop_count))
                j3d.write_uint8(f, int(entry.pan))
                j3d.write_uint8(f, int(entry.unk_byte))
                f.write(b"\x00"*0x7)
            
            f.write(b"\x00"*0x18)
            total_size = f.tell()
            f.seek(0x8)
            j3d.write_uint32(f, total_size)
            
    
    def write_anim(self, filepath, children, bones):
        with open(filepath, "w") as f:
            f.write("animVersion 1.1;\n")
            f.write("mayaVersion 2015;\n")
            f.write("timeUnit ntscf;\n")
            f.write("linearUnit cm;\n")
            f.write("angularUnit deg;\n")
            f.write("startTime 0;\n")
            f.write("endTime " + str(self.duration)+ ";\n")
            
            
            for i in range( len( self.animations) ):
                anim = self.animations[i]
                child = children[i]
                j = 0
                if len( anim.scale["X"] ) > 0:
                    write_single_comp(f, "scaleX", child, j, anim.scale["X"], anim.tan_inter[0], bones[i])
                    j += 1
                if len( anim.scale["Y"] ) > 0:
                    write_single_comp(f, "scaleY", child, j, anim.scale["Y"], anim.tan_inter[1], bones[i])
                    j += 1
                if len( anim.scale["Z"] ) > 0:
                    write_single_comp(f, "scaleZ", child, j, anim.scale["Z"], anim.tan_inter[2], bones[i])
                    j += 1
                if len( anim.rotation["X"] ) > 0:
                    write_single_comp(f, "rotateX", child, j, anim.rotation["X"], anim.tan_inter[3], bones[i])
                    j += 1
                if len( anim.rotation["Y"] ) > 0:
                    write_single_comp(f, "rotateY", child, j, anim.rotation["Y"], anim.tan_inter[4], bones[i])
                    j += 1
                if len( anim.rotation["Z"] ) > 0:
                    write_single_comp(f, "rotateZ", child, j, anim.rotation["Z"], anim.tan_inter[5], bones[i])
                    j += 1
                if len( anim.translation["X"] ) > 0:
                    write_single_comp(f, "translateX", child, j, anim.translation["X"], anim.tan_inter[6], bones[i])
                    j += 1
                if len( anim.translation["Y"] ) > 0:
                    write_single_comp(f, "translateY", child, j, anim.translation["Y"], anim.tan_inter[7], bones[i])
                    j += 1
                if len( anim.translation["Z"] ) > 0:
                    write_single_comp(f, "translateZ", child, j, anim.translation["Z"], anim.tan_inter[8], bones[i])
                    j += 1
            
        f.close()
    
    @classmethod
    def get_bck(cls, info):
        bck = cls.from_table("", info)    
        return bck
      
    @classmethod
    def match_bmd(cls, info, strings, filepath = None):
        bck = cls.from_table("", info)
        
        #bone_names = bck.get_children_names()
        #print("current bck bones")
        #print(bone_names)
        j3d.basic_animation.match_bmd(bck, strings)
        
        #bone_names = bck.get_children_names()
        #print("reduced bone names")
        #print(bone_names)
        
        #print("strings")
        #print(strings)
        
        def sort_function(animation):
            return strings.index(animation.name)

        z = sorted( bck.animations, key = sort_function)
        bck.animations = z
        
        jnt_vals = j3d.get_bone_transforms(filepath)
        rotscale = (2.0**bck.anglescale) * (180.0 / 32768.0);
        for i in range(len(jnt_vals)):
            jnt_vals[i][3] = jnt_vals[i][3] * rotscale    
            jnt_vals[i][4] *= rotscale
            jnt_vals[i][5] *= rotscale
        
        i = 0
        
        while i < len(strings) and i < len(bck.animations):
            
            anim = bck.animations[i]
            print(strings[i], anim.name)
            if anim.name != strings[i]:
                print(strings[i])
                bck.animations.insert(i, bone_anim.get_empty_bone_anim(strings[i], jnt_vals[i]) )
            i += 1
        #print("sorted bone names")
        #print( bck.get_children_names() )
        
        return bck.get_loading_information()
      
class sound_entry:
    def __init__(self, sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte):
        self.sound_id = sound_id
        self.start_time = start_time
        self.end_time = end_time
        self.coarse_pitch = coarse_pitch
        self.flags = flags
        self.volume = volume
        self.fine_pitch = fine_pitch
        self.loop_count = loop_count
        self.pan = pan
        self.unk_byte = unk_byte
    
    def __repr__(self):
        return "sound_id: {0}, start_time: {1}, end_time: {2}".format(self.sound_id, self.start_time, self.end_time)
    
    @classmethod
    def read_sound_data(cls, filepath):
        with open(filepath, "rb") as f:
            header = f.read(4)
                
            if header == b"Yaz0":
                decomp = BytesIO()
                decompress(f, decomp)
                #print(decomp)
                f = decomp
        
            f.seek(0x1c)
            
            offset = j3d.read_uint32(f) 
            if offset == 0xFFFFFFFF:
                return None
            
            f.seek( offset )
            
            num_entries = j3d.read_uint16(f)
            f.read(6)
            
            sound_entries = []
            
            for i in range(num_entries):
            
                sound_id = j3d.read_uint32(f)
                start_time = j3d.read_float(f)
                end_time = j3d.read_float(f)
                coarse_pitch = j3d.read_float(f)
                flags = j3d.read_uint32(f)
                volume = j3d.read_uint8(f)
                fine_pitch = j3d.read_uint8(f)
                loop_count = j3d.read_uint8(f)
                pan = j3d.read_uint8(f)
                unk_byte = j3d.read_uint8(f)
                
                f.read(0x7)
                
                entry = cls(sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte)
                sound_entries.append(entry)
            return sound_entries
    @classmethod
    def blank_entry(cls):
        return cls(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            
      
def write_single_comp(f, comp, children, j, array, tan_inter, name):
    f.write("anim " + comp[0:-1] + "." + comp + " " + comp + " " + name + " 0 " + str(children) + " " + str(j) + ";\n" )
    output_type = "linear"
    if len(comp) == 7:
        output_type = "angular"
    f.write("animData {\n\tinput time;\n\toutput "+output_type+";\n\tweighted 1;\n\tpreInfinity constant;\n\tpostInfinity constant;\n\tkeys {\n");
    
    if tan_inter == 0:
        tan_inter = "linear"
    else:
        tan_inter = "spline"
    
    
    
    for frame in array:
        f.write("\t\t" + str(frame.time) + " " + str(frame.value) + " " + tan_inter + " " + tan_inter + " 1 1 0;\n")
    
    
    f.write("\t}\n}\n");