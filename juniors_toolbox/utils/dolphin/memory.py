import ctypes
import struct
from struct import pack, unpack
from ctypes import wintypes, sizeof, addressof, POINTER, pointer
from ctypes.wintypes import DWORD, ULONG, LONG, WORD
from multiprocessing import shared_memory
from typing import List, Optional, Set

# Various Windows structs/enums needed for operation
NULL = 0

TH32CS_SNAPHEAPLIST = 0x00000001
TH32CS_SNAPPROCESS  = 0x00000002
TH32CS_SNAPTHREAD   = 0x00000004
TH32CS_SNAPMODULE   = 0x00000008
TH32CS_SNAPALL      = TH32CS_SNAPHEAPLIST | TH32CS_SNAPPROCESS | TH32CS_SNAPTHREAD | TH32CS_SNAPMODULE
assert TH32CS_SNAPALL == 0xF


PROCESS_QUERY_INFORMATION   = 0x0400
PROCESS_VM_OPERATION        = 0x0008
PROCESS_VM_READ             = 0x0010
PROCESS_VM_WRITE            = 0x0020

MEM_MAPPED = 0x40000

ULONG_PTR = ctypes.c_ulonglong

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [ ( 'dwSize' , DWORD ) ,
                 ( 'cntUsage' , DWORD) ,
                 ( 'th32ProcessID' , DWORD) ,
                 ( 'th32DefaultHeapID' , ctypes.POINTER(ULONG)) ,
                 ( 'th32ModuleID' , DWORD) ,
                 ( 'cntThreads' , DWORD) ,
                 ( 'th32ParentProcessID' , DWORD) ,
                 ( 'pcPriClassBase' , LONG) ,
                 ( 'dwFlags' , DWORD) ,
                 ( 'szExeFile' , ctypes.c_char * 260 ) ]
                 
                 
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [    ( 'BaseAddress' , ctypes.c_void_p),
                    ( 'AllocationBase' , ctypes.c_void_p),
                    ( 'AllocationProtect' , DWORD),
                    ( 'PartitionID' , WORD),
                    ( 'RegionSize' , ctypes.c_size_t),
                    ( 'State' , DWORD),
                    ( 'Protect' , DWORD),
                    ( 'Type' , DWORD)]
 
 
class PSAPI_WORKING_SET_EX_BLOCK(ctypes.Structure):
    _fields_ = [    ( 'Flags', ULONG_PTR),
                    ( 'Valid', ULONG_PTR),
                    ( 'ShareCount', ULONG_PTR),
                    ( 'Win32Protection', ULONG_PTR),
                    ( 'Shared', ULONG_PTR),
                    ( 'Node', ULONG_PTR),
                    ( 'Locked', ULONG_PTR),
                    ( 'LargePage', ULONG_PTR),
                    ( 'Reserved', ULONG_PTR),
                    ( 'Bad', ULONG_PTR),
                    ( 'ReservedUlong', ULONG_PTR)]
                    
                    
#class PSAPI_WORKING_SET_EX_INFORMATION(ctypes.Structure):
#    _fields_ = [    ( 'VirtualAddress' , ctypes.c_void_p),
#                    ( 'VirtualAttributes' , PSAPI_WORKING_SET_EX_BLOCK)]

class PSAPI_WORKING_SET_EX_INFORMATION(ctypes.Structure):
    _fields_ = [    ( 'VirtualAddress' , ctypes.c_void_p),
                    #( 'Flags', ULONG_PTR),
                    ( 'Valid', ULONG_PTR, 1)]
                    #( 'ShareCount', ULONG_PTR),
                    #( 'Win32Protection', ULONG_PTR),
                    #( 'Shared', ULONG_PTR),
                    #( 'Node', ULONG_PTR),
                    #( 'Locked', ULONG_PTR),
                    #( 'LargePage', ULONG_PTR),
                    #( 'Reserved', ULONG_PTR),
                    #( 'Bad', ULONG_PTR),
                    #( 'ReservedUlong', ULONG_PTR)]
                    
    #def print_values(self):
    #    for i,v in self._fields_:
    #        print(i, getattr(self, i))


# The find_dolphin function is based on WindowsDolphinProcess::findPID() from 
# aldelaro5's Dolphin memory engine
# https://github.com/aldelaro5/Dolphin-memory-engine

"""
MIT License
Copyright (c) 2017 aldelaro5
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

class Dolphin(object):
    """
    Represents a running Dolphin process that we can access the memory of
    """
    KNOWN_EXE_NAMES = {b"Dolphin.exe", b"DolphinQt2.exe", b"DolphinWx.exe"}

    def __init__(self):
        self.reset()

    def connect(self, namelist: Set[str] = KNOWN_EXE_NAMES) -> bool:
        """
        Attempt to connect to a running Dolphin process for shared memory access
        """
        return self._find_dolphin(namelist) and self._init_shared_memory()
        
    def reset(self):
        self.pid = -1
        self.memory = None

    def is_connected(self) -> bool:
        return self.pid != -1 and self.memory is not None
        
    def read_ram(self, offset: int, size: int) -> bytes:
        return self.memory.buf[offset:offset+size]
    
    def write_ram(self, offset: int, data: bytes):
        self.memory.buf[offset:offset+len(data)] = data

    def read_bool(self, addr: int) -> bool:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 1)

        return struct.unpack(">?", value)[0]
    
    def read_sbyte(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 1)

        return struct.unpack(">b", value)[0]

    def read_sint16(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 2)

        return struct.unpack(">h", value)[0]

    def read_sint32(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 4)

        return struct.unpack(">i", value)[0]

    def read_ubyte(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 1)

        return struct.unpack(">B", value)[0]

    def read_uint16(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 2)

        return struct.unpack(">H", value)[0]

    def read_uint32(self, addr: int) -> int:
        assert addr >= 0x80000000
        value = self.read_ram(addr-0x80000000, 4)

        return struct.unpack(">I", value)[0]

    def read_float(self, addr: int) -> float:
        assert addr >= 0x80000000
        value = self.read_ram(addr - 0x80000000, 4)

        return struct.unpack(">f", value)[0]

    def read_double(self, addr: int) -> float:
        assert addr >= 0x80000000
        value = self.read_ram(addr - 0x80000000, 8)

        return struct.unpack(">d", value)[0]

    def write_bool(self, addr: int, val: bool):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">?", val))

    def write_sbyte(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">b", val))

    def write_sint16(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">h", val))

    def write_sint32(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">i", val))

    def write_ubyte(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">B", val))

    def write_uint16(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">H", val))

    def write_uint32(self, addr: int, val: int):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">I", val))

    def write_float(self, addr: int, val: float):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">f", val))

    def write_double(self, addr: int, val: float):
        assert addr >= 0x80000000
        self.write_ram(addr - 0x80000000, struct.pack(">d", val))

    def _find_dolphin(self, namelist: Set[str] = KNOWN_EXE_NAMES, skipPIDs: Optional[Set[int]] = None) -> bool:
        """
        Finds a running Dolphin process to share memory with
        """
        if skipPIDs is None:
            skipPIDs = set()

        entry = PROCESSENTRY32()
        entry.dwSize = sizeof(PROCESSENTRY32)
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, NULL)
        
        potentialPID = -1
        if ctypes.windll.kernel32.Process32First(snapshot, pointer(entry)):   
            if entry.th32ProcessID not in skipPIDs and entry.szExeFile in namelist:
                potentialPID = entry.th32ProcessID
            else:
                while ctypes.windll.kernel32.Process32Next(snapshot, pointer(entry)):
                    if entry.th32ProcessID in skipPIDs:
                        continue
                    if entry.szExeFile in namelist:
                        potentialPID = entry.th32ProcessID 
            
        ctypes.windll.kernel32.CloseHandle(snapshot)
        
        if potentialPID == -1:
            return False

        self.pid = potentialPID
        return True
    
    def _init_shared_memory(self) -> bool:
        """
        Creates a shared memory object with the hooked Dolphin process
        """
        try:
            self.memory = shared_memory.SharedMemory(f"dolphin-emu.{self.pid}")
            return True
        except FileNotFoundError:
            return False

        
if __name__ == "__main__":
    dolphin = Dolphin()
    dolphin.connect()

    if dolphin.is_connected():
        print("Found Dolphin!")
    else:
        print("Didn't find Dolphin")

    print(dolphin.pid)
    
    import random 
    randint = random.randint
    from timeit import default_timer
    
    print("Testing Shared Memory Method")
    start = default_timer()
    count = 500000
    for i in range(count):
        value = randint(0, 2**32-1)
        dolphin.write_uint32(0x80000000, value)
        
        result = dolphin.read_uint32(0x80000000)
        assert result == value
    diff = default_timer()-start 
    print(count/diff, "per sec")
    print("time: ", diff)