import struct 
#from collections import OrderedDict

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

BPKFILEMAGIC = b"J3D1bpk1"
        
class ColorAnimation(object):
    def __init__(self, index, name):
        self._index = index 
        #self.matindex = matindex 
        self.name = name

        self.component = {"R": [], "G": [], "B": [], "A": []}

        self._component_offsets = {}

    def add_component(self, colorcomp, animcomp):
        self.component[colorcomp].append(animcomp)
    
    @classmethod
    def from_bpk(cls, f, name, index, rgba_arrays):
        coloranim = cls(name, index)
        
        for i, comp in enumerate(("R", "G", "B", "A")):
            count, offset, tangent_type = struct.unpack(">HHH", f.read(6)) 
            
            for j in range(count):
                animcomp = j3d.AnimComponent.from_array(offset, j, count, rgba_arrays[i], tangent_type)
                coloranim.add_component(comp, animcomp)
        
        return coloranim
        
    # These functions are used for keeping track of the offset
    # in the json->bpk conversion and are otherwise not useful.
    def _set_component_offsets(self, colorcomp, val):
        self._component_offsets[colorcomp] = val
    

class bpk(j3d.basic_animation):
    def __init__(self, loop_mode, duration, tantype = 0):
        self.animations = []
        self.loop_mode = loop_mode
        #self.anglescale = anglescale
        self.duration = duration
        #self.unknown_address = unknown_address
        if tantype == 0 or tantype == 1:
            self.tan_type = tantype
        else:
            self.tan_type = 1

    @classmethod
    def from_anim(cls, f):

        size = read_uint32(f)
       
        sectioncount = read_uint32(f)
        assert sectioncount == 1

        svr_data = f.read(16)
        
        pak_start = f.tell()       
        pak_magic = f.read(4)
        pak_sectionsize = read_uint32(f)

        loop_mode = read_uint8(f)
        padd = f.read(3)
        #assert padd == b"\xFF"
        #now at 0x2c
        duration = read_uint16(f)
        
        bpk = cls(loop_mode, duration)

        color_anim_count = read_uint16(f)

        #print("num of anims: " + str(color_anim_count))
        #print(register_color_anim_count, "register color anims and", constant_color_anim_count, "constant collor anims")
        component_counts = {}      
            
        for comp in ("R", "G", "B", "A"):
            component_counts[comp] = read_uint16(f)
            #print(comp, "count:", component_counts[comp])
        
        color_animation_offset  = read_uint32(f) + pak_start    #        
        index_offset            = read_uint32(f) + pak_start    #        
        stringtable_offset      = read_uint32(f) + pak_start    #

        offsets = {}
        for comp in ("R", "G", "B", "A"):
            offsets[comp] = read_uint32(f) + pak_start 
            #print(animtype, comp, "offset:", offsets[animtype][comp])
    
        #print(hex(index_offset))
        
        # Read indices
        indices = []
        f.seek(index_offset)
        for i in range(color_anim_count):
            index = read_uint16(f)
            if i != index:
                #print("warning: register index mismatch:", i, index)
                assert(False)
            indices.append(index)
       
        
        # Read stringtable 
        f.seek(stringtable_offset)
        stringtable = StringTable.from_file(f)
        
        # read RGBA values 
        values = {}
            
        for comp in ("R", "G", "B", "A"):
            values[comp] = []
            count = component_counts[comp]
            f.seek(offsets[comp])
            #print(animtype, comp, hex(offsets[animtype][comp]), count)
            for i in range(count):
                values[comp].append(read_sint16(f))
              
        for i in range(color_anim_count):
            f.seek(color_animation_offset + 0x1C*i)
            name = stringtable.strings[i]
            anim = ColorAnimation.from_bpk(f, i, name, (
                values["R"], values["G"], values["B"], values["A"]
                ))
                          
            
            bpk.animations.append(anim)
        return bpk

    def get_loading_information(self):

        info = []
        info.append( ["Loop Mode:", j3d.loop_mode[self.loop_mode], "Duration:", self.duration, "Tan Type:", j3d.tan_type[self.tan_type] ] )
        
        
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []       
        
        info.append( ["Material Name", "Channel"] )
        
        i = len( info ) 
        
        for anim in self.animations:
            info.append( [anim.name] )
            things = ["Red:", "Green:", "Blue:", "Alpha:"]
            
            
            for j in range (len ( things ) ):    
                comp = things[j]
                if j == 0:
                    info[i].append(comp)
                else:
                    info.append( ["", comp] )
            
                
                array = anim.component[comp[0:1]]
                
                #print (array)
                keyframes_dictionary = j3d.combine_dicts(array, keyframes_dictionary) 
                
            
            i = len(info)
            
        write_values(info, keyframes_dictionary, 1)

        
        #print(info)
        return info  
    
    @classmethod
    def empty_table(cls, created):
        info = []
        info.append( ["Loop_mode:", "Duration:", created[3], "Tan Type:", j3d.tan_type[1] ] )
        info.append( ["Material Name", "Channel", "Frame 0", "Frame " + str(created[3] ) ] )

        for i in range( int(created[1]) ):
            info.append( ["Material " + str(i), "Red:"] )
            
            things = ["Green:", "Blue:", "Alpha:"]
            for chan in things:
                info.append( ["", chan] )
        return info          
    
    @classmethod 
    def single_mat(cls):
        info = []
        info.append( ["Material Name", "Red:"] )
            
        things = ["Green:", "Blue:", "Alpha:"]
        for chan in things:
            info.append( ["", chan] )
        return info
    
    @classmethod
    def from_table(cls, f, info):
        bpk = cls(int(info[0][1]), int(info[0][3]), int(info[0][5]))

        keyframes = []
        for i in range(2, len( info[1] ) ):
            if info[1][i] != "":
                text = info[1][i][6:]
                text = int(text)
                keyframes.append(text)
        
        print(keyframes)
        
        for i in range(0, int( len(info) / 4)  ):
            curr_line = 4 * i + 2
            
            color_anim = ColorAnimation(i, info[curr_line][0] )
                       
            for j in range(0, 4):
                rgba = "RGBA"
                rgba = rgba[j: j+1]
                
                for k in range(2, len( info[curr_line + j] ) ):
                    if info[curr_line + j][k] != "":
                        anim_comp = j3d.AnimComponent(keyframes[k - 2], int(info[curr_line + j][k]) )
                        color_anim.add_component(rgba, anim_comp)
                color_anim.component[rgba] = j3d.make_tangents(color_anim.component[rgba])

            bpk.animations.append(color_anim)
                    
        
              
        if f == "":
            print("no saving")
            return bpk
        else:
            with open(f, "wb") as f:
                bpk.write_bpk(f)
                f.close()

    
    def write_bpk(self, f):
        f.write(BPKFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        write_uint32(f, 1) # Always a section count of 1
        f.write(b"SVR1" + b"\xFF"*12)

        pak1_start = f.tell()
        f.write(b"PAK1")

        pak1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for pak1 size
        write_uint8(f, self.loop_mode)
        
        write_uint8(f, 0xFF)
        write_uint8(f, 0xFF)
        write_uint8(f, 0xFF)
        
        write_uint16(f, self.duration)
        write_uint16(f, len(self.animations))
        
        
        count_offset = f.tell()
        f.write(b"AB"*4)  # Placeholder for register and constant rgba counts
        data_offsets = f.tell()
        f.write(b"ABCD"*3) # Placeholder for data offsets 
        f.write(b"ABCD"*4) # Placeholder for rgba data offsets
        
        write_padding(f, multiple=32)
        assert f.tell() == 0x60
        
        
        anim_start = f.tell()
        f.write(b"\x00"*(0x18*len(self.animations)))
        write_padding(f, multiple=4)

        all_values = {}
        
        for colorcomp in ("R", "G", "B", "A"):
            all_values[colorcomp] = []
            
            for anim in self.animations: 
                
            
                animation_components = anim.component[colorcomp]
             
                    
                # Set up offset for scale
                if len(animation_components) == 1:
                    sequence = [ int( animation_components[0].value) ]
                else:
                    sequence = []
                    for comp in animation_components:
                        sequence.append(comp.time)
                        sequence.append(comp.value)
                        sequence.append( int(comp.tangentIn) )
                        if self.tan_type == 1 :
                            sequence.append( int( comp.tangentOut) )
                            
                
                offset = j3d.find_sequence(all_values[colorcomp],sequence)

                if offset == -1:
                    offset = len(all_values[colorcomp])
                    all_values[colorcomp].extend(sequence)
                    
                anim._set_component_offsets(colorcomp, offset)

        data_starts = []
        
            
        for comp in ("R", "G", "B", "A"):
            data_starts.append(f.tell())
            for val in all_values[comp]:
                write_sint16(f, val)
            write_padding(f, 4)
                
                
        # Write the indices for each animation
        index_start = f.tell()
        for i in range(len(self.animations)):
            write_uint16(f, i)
        write_padding(f, multiple=4)
       
        
        # Create string table of material names for register color animations
        stringtable = j3d.StringTable()

        for anim in self.animations:
            stringtable.strings.append(anim.name)
        
        stringtable_start = f.tell()
        stringtable.write(f, stringtable.strings)
        write_padding(f, multiple=4)
        
        
        write_padding(f, multiple=32)
        total_size = f.tell()

        f.seek(anim_start)
        for anim in self.animations:
            for comp in ("R", "G", "B", "A"):
                write_uint16(f, len(anim.component[comp])) # Scale count for this animation
                write_uint16(f, anim._component_offsets[comp]) # Offset into scales
                write_uint16(f, self.tan_type) # Tangent type, 0 = only TangentIn; 1 = TangentIn and TangentOut


        # Fill in all the placeholder values
        f.seek(filesize_offset)
        write_uint32(f, total_size)

        f.seek(pak1_size_offset)
        write_uint32(f, total_size - pak1_start)

        f.seek(count_offset)

        for comp in ("R", "G", "B", "A"):
            write_uint16(f, len(all_values[comp]))
                
        # Next come the section offsets
        write_uint32(f, anim_start        - pak1_start)
        
        write_uint32(f, index_start       - pak1_start)
        
        write_uint32(f, stringtable_start - pak1_start)
        
        
        # RGBA data starts 
        for data_start in data_starts:
            write_uint32(f, data_start - pak1_start)

    @classmethod
    def match_bmd(cls, info, strings):
        bpk = cls.from_table("", info)
        j3d.basic_animation.match_bmd(bpk, strings)
        return bpk.get_loading_information()