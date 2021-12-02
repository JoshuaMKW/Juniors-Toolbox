import struct 
#from collections import OrderedDict

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

BVAFILEMAGIC = b"J3D1bva1"

class VisibilityAnimation(object):
    def __init__(self, index, name, frames):
        self.index = index 
        self.name = name 
        self.frames = frames
        
        self._offset = 0;


    # These functions are used for keeping track of the offset
    # in the json->brk conversion and are otherwise not useful.
    def _set_offset(self, val):
        self._offset = val


class bva(j3d.basic_animation):
    def __init__(self, loop_mode, duration, tantype = 0):
        self.animations = []
        self.loop_mode = loop_mode
        #self.anglescale = anglescale
        self.duration = duration
        
        if tantype == 0 or tantype == 1:
            self.tan_type = tantype
        else:
            self.tan_type = 1
        #self.unknown_address = unknown_address

    @classmethod
    def from_anim(cls, f):

        size = read_uint32(f)
        #print("Size of brk: {} bytes".format(size))
        sectioncount = read_uint32(f)
        assert sectioncount == 1

        svr_data = f.read(16)
        
        vaf_start = f.tell()
        
        vaf_magic = f.read(4)
        vaf_sectionsize = read_uint32(f)

        loop_mode = read_uint8(f)
        padd = f.read(1)
        assert padd == b"\xFF"
        duration = read_uint16(f)
        bva = cls(loop_mode, duration)

        visibility_count = read_uint16(f)
        show_table_count = read_uint16(f)
        visibility_offset = read_uint32(f) + vaf_start 
        show_table_offset = read_uint32(f) + vaf_start


        for i in range(visibility_count):
            
            
            f.seek(visibility_offset + 0x4*i)
            show_count = read_uint16(f) #duration
            show_index = read_uint16(f) #index into table
            
            frames = []
            f.seek( show_table_offset + show_index)
            for j in range( show_count ):
                frames.append( read_uint8(f) )
            
            anim = VisibilityAnimation(i, "Mesh " + str(i), frames)
            bva.animations.append(anim)
        

        return bva

    def get_children_names(self):
        mesh_names = []
        for mesh in self.animations:
            mesh_names.append(mesh.name)
        return mesh_names

    def get_loading_information(self):

        info = []
        info.append( ["Loop Mode:", j3d.loop_mode[self.loop_mode] , "Duration:", self.duration, "Tan Type:", j3d.tan_type[1] ] )
    
        
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []
        

        info.append( ["Mesh Name", "Duration"] )
        
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []

        
        for anim in self.animations: 
            #print("current at mat index : " + str(i) )
                       
            list_of_frames = anim.frames

            curr_info = [anim.name, len(list_of_frames)]
            
            keyframes_dictionary[0].append(list_of_frames[0])
            
            thismat_kf = {}
  
            texture_index = list_of_frames[0]
            
            thismat_kf[0]= [texture_index]
      
            for j in range(len(list_of_frames)): #j is the index within each mat frame list
                if list_of_frames[j] == texture_index:
                    pass #if it's unchanged, do nothing
                else: #if it's changed, add it to the list and update
                    thismat_kf[j] = list_of_frames[j]                    
                    texture_index = list_of_frames[j]

            #print("keyframes for " + self.animations[i].name)
            #print(thismat_kf.keys())
            
            for j in keyframes_dictionary.keys(): #if there is a keyframe that does not apply to the current material, pad
                if not j in thismat_kf.keys():
                    keyframes_dictionary[j].append("")
                    
            for j in thismat_kf.keys():
                if j == 0: 
                    pass
                elif j in keyframes_dictionary: 
                    keyframes_dictionary[j].append(thismat_kf[j])
                else: #new keyframe
                    to_add = []
                    #for k in range(i-1):
                    for k in range( len(keyframes_dictionary[0] ) - 1):
                        to_add.append("")
                    to_add.append(thismat_kf[j])
                    keyframes_dictionary[j] = (to_add)
            #print("keyframes dic")
            #print(keyframes_dictionary)
            
            info.append(curr_info)
        
        keys = []

        for i in keyframes_dictionary.keys():
            keys.append(i)
       
        keys.sort()
        
        for i in keys: #i is the frame, so for each keyframe
            info[1].append("Frame " + str(i)) #add the header
            
            k = 2 #k in the row index in the table
            for j in keyframes_dictionary[i]: #j is the value
                info[k].append(j)
                k += 1
        
        
        
        print(info)
        return info  
    
    @classmethod
    def empty_table(cls, created):
        information = []
        
        information.append(["Flag: ", 0, "Anglescale", 0, "Unknown:", 0])
        
        information.append( [ "Mesh Name", "Duration"] )
        
        for i in range( int(created[3] ) ):
            information[1].append( "Frame " + str(i))
        
        for i in range( int(created[1]) ):
            information.append( [ "Mesh "  + str(i), created[3] ] )
        
        return information
    
    @classmethod
    def from_table(cls, f, info):
        bva = cls(int(info[0][1]), int(info[0][3]), int(info[0][5])  )


        largest_duration = 0;
        
        extent = max(len(info[0]), len(info[1]))
        
        keyframes = []
        
        print(info[1])
        for i in range( 2, len( info[1] ) ):
            text = info[1][i][6:]
            print(text)
            #assert text.isnumeric()
            if text.isnumeric():
                text = int(text)
                keyframes.append(text)
        
        print("keyframes:")
        print (keyframes)
        
        for i in range(2, len(info)):
            for j in range (3, extent):
                if j >= len(info[i]):
                    info[i].append(info[i][j-1])
                elif info[i][j] == "":
                    info[i][j] = info[i][j-1]
        
        for i in range( 2, len(info) ): #i is the index of the material in info
            current_duration = info[i][1]   
            
            
            current_duration = int(current_duration)
            largest_duration = max(largest_duration, current_duration )                 
            
            frames = []
            
            last_value = 0
            
            next_kf = 2
            prev_kf = 2
            
            for j in range( current_duration ): #for each frame
                if j == 0:#for the first frame, just write the value
                    frames.append(info[i][2]) 
                    last_value = info[i][2]
                    
                    next_kf += 1
             
                elif j > keyframes[-1]:
                    frames.append(last_value)            
                elif j != int(info[1][next_kf][6:]): #if not a keyframe, just write
                    frames.append(last_value)
                else: #if it is a keyframe       
                    
                    last_value = info[i][next_kf]
                    frames.append(last_value)
                    prev_kf = next_kf
                    print("keyframe " + str(last_value))
                    next_kf += 1
                     
            print("frames:")
            print(frames)
            
            entry = VisibilityAnimation(info[i][0], "toadette", frames)
            bva.animations.append(entry)
            bva.largest_duration = largest_duration
   
        if f == "":
            print("no saving")
            return bva
        else:
            with open(f, "wb") as f:
                bva.write_bva(f)
                f.close()


    def write_bva(self, f):
        f.write(BVAFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)

        vaf1_start = f.tell()
        f.write(b"VAF1")

        vaf1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for vaf1 size
        
        write_uint8(f, self.loop_mode)
        write_uint8(f, 0xFF)
        write_uint16(f, self.duration)
        
        
        write_uint16(f, len(self.animations))
        
        count_offset = f.tell()
        f.write(b"AB"*1)  # Placeholder for table count
        data_offsets = f.tell()
        f.write(b"ABCD"*2) # Placeholder for data offsets 
   
        write_padding(f, multiple=32)
        assert f.tell() == 0x40
         
        # now, time for the visiblity animations to be written as placeholders        
        anim_start = f.tell()
        f.write(b"\x00"*(0x4*len(self.animations)))
        write_padding(f, multiple=4)
        
        table_offset = f.tell()
        # write the table
        all_frames = []
        
        for anim in self.animations:
            print(anim.frames)
            offset = j3d.find_sequence( all_frames, anim.frames )
            if offset == -1:
                offset = len(all_frames)
                all_frames.extend(anim.frames)
            
            anim._set_offset(offset)
       
        for val in all_frames:
            j3d.write_uint8(f, int(val) )
            
        j3d.write_padding(f, 4)
        
 
        write_padding(f, multiple=32)
        total_size = f.tell()

        f.seek(anim_start)
        for anim in self.animations:
            write_uint16(f, len(anim.frames))
            write_uint16(f, anim._offset)
     
        # Fill in all the placeholder values
        f.seek(count_offset)
        write_uint16(f, len(all_frames ) )
        
        f.seek(filesize_offset)
        write_uint32(f, total_size)

        f.seek(vaf1_size_offset)
        write_uint32(f, total_size - vaf1_start)

        f.seek(data_offsets)
        write_uint32(f, anim_start        - vaf1_start)
        write_uint32(f, table_offset        - vaf1_start)


    @classmethod
    def match_bmd(cls, info, strings):
        bva = cls.from_table("", info)
        j3d.basic_animation.match_bmd(bva, strings)
        return bva.get_loading_information()