

## Implementation of a yaz0 decoder/encoder in Python, by Yoshi2
## Using the specifications in http://www.amnoid.de/gc/yaz0.txt

from struct import unpack, pack
import struct as struct
import os
import re
import hashlib
import math



from timeit import default_timer as time
from io import BytesIO

def data_len(data):
  data_length = data.seek(0, 2)
  return data_length

def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]
def read_uint16(f):
    return struct.unpack(">H", f.read(2))[0]
def read_sint16(f):
    return struct.unpack(">h", f.read(2))[0]
def read_uint8(f):
    return struct.unpack(">B", f.read(1))[0]
def read_sint8(f):
    return struct.unpack(">b", f.read(1))[0]
def read_float(f):
    return struct.unpack(">f", f.read(4))[0]
    
    
def write_uint32(f, val):
    f.write(struct.pack(">I", val))
def write_uint16(f, val):
    f.write(struct.pack(">H", val))
def write_sint16(f, val):
    f.write(struct.pack(">h", val))
def write_uint8(f, val):
    f.write(struct.pack(">B", val))
def write_sint8(f, val):
    f.write(struct.pack(">b", val))
def write_float(f, val):
    f.write(struct.pack(">f", val))

def read_u8(data, offset):
  data.seek(offset)
  return struct.unpack(">B", data.read(1))[0]

def read_u16(data, offset):
  data.seek(offset)
  return struct.unpack(">H", data.read(2))[0]

def read_u32(data, offset):
  data.seek(offset)
  return struct.unpack(">I", data.read(4))[0]

def write_u8(data, offset, new_value):
  new_value = struct.pack(">B", new_value)
  data.seek(offset)
  data.write(new_value)

def write_u16(data, offset, new_value):
  new_value = struct.pack(">H", new_value)
  data.seek(offset)
  data.write(new_value)

def write_u32(data, offset, new_value):
  new_value = struct.pack(">I", new_value)
  data.seek(offset)
  data.write(new_value)


def write_padding(f, multiple):
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)
    
    diff = next_aligned - f.tell()
    
    for i in range(diff):
        
        pos = i%len(PADDING)
        f.write(PADDING[pos:pos+1])

#from cStringIO import StringIO

#class yaz0():
#    def __init__(self, inputobj, outputobj = None, compress = False):

DEFAULT_SEARCH_DEPTH = 0x1000

def write_limited(f, data, limit):
    if f.tell() >= limit:
        pass
    else:
        f.write(data)

class Yaz0:
    num_bytes_1 = 0
    match_pos = 0
    prev_flag = False
    MAX_RUN_LENGTH = 0xFF + 0x12
    next_num_bytes = 0
    next_match_pos = 0
    next_flag = False
    

def decompress(f, out, suppress_error=False):
    #if out is None:
    #    out = BytesIO()
    
    # A way to discover the total size of the input data that
    # should be compatible with most file-like objects.
    f.seek(0, 2)
    maxsize = f.tell()
    f.seek(0)
    
    
    header = f.read(4)
    if header != b"Yaz0":
        if suppress_error:
            f.seek(0)
            out.write(f.read())
            return 
        else:
            raise RuntimeError("File is not Yaz0-compressed! Header: {0}".format(header))
    
    decompressed_size = read_uint32(f)
    f.read(8) # padding
        
    eof = False

    # Some micro optimization, can save up to a second on bigger files
    file_read = f.read
    file_tell = f.tell

    out_read = out.read
    out_write = out.write
    out_tell = out.tell
    out_seek = out.seek

    range_8 = [i for i in range(8)]

    while out_tell() < decompressed_size and not eof:
        code_byte = file_read(1)[0]
        
        for i in range_8:
            #is_set = ((code_byte << i) & 0x80) != 0
            
            if (code_byte << i) & 0x80:
                out_write(file_read(1)) # Write next byte as-is without requiring decompression
            else:
                if file_tell() >= maxsize-1:
                    eof = True
                    break

                data = file_read(2)
                infobyte = data[0] << 8 | data[1]
                

                bytecount = infobyte >> 12 
                
                if bytecount == 0:
                    if file_tell() > maxsize-1:
                        eof = True
                        break
                    bytecount = file_read(1)[0] + 0x12
                else:
                    bytecount += 2
                
                offset = infobyte & 0x0FFF
                
                current = out_tell()
                seekback = current - (offset+1)
                
                if seekback < 0:
                    raise RuntimeError("Malformed Yaz0 file: Seek back position goes below 0")

                out_seek(seekback)
                copy = out_read(bytecount)
                out_seek(current)
                
                write_limited(out, copy, decompressed_size)

                copy_length = len(copy)
                
                if copy_length < bytecount:
                    # Copy source and copy distance overlap which essentially means that
                    # we have to repeat the copied source to make up for the difference
                    j = 0
                    for i in range(bytecount-copy_length):
                        #write_limited(out, copy[j:j+1], decompressed_size)
                        if out_tell() < decompressed_size:
                            out_write(copy[j:j+1])
                        else:
                            break

                        j = (j+1) % copy_length
    
    if out.tell() < decompressed_size:
        #print("this isn't right")
        raise RuntimeError("Didn't decompress correctly, notify the developer!")
    if out.tell() > decompressed_size:
        print(  "Warning: output is longer than decompressed size for some reason: "
                "{}/decompressed: {}".format(out.tell(), decompressed_size))


def compress_slow(uncomp_data, search_depth=0x1000, should_pad_data=False):
    comp_data = BytesIO()
    write_magic_str(comp_data, 0, "Yaz0", 4)
    
    uncomp_size = data_len(uncomp_data)
    write_u32(comp_data, 4, uncomp_size)
    
    write_u32(comp_data, 8, 0)
    write_u32(comp_data, 0xC, 0)
    
    Yaz0.next_num_bytes = 0
    Yaz0.next_match_pos = None
    Yaz0.next_flag = False
    
    uncomp_offset = 0
    uncomp = read_and_unpack_bytes(uncomp_data, 0, uncomp_size, "B"*uncomp_size)
    comp_offset = 0x10
    dst = []
    valid_bit_count = 0
    curr_code_byte = 0
    while uncomp_offset < uncomp_size:
      num_bytes, match_pos = get_num_bytes_and_match_pos(uncomp, uncomp_offset, search_depth=search_depth)
      
      if num_bytes < 3:
        # Copy the byte directly
        dst.append(uncomp[uncomp_offset])
        uncomp_offset += 1
        
        curr_code_byte |= (0x80 >> valid_bit_count)
      else:
        dist = (uncomp_offset - match_pos - 1)
        
        if num_bytes >= 0x12:
          dst.append((dist & 0xFF00) >> 8)
          dst.append((dist & 0x00FF))
          
          if num_bytes > Yaz0.MAX_RUN_LENGTH:
            num_bytes = Yaz0.MAX_RUN_LENGTH
          dst.append(num_bytes - 0x12)
        else:
          byte = (((num_bytes - 2) << 4) | (dist >> 8) & 0x0F)
          dst.append(byte)
          dst.append(dist & 0xFF)
        
        uncomp_offset += num_bytes
      
      valid_bit_count += 1
      
      if valid_bit_count == 8:
        # Finished 8 codes, so write this block
        write_u8(comp_data, comp_offset, curr_code_byte)
        comp_offset += 1
        
        for byte in dst:
          write_u8(comp_data, comp_offset, byte)
          comp_offset += 1
        
        curr_code_byte = 0
        valid_bit_count = 0
        dst = []
    
    if valid_bit_count > 0:
      # Still some codes leftover that weren't written yet, so write them now.
      write_u8(comp_data, comp_offset, curr_code_byte)
      comp_offset += 1
      
      for byte in dst:
        write_u8(comp_data, comp_offset, byte)
        comp_offset += 1
    else:
      # If there are no codes leftover to be written, we instead write a single zero at the end for some reason.
      # I don't think it's necessary in practice, but we do it for maximum accuracy with the original algorithm.
      write_u8(comp_data, comp_offset, 0)
      comp_offset += 1
    
    if should_pad_data:
      align_data_to_nearest(comp_data, 0x20, padding_bytes=b'\0')
    
    return comp_data

def compress(uncomp_data):
    comp_data = BytesIO()
    write_magic_str(comp_data, 0, "Yaz0", 4)
    
    uncomp_size = data_len(uncomp_data)
    write_u32(comp_data, 4, uncomp_size)
    
    write_u32(comp_data, 8, 0)
    write_u32(comp_data, 0xC, 0)
    
    Yaz0.num_bytes_1 = 0
    Yaz0.match_pos = 0
    Yaz0.prev_flag = False
 
    uncomp_offset = 0
    uncomp = read_and_unpack_bytes(uncomp_data, 0, uncomp_size, "B"*uncomp_size)
    comp_offset = 0x10
    dst = []
    valid_bit_count = 0
    curr_code_byte = 0
    while uncomp_offset < uncomp_size:
      num_bytes, match_pos = get_num_bytes_and_match_pos(uncomp, uncomp_offset)
      
      if num_bytes < 3:
        # Copy the byte directly
        dst.append(uncomp[uncomp_offset])
        uncomp_offset += 1
        
        curr_code_byte |= (0x80 >> valid_bit_count)
      else:
        dist = (uncomp_offset - match_pos - 1)
        
        if num_bytes >= 0x12:
          dst.append((dist & 0xFF00) >> 8)
          dst.append((dist & 0x00FF))
          
          if num_bytes > 0xFF + 0x12:
            num_bytes = 0xFF + 0x12
          dst.append(num_bytes - 0x12)
        else:
          byte = (((num_bytes - 2) << 4) | (dist >> 8) & 0xFF)
          dst.append(byte)
          dst.append(dist & 0xFF)
        
        uncomp_offset += num_bytes
      
      valid_bit_count += 1
      
      if valid_bit_count == 8:
        # Finished 8 codes, so write this block
        write_u8(comp_data, comp_offset, curr_code_byte)
        comp_offset += 1
        
        for byte in dst:
          write_u8(comp_data, comp_offset, byte)
          comp_offset += 1
        
        curr_code_byte = 0
        valid_bit_count = 0
        dst = []
    
    if valid_bit_count > 0:
      # Still some codes leftover that weren't written yet, so write them now.
      write_u8(comp_data, comp_offset, curr_code_byte)
      comp_offset += 1
      
      for byte in dst:
        write_u8(comp_data, comp_offset, byte)
        comp_offset += 1
    
    return comp_data

def compress_fast(uncomp_data): #formerly,f, out
    out = BytesIO()
    
    data = uncomp_data.read()
    
    maxsize = len(data)
    
    out.write(b"Yaz0")
    out.write(pack(">I", maxsize))
    out.write(b"\x00"*8)

    out_write = out.write
    print("size:", hex(maxsize))
    print(maxsize//8, maxsize/8.0)
    for i in range(int(math.ceil(maxsize/8))):
        start = i*8 
        end = (i+1)*8
        if end > maxsize:
            # Pad data with 0's up to 8 bytes
            tocopy = data[start:maxsize] + b"\x00"*(end-maxsize)
            print("padded")
        else:
            tocopy = data[start:end]
        
        out_write(b"\xFF") # Set all bits in the code byte to 1 to mark the following 8 bytes as copy
        out_write(tocopy)
    return out

def write_magic_str(data, offset, new_string, max_length):
  # Writes a fixed-length string that does not have to end with a null byte.
  # This is for magic file format identifiers.
  
  str_len = len(new_string)
  if str_len > max_length:
    raise Exception("String %s is too long (max length 0x%X)" % (new_string, max_length))
  
  padding_length = max_length - str_len
  null_padding = b"\x00"*padding_length
  new_value = new_string.encode("shift_jis") + null_padding
  
  data.seek(offset)
  data.write(new_value)
  
def read_and_unpack_bytes(data, offset, length, format_string):
  data.seek(offset)
  requested_data = data.read(length)
  unpacked_data = struct.unpack(format_string, requested_data)
  return unpacked_data


def get_num_bytes_and_match_pos(uncomp, uncomp_offset, search_depth=DEFAULT_SEARCH_DEPTH):
    num_bytes = 1
    
    if Yaz0.next_flag:
      Yaz0.next_flag = False
      return (Yaz0.next_num_bytes, Yaz0.next_match_pos)
    
    Yaz0.next_flag = False
    num_bytes, match_pos = simple_rle_encode(uncomp, uncomp_offset, search_depth=search_depth)
    
    if num_bytes >= 3:
      # Check if the next byte has a match that would compress better than the current byte.
      Yaz0.next_num_bytes, Yaz0.next_match_pos = simple_rle_encode(uncomp, uncomp_offset+1, search_depth=search_depth)
      
      if Yaz0.next_num_bytes >= num_bytes+2:
        # If it does, then only copy one byte for this match and reserve the next match for later so we save more space.
        num_bytes = 1
        match_pos = None
        Yaz0.next_flag = True
    
    return (num_bytes, match_pos)


def simple_rle_encode(uncomp, uncomp_offset, search_depth=DEFAULT_SEARCH_DEPTH):
    start_offset = uncomp_offset - search_depth
    if start_offset < 0:
      start_offset = 0

    num_bytes = 0
    match_pos = None
    max_num_bytes_to_check = len(uncomp) - uncomp_offset
    if max_num_bytes_to_check > Yaz0.MAX_RUN_LENGTH:
      max_num_bytes_to_check = Yaz0.MAX_RUN_LENGTH

    for possible_match_pos in range(start_offset, uncomp_offset):
      for index_in_match in range(max_num_bytes_to_check):
        if uncomp[possible_match_pos + index_in_match] != uncomp[uncomp_offset + index_in_match]:
          break
        
        num_bytes_matched = index_in_match + 1
        if num_bytes_matched > num_bytes:
          num_bytes = num_bytes_matched
          match_pos = possible_match_pos

    return (num_bytes, match_pos)
