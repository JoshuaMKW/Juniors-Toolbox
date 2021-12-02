import struct 
from collections import OrderedDict

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

BLKFILEMAGIC = b"J3D1blk1"

class cluster_anim(object):
    def __init__(self):
        self.seq = []
        self.scale_offset = 0

class blk(j3d.basic_animation):
    def __init__(self, loop_mode, duration, tantype = 1):
        self.loop_mode = loop_mode
        self.anglescale = 0
        self.duration = duration
        
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
        
        svr_data = f.read(16)
        
        clk_start = f.tell()
        clk_magic = f.read(4) #clk1
        clk_size = j3d.read_uint32(f)
        
        loop_mode = j3d.read_uint8(f)
        j3d.read_uint8(f)
        
        duration = j3d.read_uint16(f)
        blk = cls(loop_mode, duration)

        cluster_count = read_uint16(f)
        scales_count = int(read_uint16(f))
        
        #print("scales count " + str(scales_count) )
        
        cluster_offset = read_uint32(f) + clk_start
        scales_offset = read_uint32(f) + clk_start
        
        scales = []
        f.seek(scales_offset)
        for i in range(scales_count):
            scales.append ( read_float(f)) 
            """
            time = read_float(f)
            value = read_float(f)
            tangentIn = read_float(f)
            anim = j3d.AnimComponent( time, value, tangentIn )
            scales.append(anim) 
            """
            

        tangent_type = 0
        
        f.seek(cluster_offset)
        while ( f.read(2) != b'Th'):
            f.seek (f.tell() - 2)
            
            new_anim = cluster_anim()
            
            clus_durati = j3d.read_uint16(f)
            clus_offset = int(j3d.read_uint16(f))
            tan_type = j3d.read_uint16(f)
            tangent_type = max(tangent_type, tan_type )

            
            for j in range( clus_durati ):
                comp = j3d.AnimComponent.from_array(clus_offset, j, clus_durati, scales, tan_type)
                #new_anim.seq.append( scales[j + clus_offset] ) 
                new_anim.seq.append(comp)
                
            blk.animations.append(new_anim)
            
        blk.tan_type = tangent_type

        return blk
    def get_children_names(self):
        joints = []
        for i in range( len( self.animations )):
            joints.append("Cluster " + str(i) )
        return joints
            
    def get_loading_information(self):
        info = []
        info.append( [ "Loop Mode:", j3d.loop_mode[self.loop_mode], "Duration:", self.duration, "Tangent Type:", j3d.tan_type[self.tan_type] ] )
        info.append( ["Weight Number"])
        
        keyframes_dictionary = {}
        keyframes_dictionary[0] = []
        
        i = len( info ) 
        
        count = 0
        
        for anim in self.animations:
            info.append( ["Weight " + str(count)] )
            
            array = anim.seq
            
            keyframes_dictionary = j3d.combine_dicts(array, keyframes_dictionary)
            
            i = len(info)
            
            count += 1
        
        write_values(info, keyframes_dictionary, 1)
        return info  
    
    @classmethod
    def empty_table(cls, created):
        info = []
        info.append( [ "Loop Mode:", "", "Duration:", created[3], "Tangent Type:", j3d.tan_type[1] ] )
        info.append( ["Cluster Number"])
        
        for i in range( int(created[3])):
            info[1].append("Frame " + str(i) )
            
        for i in range( int(created[1]) ):
            info.append( ["Weight " + str(i)] )

        return info
    
    @classmethod
    def from_table(cls, f, info):
        blk = cls(int(info[0][1]), int(info[0][3]))
        
        keyframes = []
        
        print("filename " + f)
        
        frame_offset = 1
        if f == "" or info[1][1] == "Duration":
            frame_offset = 2
            blk.tan_type = 1
        else:
            blk.tan_type = int(info[0][5])
        
        for i in range(frame_offset, len( info[1] ) ):
            if info[1][i] != "":
                text = info[1][i][6:]
                text = int(text)
                keyframes.append(text)

        
        print("keyframes")
        print (keyframes)
        
        for i in range( 2, len(info)   ): #for each cluster
            current_anim = cluster_anim()           
          
            for k in range(frame_offset, len(info[i])): #for each keyframe
                if info[i][k] != "":
                    comp = j3d.AnimComponent( keyframes[ k - frame_offset ], float(info[i][k]))
                    current_anim.seq.append(comp)                      
                    current_anim.seq = j3d.make_tangents(current_anim.seq)
            
            blk.animations.append(current_anim)
       
        if f == "":
            print("no saving")
            return blk
        else:
            with open(f, "wb") as f:
                blk.write_blk(f)
                f.close()
            
    def write_blk(self, f):
        f.write(BLKFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        j3d.write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)
        
        clk1_start = f.tell()
        f.write(b"CLK1")
        
        ttk1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for clk1 size
        j3d.write_uint8(f, self.loop_mode)
        j3d.write_sint8(f, self.anglescale)        
        j3d.write_uint16(f, self.duration)
        
        #0x30        
      
        count_offset = f.tell()
        f.write(b"yolo")  # Placeholder for counts
        
        data_offsets = f.tell()
        f.write(b"toadette") #placeholder for offsets
        
        j3d.write_padding(f, multiple=32)
        cluster_anim_start = f.tell()
        
        f.write(b"\x00"*(0x6*len(self.animations))) #placeholder for stuff
        
        j3d.write_padding(f, multiple=32)
        
        all_scales = []
        for anim in self.animations:
           
            if len(anim.seq) == 1:
                sequence = [anim.seq[0].value]
            else:
                sequence = []
                for comp in anim.seq:
                    sequence.append(comp.time)
                    sequence.append(comp.value)
                    sequence.append(comp.tangentIn)
                    if self.tan_type == 1 :
                        sequence.append(comp.tangentOut)
                
            offset = j3d.find_sequence(all_scales,sequence)
            if offset == -1:
                offset = len(all_scales)
                all_scales.extend(sequence)
                
            anim.scale_offset = offset


        scale_start = f.tell()
        for val in all_scales:
            write_float(f, val)

        j3d.write_padding(f, 32)

       
        total_size = f.tell()

        f.seek(cluster_anim_start)
        for anim in self.animations:
            j3d.write_uint16(f, len(anim.seq) ) # Scale count for this animation
            j3d.write_uint16(f, anim.scale_offset)
            j3d.write_uint16(f, self.tan_type) # Tangent type, 0 = only TangentIn; 1 = TangentIn and TangentOut
    

        # Fill in all the placeholder values
        f.seek(filesize_offset)
        j3d.write_uint32(f, total_size)

        f.seek(ttk1_size_offset)
        j3d.write_uint32(f, total_size - clk1_start)

        f.seek(count_offset)
        j3d.write_uint16(f, 1)
        j3d.write_uint16(f, len(all_scales) )

        # Next come the section offsets

        j3d.write_uint32(f, cluster_anim_start  - clk1_start)
        j3d.write_uint32(f, scale_start         - clk1_start)
        
    @classmethod
    def get_blk(cls, info):
        blk = cls.from_table("", info)    
        return blk
        
    @classmethod
    def match_bmd(cls, info, strings):
        blk = cls.from_table("", info)
        j3d.basic_animation.match_bmd(blk, strings)
        return blk.get_loading_information()