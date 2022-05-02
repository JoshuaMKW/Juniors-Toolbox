from io import BytesIO
import struct
from typing import BinaryIO
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs, write_jsystem_padding

from juniors_toolbox.utils.iohelper import read_ubyte, read_uint16, read_uint32, write_ubyte, write_uint16, write_uint32
from juniors_toolbox.utils.j3d.anim.general_animation import BTPFILEMAGIC, BasicAnimation, StringTable, find_sequence

class BtpFacialEntry():
    def __init__(self, mat_name, frames):
        self.name = mat_name
        self.frames = frames
        
        self._offset = 0
        
    def _set_offset(self, val):
        self._offset = val

class BTP(BasicAnimation):
  
    def __init__(self, flag, unknown1 = 1):
        self.animations = []
        self.flag = flag
        self.unknown_address = unknown1    
        
        self.largest_duration = unknown1
        
    
    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
        #at this point, f is at 0x09
        size = read_uint32(data)

        sectioncount = read_uint32(data)
        assert sectioncount == 1

        svr_data = data.read(16)
        #at this point, f is at the actual start of the documentaion

        tpt_start = data.tell()
        tpt_magic = data.read(4) #TPT1

        tpt_sectionsize = read_uint32(data)

        flag = read_ubyte(data)
        read_ubyte(data)

        anim_length = read_uint16(data)
        num_entries = read_uint16(data) #also known as "keyframe count in the documentation"
        #print("there are " + str(num_entries) + " entries")
        
        unknown1 = read_uint16(data)
        
        btp = cls(flag, anim_length)

        #offsets
        facial_animation_entries_os = read_uint32(data) + tpt_start
        texture_index_bank_os = read_uint32(data) + tpt_start
        remap_table_os = read_uint32(data) + tpt_start
        stringtable_os = read_uint32(data) + tpt_start

        #at this point, we are at the facial animation entries
        
        
        #make string table
        data.seek(stringtable_os)
        stringtable = StringTable.from_file(data)
    
        read_animations = []
    
        for i in range(num_entries):
        
            data.seek(facial_animation_entries_os + i * 8)
            #print(data.tell())
        
            this_length = read_uint16(data)
            #print("length of " + str(i) + " is " + str(this_length))
            this_start = read_uint16(data)
            
            indices = []
            
            data.seek(texture_index_bank_os + 2 * this_start)
     
            for j in range(this_length):
                indices.append(read_uint16(data))
            
            animation = BtpFacialEntry(stringtable.strings[i], indices)
            
            read_animations.append(animation)
            
       
        btp.animations = read_animations
        return btp
              
    def get_loading_information(self):
        
        information = []
        
        information.append(["Loop Mode: ", self.flag, "Maximum Duration:", self.unknown_address])
        
        information.append( [ "Material Name", "Duration"] )
        
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
            
            information.append(curr_info)
        
        keys = []

        for i in keyframes_dictionary.keys():
            keys.append(i)
       
        keys.sort()
        
        for i in keys: #i is the frame, so for each keyframe
            information[1].append("Frame " + str(i)) #add the header
            
            k = 2 #k in the row index in the table
            for j in keyframes_dictionary[i]: #j is the value
                information[k].append(j)
                k += 1
        
        #print("information: ")        
        #print (information)
        return information
    
    @classmethod
    def empty_table(cls, created):
        information = []
        
        information.append(["Flag / Loop Mode: ", 0, "Maximum Duration:",int(created[3] )  ])
        
        information.append( [ "Material Name", "Duration"] )
        
        for i in range( int(created[3] ) ):
            information[1].append( "Frame " + str(i))
        
        for i in range( int(created[1]) ):
            information.append( [ "Material "  + str(i), created[3] ] )
        
        return information
            
    
    @classmethod
    def from_table(cls, f, info):
        
        
        btp = cls(int(info[0][1]) , int(info[0][3]))
        
        largest_duration = 0;
        
        extent = max(len(info[0]), len(info[1]))
        
        keyframes = []
        
        for i in range( 2, len( info[1] ) ):
            text = info[1][i][6:]
            #print(text)
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
                    
                    next_kf += 1
                     
            print("frames:")
            print(frames)
            
            entry = BtpFacialEntry(info[i][0], frames)
            btp.animations.append(entry)
            btp.largest_duration = largest_duration
            
        if f == "":
            print("no saving")
            return btp
        else:
            with open(f, "wb") as f:
                btp.write_btp(f)
                f.close()
        
    def to_bytes(self) -> bytes:
        f = BytesIO()

        #header info 
        f.write(BTPFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)
         
        tpt1_start = f.tell()
        f.write(b"TPT1")
        
        tpt1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for tpt1 size
                    
        write_ubyte(f, self.flag)
        write_ubyte(f, 0xff)
        write_uint16(f, self.largest_duration)
        write_uint16(f, len(self.animations) )
        write_uint16(f, self.unknown_address)
        
        tables_offset = f.tell()
        
        f.write(b"toadettebestgril")           

        facial_animation_entries_os = f.tell()
        
        f.write(b"\x00"*(0x8*len(self.animations))) #placeholder for stuff
        
        """
        total_frames = 0;
       
        for i in range( len (btp.animations) ):
            write_uint16(f, len ( btp.animations[i].frames ))
            write_uint16(f, total_frames)
            total_frames += len (btp.animations[i].frames )
            write_uint16(f, 0x00FF)
            write_uint16(f, 0xFFFF)
        """
        
        write_jsystem_padding(f, 4)
        
        texture_index_bank_os = f.tell()
        
        all_frames = []
        
        for anim in self.animations:
            offset = find_sequence( all_frames, anim.frames )
            if offset == -1:
                offset = len(all_frames)
                all_frames.extend(anim.frames)
            
            anim._set_offset(offset)
       
        for val in all_frames:
            write_uint16(f, int(val) )
            
        write_jsystem_padding(f, 4)
       
        """
        for i in range( len (btp.animations) ):
            for j in btp.animations[i].frames:
                j = int(j)
                write_uint16(f, j)
        """
        
        remap_table_os = f.tell()
        
        write_uint32(f, 0x00000001)
        
        stringtable_os = f.tell()
        
        strings = self.get_children_names()
        
        StringTable.write(f, strings)
        
        write_jsystem_padding(f, 32)
        
        total_size = f.tell()
        
        f.seek(filesize_offset)
        write_uint32(f, total_size)
        
        f.seek(tpt1_size_offset)
        write_uint32(f, total_size - tpt1_start)
        
        f.seek(facial_animation_entries_os)
        for anim in self.animations:
            write_uint16(f, len ( anim.frames ))
            write_uint16(f, anim._offset)
            write_uint16(f, 0x00FF)
            write_uint16(f, 0xFFFF)
                
        f.seek(tables_offset)
        write_uint32(f, facial_animation_entries_os - tpt1_start)
        write_uint32(f, texture_index_bank_os - tpt1_start)
        write_uint32(f, remap_table_os - tpt1_start)
        write_uint32(f, stringtable_os - tpt1_start)

        return f.getvalue()
        
    @classmethod
    def match_bmd(cls, info, strings):
        btp = cls.from_table("", info)
        info = BasicAnimation.match_bmd(btp, strings)
        return btp.get_loading_information()
