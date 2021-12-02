import struct 
from collections import OrderedDict

from animations.general_animation import *
from animations.general_animation import basic_animation
import animations.general_animation as j3d

BLAFILEMAGIC = b"J3D1bla1"

class cluster_anim(object):
    def __init__(self):
        self.seq = []

class bla(j3d.basic_animation):
    def __init__(self, loop_mode, duration):
        self.loop_mode = loop_mode
        self.anglescale = 0
        self.duration = duration
        
        self.animations = []
    
    @classmethod
    def from_anim(cls, f):
        size = j3d.read_uint32(f)
        
        sectioncount = j3d.read_uint32(f)
        assert sectioncount == 1
        
        svr_data = f.read(16)
        
        clf_start = f.tell()
        clf_magic = f.read(4) #clf1
        clf_size = j3d.read_uint32(f)
        
        loop_mode = j3d.read_uint8(f)
        j3d.read_uint8(f)
        
        duration = j3d.read_uint16(f)
        bla = cls(loop_mode, duration)

        cluster_count = read_uint16(f)
        scales_count = read_uint16(f)      
        
        #print(scales_count)
        
        cluster_offset = read_uint32(f) + clf_start
        scales_offset = read_uint32(f) + clf_start

        # Read floats
        scales = []
        f.seek(scales_offset)
        for i in range(scales_count):

            scales.append(read_float(f))      

        # Read clusters
        
        f.seek(cluster_offset)
        
        while ( f.read(2) != b'Th'):
            f.seek (f.tell() - 2)
            new_anim = cluster_anim()
            
            clus_durati = j3d.read_uint16(f)
            clus_offset = j3d.read_uint16(f)
            
            #print(clus_durati)
            
            for j in range( clus_durati ):
                new_anim.seq.append( scales[j + clus_offset] ) 
            
            bla.animations.append(new_anim)
       
        return bla
        
    def get_children_names(self):
        joints = []
        for i in range( len( self.animations )):
            joints.append("Cluster " + str(i) )
        return joints
            
    def get_loading_information(self):
        info = []
        info.append( [ "Loop Mode:", j3d.loop_mode[self.loop_mode], "Duration:", self.duration ] ) 
        info.append( ["Cluster Number", "Duration"])
        
        for i in range(self.duration):
            info[1].append("Frame " + str(i) )
        
        i = len( info ) 
        
        count = 0
        
        for anim in self.animations:
            info.append( ["Cluster " + str(count), len(anim.seq)] )
            
            for j in range (len ( anim.seq) ):    
                info[i].append( anim.seq[j] )
            
            i = len(info)
            
            count += 1
            
        return info  
    
    @classmethod
    def empty_table(cls, created):
        info = []
        info.append( [ "Loop Mode:", "", "Duration:", created[3]] )
        info.append( ["Cluster Number", "Duration"])
        
        for i in range( int(created[3])):
            info[1].append("Frame " + str(i) )
            
        for i in range( int(created[1]) ):
            info.append( ["Cluster " + str(i), created[3]] )

        return info
            
    def write_bla(self, f):
        f.write(BLAFILEMAGIC)
        filesize_offset = f.tell()
        f.write(b"ABCD") # Placeholder for file size
        j3d.write_uint32(f, 1) # Always a section count of 1
        f.write(b"\xFF"*16)
        
        clf1_start = f.tell()
        f.write(b"CLF1")
        
        clf1_size_offset = f.tell()
        f.write(b"EFGH")  # Placeholder for clf1 size
        j3d.write_uint8(f, self.loop_mode)
        j3d.write_sint8(f, self.anglescale)    
        j3d.write_uint16(f, self.duration)
        
        #0x30        
      
        count_offset = f.tell()
        f.write(b"toad")  # Placeholder for cluster and scale counts
        
        data_offsets = f.tell()
        f.write(b"toadette") #placeholder for offsets
        
        write_padding(f, multiple=32)
        cluster_anim_start = f.tell()
        
        f.write(b"\x00"*(0x4*len(self.animations))) #placeholder for stuff
        
        write_padding(f, multiple=32)
        
        all_scales = []
        for anim in self.animations:
           
            if len(anim.seq) == 1:
                sequence = [anim.seq[0].value]
            else:
                sequence = []
                for comp in anim.seq:
                    sequence.append(comp.value)
                
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
    

        # Fill in all the placeholder values
        f.seek(filesize_offset)
        j3d.write_uint32(f, total_size)

        f.seek(clf1_size_offset)
        j3d.write_uint32(f, total_size - clf1_start)

        f.seek(count_offset)
        j3d.write_uint16(f, 1)
        j3d.write_uint16(f, len(all_scales) )

        # Next come the section offsets

        j3d.write_uint32(f, cluster_anim_start  - clf1_start)
        j3d.write_uint32(f, scale_start         - clf1_start)
        
        
    @classmethod
    def from_blk(cls, blk):
        bla = cls(blk.loop_mode, blk.duration)
        
        for cluster_animation in blk.animations:
            new_cluster_anim = cluster_anim()
            
            if len( cluster_animation.seq ) < blk.duration:
                val_array = interpolate( joint_anim.seq )
                new_cluster_anim.seq = val_array
            else:
                new_cluster_anim.seq = cluster_animation.seq
            
            bla.animations.append(new_cluster_anim)
        
        return bla
def interpolate(entry_array):

    all_values = []
    
    if len( entry_array) == 1:
        return entry_array

    for i in range( len( entry_array ) - 1):
        
        some_values = inter_helper(entry_array[i], entry_array[i + 1])
        
        for value in some_values:
            all_values.append(value)
    
    all_values.append( entry_array[-1] )
    
    return all_values
    
def inter_helper(start, end):
    values = []
    for i in range(end.time - start.time):
        comp = cluster_entry( start.value + (i / (end.time - start.time)) * (end.value - start.value))
        values.append( comp )
    #print (values)
    return values