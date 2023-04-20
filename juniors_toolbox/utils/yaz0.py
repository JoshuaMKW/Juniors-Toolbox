# The MIT License (MIT)
#
# Copyright (c) 2018 LagoLunatic
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from pathlib import Path


import struct
from io import BytesIO

from juniors_toolbox.utils.iohelper import *

try:
    import pyfastyaz0
    PY_FAST_YAZ0_INSTALLED = True
except ImportError:
    PY_FAST_YAZ0_INSTALLED = False


class Yaz0:
    MAX_RUN_LENGTH = 0xFF + 0x12

    # How far back to search when compressing.
    # Can search as far back as 0x1000 bytes, but the farther back we search the slower it is.
    DEFAULT_SEARCH_DEPTH = 0x1000

    # Variables to hold the reserved next match across loops.
    next_num_bytes = 0
    next_match_pos = 0
    next_flag = False

    @staticmethod
    def check_is_compressed(data: BinaryIO) -> bool:
        if read_string(data, maxlen=4) != "Yaz0":
            return False

        return True

    @staticmethod
    def decompress(comp_data: BinaryIO) -> BytesIO:
        if not Yaz0.check_is_compressed(comp_data):
            print("File is not compressed.")
            return comp_data

        if PY_FAST_YAZ0_INSTALLED:
            comp_data.seek(-4, 1)
            uncomp_data = comp_data.read()
            uncomp_data = pyfastyaz0.decompress(uncomp_data)
            uncomp_data = BytesIO(uncomp_data)
            return uncomp_data

        uncomp_size = read_uint32(comp_data)

        comp_data.seek(-4, 1)
        comp = comp_data.read()

        output = []
        output_len = 0
        src_offset = 0x10
        valid_bit_count = 0
        curr_code_byte = 0
        while output_len < uncomp_size:
            if valid_bit_count == 0:
                curr_code_byte = comp[src_offset]
                src_offset += 1
                valid_bit_count = 8

            if curr_code_byte & 0x80 != 0:
                output.append(comp[src_offset])
                src_offset += 1
                output_len += 1
            else:
                byte1 = comp[src_offset]
                byte2 = comp[src_offset+1]
                src_offset += 2

                dist = ((byte1 & 0xF) << 8) | byte2
                copy_src_offset = output_len - (dist + 1)
                num_bytes = (byte1 >> 4)
                if num_bytes == 0:
                    num_bytes = comp[src_offset] + 0x12
                    src_offset += 1
                else:
                    num_bytes += 2

                for i in range(0, num_bytes):
                    output.append(output[copy_src_offset])
                    output_len += 1
                    copy_src_offset += 1

            curr_code_byte = (curr_code_byte << 1)
            valid_bit_count -= 1

        uncomp_data = struct.pack("B"*output_len, *output)

        return BytesIO(uncomp_data)

    @staticmethod
    def compress(uncomp_data: BinaryIO, search_depth=DEFAULT_SEARCH_DEPTH, should_pad_data=False):
        if PY_FAST_YAZ0_INSTALLED:
            comp_data = pyfastyaz0.compress(uncomp_data.read(), search_depth)
            if should_pad_data:
                if (len(comp_data) % 0x20) != 0:
                    comp_data += b'\0' * (0x20 - (len(comp_data) % 0x20))
            return BytesIO(comp_data)

        comp_data = BytesIO()
        comp_data.write(b"Yaz0")

        _oldPos = uncomp_data.tell()
        uncomp_data.seek(0, 2)
        uncomp_size = uncomp_data.tell()
        uncomp_data.seek(_oldPos, 0)

        write_uint32(comp_data, uncomp_size)

        write_uint32(comp_data, 0)
        write_uint32(comp_data, 0)

        Yaz0.next_num_bytes = 0
        Yaz0.next_match_pos = None
        Yaz0.next_flag = False

        uncomp_offset = 0
        uncomp = uncomp_data.read()
        comp_offset = 0x10
        dst = []
        valid_bit_count = 0
        curr_code_byte = 0
        while uncomp_offset < uncomp_size:
            num_bytes, match_pos = Yaz0.get_num_bytes_and_match_pos(
                uncomp, uncomp_offset, search_depth=search_depth)

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
                write_ubyte(comp_data, curr_code_byte)

                for byte in dst:
                    write_ubyte(comp_data, byte)

                curr_code_byte = 0
                valid_bit_count = 0
                dst = []

        if valid_bit_count > 0:
            # Still some codes leftover that weren't written yet, so write them now.
            write_ubyte(comp_data, curr_code_byte)
            comp_offset += 1

            for byte in dst:
                write_ubyte(comp_data, byte)
                comp_offset += 1
        else:
            # If there are no codes leftover to be written, we instead write a single zero at the end for some reason.
            # I don't think it's necessary in practice, but we do it for maximum accuracy with the original algorithm.
            write_ubyte(comp_data, 0)
            comp_offset += 1

        if should_pad_data:
            if (len(comp_data) % 0x20) != 0:
                comp_data += b'\0' * (0x20 - (len(comp_data) % 0x20))

        return comp_data

    @staticmethod
    def get_num_bytes_and_match_pos(uncomp, uncomp_offset, search_depth=DEFAULT_SEARCH_DEPTH):
        num_bytes = 1

        if Yaz0.next_flag:
            Yaz0.next_flag = False
            return (Yaz0.next_num_bytes, Yaz0.next_match_pos)

        Yaz0.next_flag = False
        num_bytes, match_pos = Yaz0.simple_rle_encode(
            uncomp, uncomp_offset, search_depth=search_depth)

        if num_bytes >= 3:
            # Check if the next byte has a match that would compress better than the current byte.
            Yaz0.next_num_bytes, Yaz0.next_match_pos = Yaz0.simple_rle_encode(
                uncomp, uncomp_offset+1, search_depth=search_depth)

            if Yaz0.next_num_bytes >= num_bytes+2:
                # If it does, then only copy one byte for this match and reserve the next match for later so we save more space.
                num_bytes = 1
                match_pos = None
                Yaz0.next_flag = True

        return (num_bytes, match_pos)

    @staticmethod
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


def decompress_yaz0(data: BytesIO) -> BytesIO:
    """
    Decompresses YAZ0 compressed data

    :param data: Data to decompress
    :return: Decompressed data
    """
    return Yaz0.decompress(data)


def compress_yaz0(data: BytesIO, level: int = 7, align_data: bool = False) -> BytesIO:
    """
    Compresses data using YAZ0

    :param data: Data to compress
    :param level: Compression level
    :param align_data: Whether to align the data
    :return: Compressed data
    """
    return Yaz0.compress(data, search_depth=level, should_pad_data=align_data)


def decompress_yaz0_file(path: Path) -> BytesIO:
    """
    Decompresses a YAZ0 compressed file

    :param path: Path to the file
    :return: Decompressed data
    """
    with open(path, 'rb') as f:
        data = f.read()
    return decompress_yaz0(data)


def compress_yaz0_file(path: Path, data_alignment: int = 0, level: int = 7) -> BytesIO:
    """
    Compresses a file using YAZ0

    :param path: Path to the file
    :param data_alignment: Alignment of the data
    :param level: Compression level
    :return: Compressed data
    """
    with open(path, 'rb') as f:
        data = f.read()
    return compress_yaz0(data)


def is_yaz0_compressed(data: bytes) -> bool:
    """
    Checks if the data is YAZ0 compressed

    :param data: Data to check
    :return: True if the data is YAZ0 compressed
    """
    return data[:4] == b'Yaz0'


def is_yaz0_file(path: Path) -> bool:
    """
    Checks if the file is YAZ0 compressed

    :param path: Path to the file
    :return: True if the file is YAZ0 compressed
    """
    with open(path, 'rb') as f:
        data = f.read(4)
    return is_yaz0_compressed(data)
