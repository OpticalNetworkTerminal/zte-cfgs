"""ZTE ctce8/e8_Config_Backup wrapper support."""

from __future__ import annotations

import struct
from pathlib import Path

from .format import FormatError

WRAP_MAGIC = bytes.fromhex("999999994444444455555555aaaaaaaa")
MODEL_MAGIC = bytes.fromhex("04030201")


def _u32(data: bytes, offset: int, endian: str) -> int:
    return struct.unpack_from(endian + "I", data, offset)[0]


def parse_cfg(data: bytes) -> dict:
    if len(data) < 128 or data[:16] != WRAP_MAGIC:
        raise FormatError("cfg wrapper magic/header mismatch")
    # Current devices store wrapper fields little-endian.  zxcfg-compatible
    # files advertise the order in the h4.x4 word at offset 0x14.
    endian = "<" if _u32(data, 0x18, "<") == 4 else ">"
    # h4.offset at 0x3c points to the type header (normally 0x40).  The
    # following field at 0x44 points to the model header (normally 0x80).
    payload_offset = _u32(data, 0x44, endian)
    if payload_offset < 128 or payload_offset >= len(data):
        payload_offset = 128
    payload_len = _u32(data, 0x48, endian)
    if payload_len and payload_offset + payload_len != len(data):
        raise FormatError("cfg payload length does not match file size")
    if payload_offset + 12 > len(data):
        raise FormatError("cfg payload header is truncated")
    model_magic = data[payload_offset:payload_offset + 4]
    if model_magic != MODEL_MAGIC and model_magic != MODEL_MAGIC[::-1]:
        raise FormatError("cfg model header magic mismatch")
    model_len = _u32(data, payload_offset + 8, ">")
    model_start = payload_offset + 12
    model_end = model_start + model_len
    if model_end + 8 > len(data):
        raise FormatError("cfg model name exceeds file")
    if data[model_end:model_end + 4] != b"\x01\x02\x03\x04":
        raise FormatError("embedded database magic mismatch")
    return {
        "size": len(data), "byte_order": "little" if endian == "<" else "big",
        "payload_offset": payload_offset, "model": data[model_start:model_end].decode("ascii", "replace"),
        "model_len": model_len, "payload_len": payload_len, "embedded_db_offset": model_end,
        "embedded_db_len": len(data) - model_end,
        "embedded_db_version": _u32(data, model_end + 4, ">"),
        "cfg_type": _u32(data, 0x40, endian) & 0xFFFF,
        "default_cfg_type": (_u32(data, 0x40, endian) >> 16) & 0xFFFF,
    }


def extract_db(path: Path) -> tuple[bytes, dict]:
    data = path.read_bytes()
    info = parse_cfg(data)
    return data[info["embedded_db_offset"]:], info


def repack_cfg(template: Path, db_path: Path, output: Path, model: str | None = None) -> dict:
    source = template.read_bytes()
    info = parse_cfg(source)
    database = db_path.read_bytes()
    if database[:4] != b"\x01\x02\x03\x04":
        raise FormatError("database does not start with 01 02 03 04")
    model_text = model if model is not None else info["model"]
    model_data = model_text.encode("ascii")
    payload = MODEL_MAGIC + b"\0\0\0\0" + struct.pack(">I", len(model_data)) + model_data + database
    rebuilt = source[:info["payload_offset"]] + payload
    rebuilt = bytearray(rebuilt)
    endian = "<" if info["byte_order"] == "little" else ">"
    struct.pack_into(endian + "I", rebuilt, 0x48, len(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)
    return parse_cfg(bytes(rebuilt))
