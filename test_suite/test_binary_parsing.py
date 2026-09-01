"""Comprehensive physical Zero-Mock test suite for cochem_base.io.binary_parsing.

Validates:
- Strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM.
- Zero personal machine or local user path leakage.
- Backward compatibility and lazy resolution in cochem_base.io.
- EndiannessMismatch-015 safety validations across little-endian and big-endian streams.
- Magic header validation and boundary checking.
- Integer (int32) and floating-point (float64) decoding precision.
- Truncation and unexpected end-of-data handling.
"""

from __future__ import annotations

import struct
from pathlib import Path
import pytest

import cochem_base.io as io_pkg
from cochem_base.io.binary_parsing import BinaryParser
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def binary_parsing_file_path() -> Path:
    """Return absolute path to cochem_base/io/binary_parsing.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "binary_parsing.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(binary_parsing_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = binary_parsing_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in binary_parsing.py"
    assert b"\n" in raw, "Missing newline characters in binary_parsing.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in binary_parsing.py"


def test_zero_personal_path_leaks(binary_parsing_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in binary_parsing.py."""
    lines = binary_parsing_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in binary_parsing.py: {leaks}"


def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io lazily exports BinaryParser."""
    parser_cls = getattr(io_pkg, "BinaryParser")
    assert parser_cls is BinaryParser


def test_binary_parser_initialization() -> None:
    """Verify BinaryParser initialization and endianness validation."""
    data = b"\x12\x34\x56\x78\x00\x00\x00\x01"
    parser_le = BinaryParser(data, expected_endianness="little")
    assert parser_le.data == data
    assert parser_le.expected_endianness == "little"
    assert parser_le.offset == 0

    parser_be = BinaryParser(data, expected_endianness="big")
    assert parser_be.expected_endianness == "big"

    with pytest.raises(ValueError, match="Expected endianness must be 'little' or 'big'"):
        BinaryParser(data, expected_endianness="invalid")  # type: ignore[arg-type]


def test_validate_magic_header_success() -> None:
    """Verify validation of magic headers for little-endian and big-endian formats."""
    le_data = BinaryParser.LITTLE_ENDIAN_MAGIC + b"\x01\x00\x00\x00"
    parser_le = BinaryParser(le_data, expected_endianness="little")
    assert parser_le.validate_magic_header() is True
    assert parser_le.offset == 4

    be_data = BinaryParser.BIG_ENDIAN_MAGIC + b"\x00\x00\x00\x01"
    parser_be = BinaryParser(be_data, expected_endianness="big")
    assert parser_be.validate_magic_header() is True
    assert parser_be.offset == 4


def test_validate_magic_header_failures() -> None:
    """Verify validation failures on short buffers and endianness mismatches."""
    short_parser = BinaryParser(b"\x12\x34", expected_endianness="little")
    with pytest.raises(ValueError, match="Data too short to contain magic header"):
        short_parser.validate_magic_header()

    mismatch_le = BinaryParser(BinaryParser.BIG_ENDIAN_MAGIC, expected_endianness="little")
    with pytest.raises(ValueError, match="Endianness mismatch detected"):
        mismatch_le.validate_magic_header()

    mismatch_be = BinaryParser(BinaryParser.LITTLE_ENDIAN_MAGIC, expected_endianness="big")
    with pytest.raises(ValueError, match="Endianness mismatch detected"):
        mismatch_be.validate_magic_header()


def test_read_int32() -> None:
    """Verify reading 32-bit signed integers in both endianness modes."""
    val_int = -12345678
    raw_le = struct.pack("<i", val_int)
    parser_le = BinaryParser(raw_le, expected_endianness="little")
    assert parser_le.read_int32() == val_int
    assert parser_le.offset == 4

    raw_be = struct.pack(">i", val_int)
    parser_be = BinaryParser(raw_be, expected_endianness="big")
    assert parser_be.read_int32() == val_int
    assert parser_be.offset == 4

    # Truncated error
    short_parser = BinaryParser(b"\x01\x02", expected_endianness="little")
    with pytest.raises(ValueError, match="Unexpected end of data"):
        short_parser.read_int32()


def test_read_float64() -> None:
    """Verify reading 64-bit IEEE double-precision floats in both endianness modes."""
    val_float = 3.141592653589793
    raw_le = struct.pack("<d", val_float)
    parser_le = BinaryParser(raw_le, expected_endianness="little")
    assert parser_le.read_float64() == val_float
    assert parser_le.offset == 8

    raw_be = struct.pack(">d", val_float)
    parser_be = BinaryParser(raw_be, expected_endianness="big")
    assert parser_be.read_float64() == val_float
    assert parser_be.offset == 8

    # Truncated error
    short_parser = BinaryParser(b"\x01\x02\x03\x04", expected_endianness="little")
    with pytest.raises(ValueError, match="Unexpected end of data"):
        short_parser.read_float64()


def test_sequential_stream_parsing() -> None:
    """Verify full sequential record stream parsing with header, int32, and float64."""
    header = BinaryParser.LITTLE_ENDIAN_MAGIC
    num_particles = 42
    binding_energy = -15.875
    raw_stream = header + struct.pack("<i", num_particles) + struct.pack("<d", binding_energy)

    parser = BinaryParser(raw_stream, expected_endianness="little")
    assert parser.validate_magic_header() is True
    assert parser.read_int32() == 42
    assert parser.read_float64() == -15.875
    assert parser.offset == len(raw_stream)
