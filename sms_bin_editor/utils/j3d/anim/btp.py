import struct

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

class btp_facial_entry(object):
    def __init__(self, mat_name, frames):
        self.name = mat_name
        self.frames = frames
        
        self._offset = 0;
        
    def _set_offset(self, val):
        self._offset = val

class btp(j3d.basic_animation):
  
    def __init__(self, flag, unknown1 = 1):
        self.animations = []
        self.flag = flag
        self.unknown_address = unknown1    
        
        self.largest_duration = unknown1
        
    
    @classmethod
    def from_anim(cls, f):
        #at this point, f is at 0x09
        size = j3d.read_uint32(f)

        sectioncount = j3d.read_uint32(f)
        assert sectioncount == 1

        svr_data = f.read(16)
        #at this point, f is at the actual start of the documentaion

        tpt_start = f.tell()
        tpt_magic = f.read(4) #TPT1

        tpt_sectionsize = j3d.read_uint32(f)

        flag = j3d.read_uint8(f)
        j3d.read_uint8(f)

        anim_length = j3d.read_uint16(f)
        num_entries = j3d.read_uint16(f) #also known as "keyframe count in the documentation"
        #print("there are " + str(num_entries) + " entries")
        
        unknown1 = j3d.read_uint16(f)
        
        btp = cls(flag, anim_length)

        #offsets
        facial_animation_entries_os = j3d.read_uint32(f) + tpt_start
        texture_index_bank_os = j3d.read_uint32(f) + tpt_start
        remap_table_os = j3d.read_uint32(f) + tpt_start
        stringtable_os = j3d.read_uint32(f) + tpt_start

        #at this point, we are at the facial animation entries
        
        
        #make string table
        f.seek(stringtable_os)
        stringtable = j3d.StringTable.from_file(f)
    
        read_animations = []
    
        for i in range(num_entries):
        
            f.seek(facial_animation_entries_os + i * 8)
            #print(f.tell())
        
            this_length = j3d.read_uint16(f)
            #print("length of " + str(i) + " is " + str(this_length))
            this_start = j3d.read_uint16(f)
            
            indices = []
            
            f.seek(texture_index_bank_os + 2 * this_start)
     
            for j in range(this_length):
                indices.append(j3d.read_uint16(f))
            
            animation = btp_facial_entry(stringtable.strings[i], indices)
            
            read_animations.append(animation)
            
       
        btp.animations = read_animations
        f.close()
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
            
            entry = btp_facial_entry(info[i][0], frames)
            btp.animations.append(entry)
            btp.largest_duration = largest_duration
            
        if f == "":
            print("no saving")
            return btp
        else:
            with open(f, "wb") as f:
                btp.write_btp(f)
                f.close()
        
    def write_btp(self, f):

        #header info 
        f.write(j3d.BTPFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        j3d.write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)
         
        tpt1_start = f.tell()
        f.write(b"TPT1")
        
        tpt1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for tpt1 size
                    
        j3d.write_uint8(f, self.flag)
        j3d.write_uint8(f, 0xff)
        j3d.write_uint16(f, self.largest_duration)
        j3d.write_uint16(f, len(self.animations) )
        j3d.write_uint16(f, self.unknown_address)
        
        tables_offset = f.tell();
        
        f.write(b"toadettebestgril")           

        facial_animation_entries_os = f.tell()
        
        f.write(b"\x00"*(0x8*len(self.animations))) #placeholder for stuff
        
        """
        total_frames = 0;
       
        for i in range( len (btp.animations) ):
            j3d.write_uint16(f, len ( btp.animations[i].frames ))
            j3d.write_uint16(f, total_frames)
            total_frames += len (btp.animations[i].frames )
            j3d.write_uint16(f, 0x00FF)
            j3d.write_uint16(f, 0xFFFF)
        """
        
        j3d.write_padding(f, 4)
        
        texture_index_bank_os = f.tell()
        
        all_frames = []
        
        for anim in self.animations:
            offset = j3d.find_sequence( all_frames, anim.frames )
            if offset == -1:
                offset = len(all_frames)
                all_frames.extend(anim.frames)
            
            anim._set_offset(offset)
       
        for val in all_frames:
            j3d.write_uint16(f, int(val) )
            
        j3d.write_padding(f, 4)
       
        """
        for i in range( len (btp.animations) ):
            for j in btp.animations[i].frames:
                j = int(j)
                j3d.write_uint16(f, j)
        """
        
        remap_table_os = f.tell()
        
        j3d.write_uint32(f, 0x00000001)
        
        stringtable_os = f.tell()
        
        strings = self.get_children_names()
        
        j3d.StringTable.write(f, strings)
        
        j3d.write_padding(f, 32)
        
        total_size = f.tell()
        
        f.seek(filesize_offset)
        j3d.write_uint32(f, total_size)
        
        f.seek(tpt1_size_offset)
        j3d.write_uint32(f, total_size - tpt1_start)
        
        f.seek(facial_animation_entries_os);
        for anim in self.animations:
            j3d.write_uint16(f, len ( anim.frames ))
            j3d.write_uint16(f, anim._offset)
            j3d.write_uint16(f, 0x00FF)
            j3d.write_uint16(f, 0xFFFF)
                
        f.seek(tables_offset)
        j3d.write_uint32(f, facial_animation_entries_os - tpt1_start)
        j3d.write_uint32(f, texture_index_bank_os - tpt1_start)
        j3d.write_uint32(f, remap_table_os - tpt1_start)
        j3d.write_uint32(f, stringtable_os - tpt1_start)
        
    @classmethod
    def match_bmd(cls, info, strings):
        btp = cls.from_table("", info)
        info = j3d.basic_animation.match_bmd(btp, strings)
        return btp.get_loading_information()
