import struct
import sys

class BinaryParser:
    """
    Safely parses binary data while enforcing cross-architecture endianness safety mechanisms.
    Supports EndiannessMismatch-015 validations.
    """
    
    LITTLE_ENDIAN_MAGIC = b'\x12\x34\x56\x78'
    BIG_ENDIAN_MAGIC = b'\x78\x56\x34\x12'

    def __init__(self, data: bytes, expected_endianness: str = "little"):
        """
        expected_endianness: 'little' or 'big'
        """
        self.data = data
        self.offset = 0
        if expected_endianness not in ["little", "big"]:
            raise ValueError("Expected endianness must be 'little' or 'big'")
        self.expected_endianness = expected_endianness
        
    def validate_magic_header(self):
        """
        Reads the first 4 bytes and asserts that the endianness matches the expected architecture endianness.
        """
        if len(self.data) < 4:
            raise ValueError("Data too short to contain magic header.")
            
        header = self.data[0:4]
        self.offset = 4
        
        if self.expected_endianness == "little" and header != self.LITTLE_ENDIAN_MAGIC:
            raise ValueError(f"Endianness mismatch detected. Expected little-endian magic {self.LITTLE_ENDIAN_MAGIC}, got {header}")
            
        if self.expected_endianness == "big" and header != self.BIG_ENDIAN_MAGIC:
            raise ValueError(f"Endianness mismatch detected. Expected big-endian magic {self.BIG_ENDIAN_MAGIC}, got {header}")
            
        return True
        
    def read_int32(self) -> int:
        """
        Reads an int32 using the explicitly verified endianness format.
        """
        if len(self.data) - self.offset < 4:
            raise ValueError("Unexpected end of data.")
            
        fmt = "<i" if self.expected_endianness == "little" else ">i"
        val = struct.unpack_from(fmt, self.data, self.offset)[0]
        self.offset += 4
        return val

    def read_float64(self) -> float:
        """
        Reads a float64 using the explicitly verified endianness format.
        """
        if len(self.data) - self.offset < 8:
            raise ValueError("Unexpected end of data.")
            
        fmt = "<d" if self.expected_endianness == "little" else ">d"
        val = struct.unpack_from(fmt, self.data, self.offset)[0]
        self.offset += 8
        return val
