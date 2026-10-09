"""ZTE ctce8/e8_Config_Backup wrapper support."""

from __future__ import annotations

import struct
from pathlib import Path

from .format import FormatError

WRAP_MAGIC = bytes.fromhex("999999994444444455555555aaaaaaaa")
MODEL_MAGIC = bytes.fromhex("04030201")
XOR_KEY = (
    b"*&(*H65GFRUY6KH53%#74BUG^%^RFIOO*&*^&^RRU6YOK8PE(&(#TI_+"
    b"7(U9(7!U(HF*(ET6FGHKDIO8E@67!R#@#"
)


def _u32(data: bytes, offset: int, endian: str) -> int:
    return struct.unpack_from(endian + "I", data, offset)[0]


def xor_data(data: bytes) -> bytes:
    """Apply the repeating 89-byte XOR used by web-exported config.bin files."""
    return bytes(value ^ XOR_KEY[index % len(XOR_KEY)] for index, value in enumerate(data))


def _decode_payload(data: bytes, payload_offset: int) -> tuple[bytes, str]:
    payload = data[payload_offset:]
    if payload[:4] in (MODEL_MAGIC, MODEL_MAGIC[::-1]):
        return payload, "plain"
    decoded = xor_data(payload)
    if decoded[:4] in (MODEL_MAGIC, MODEL_MAGIC[::-1]):
        return decoded, "xor-89"
    raise FormatError("cfg model header magic mismatch")


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
    payload, payload_encoding = _decode_payload(data, payload_offset)
    model_len = _u32(payload, 8, ">")
    model_start = 12
    model_end = model_start + model_len
    if model_end + 8 > len(payload):
        raise FormatError("cfg model name exceeds file")
    if payload[model_end:model_end + 4] != b"\x01\x02\x03\x04":
        raise FormatError("embedded database magic mismatch")
    return {
        "size": len(data), "byte_order": "little" if endian == "<" else "big",
        "payload_offset": payload_offset,
        "payload_encoding": payload_encoding,
        "model": payload[model_start:model_end].decode("ascii", "replace"),
        "model_len": model_len, "payload_len": payload_len,
        "embedded_db_offset": payload_offset + model_end,
        "embedded_db_len": len(payload) - model_end,
        "embedded_db_version": _u32(payload, model_end + 4, ">"),
        "cfg_type": _u32(data, 0x40, endian) & 0xFFFF,
        "default_cfg_type": (_u32(data, 0x40, endian) >> 16) & 0xFFFF,
    }


def extract_db(path: Path) -> tuple[bytes, dict]:
    data = path.read_bytes()
    info = parse_cfg(data)
    payload, _ = _decode_payload(data, info["payload_offset"])
    relative_db_offset = info["embedded_db_offset"] - info["payload_offset"]
    return payload[relative_db_offset:], info


def repack_cfg_data(source: bytes, database: bytes, model: str | None = None) -> tuple[bytes, dict]:
    """Replace a wrapper's embedded DB and preserve its plain/XOR encoding."""
    info = parse_cfg(source)
    if database[:4] != b"\x01\x02\x03\x04":
        raise FormatError("database does not start with 01 02 03 04")
    model_text = model if model is not None else info["model"]
    model_data = model_text.encode("ascii")
    payload = MODEL_MAGIC + b"\0\0\0\0" + struct.pack(">I", len(model_data)) + model_data + database
    stored_payload = xor_data(payload) if info["payload_encoding"] == "xor-89" else payload
    rebuilt = bytearray(source[:info["payload_offset"]] + stored_payload)
    endian = "<" if info["byte_order"] == "little" else ">"
    struct.pack_into(endian + "I", rebuilt, 0x48, len(stored_payload))
    result = bytes(rebuilt)
    return result, parse_cfg(result)


def repack_cfg(template: Path, db_path: Path, output: Path, model: str | None = None) -> dict:
    source = template.read_bytes()
    database = db_path.read_bytes()
    rebuilt, info = repack_cfg_data(source, database, model)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)
    return info
