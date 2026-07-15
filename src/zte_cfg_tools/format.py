"""ZTE XML database container format.

The format uses big-endian 32-bit fields.  Versions 0/1/2 are unencrypted
variants; versions 3 and 4 contain the same compressed payload behind AES-CBC.
The implementation keeps all validation in this module so key auto-detection
cannot mistake random plaintext for a successful decrypt.
"""

from __future__ import annotations

import binascii
import hashlib
import struct
import zlib
from dataclasses import dataclass

from Crypto.Cipher import AES

MAGIC = 0x01020304
HEADER_SIZE = 0x3C
BLOCK_HEADER_SIZE = 12
SPLIT_SIZE = 0x10000
AES_BLOCK = 16


class FormatError(ValueError):
    """Raised when a ZTE container fails structural or integrity checks."""


@dataclass(frozen=True)
class KeyMaterial:
    key_string: str
    iv_string: str
    source: str = "explicit"


def u32be(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def p32be(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFFFF)


def crc_update(data: bytes, crc: int = 0xFFFFFFFF) -> int:
    return binascii.crc32(data, crc ^ 0xFFFFFFFF) ^ 0xFFFFFFFF


def crc_final(crc: int) -> int:
    return (~crc) & 0xFFFFFFFF


def make_header(words: list[int]) -> bytes:
    return b"".join(p32be(word) for word in (words + [0] * 15)[:15])


def parse_header(data: bytes) -> dict:
    if len(data) < HEADER_SIZE:
        raise FormatError(f"file is shorter than {HEADER_SIZE} bytes")
    words = [u32be(data, offset) for offset in range(0, HEADER_SIZE, 4)]
    return {
        "magic": f"0x{words[0]:08x}",
        "magic_valid": words[0] == MAGIC,
        "version": words[1],
        "raw_words": words,
        "nonzero_reserved": [
            {"offset": i * 4, "value": f"0x{value:08x}"}
            for i, value in enumerate(words[2:], 2)
            if value
        ],
    }


def parse_blocks(data: bytes, offset: int = HEADER_SIZE) -> list[dict]:
    blocks: list[dict] = []
    index = 0
    while offset < len(data):
        if offset + BLOCK_HEADER_SIZE > len(data):
            raise FormatError(f"truncated block header at 0x{offset:x}")
        plain_len, cipher_len, next_flag = struct.unpack_from(">III", data, offset)
        payload_offset = offset + BLOCK_HEADER_SIZE
        end = payload_offset + cipher_len
        if cipher_len == 0 or end > len(data):
            raise FormatError(f"invalid block {index}: payload exceeds file")
        if cipher_len % AES_BLOCK:
            raise FormatError(f"block {index} cipher length is not AES aligned")
        if plain_len > cipher_len:
            raise FormatError(f"block {index} plain length exceeds cipher length")
        blocks.append({
            "index": index,
            "header_offset": offset,
            "payload_offset": payload_offset,
            "plain_len": plain_len,
            "cipher_len": cipher_len,
            "next": next_flag,
        })
        offset = end
        index += 1
        if next_flag == 0:
            break
    if not blocks or blocks[-1]["next"] != 0:
        raise FormatError("block chain has no terminating block")
    if offset != len(data):
        raise FormatError(f"unexpected trailing bytes at 0x{offset:x}")
    return blocks


def _cipher(material: KeyMaterial) -> AES:
    key = hashlib.sha256(material.key_string.encode("utf-8")[:31]).digest()
    iv = hashlib.sha256(material.iv_string.encode("utf-8")[:31]).digest()[:AES_BLOCK]
    return AES.new(key, AES.MODE_CBC, iv)


def decrypt_cbc(data: bytes, material: KeyMaterial) -> bytes:
    if len(data) % AES_BLOCK:
        raise FormatError("AES-CBC input is not block aligned")
    return _cipher(material).decrypt(data)


def encrypt_cbc(data: bytes, material: KeyMaterial) -> bytes:
    if len(data) % AES_BLOCK:
        raise FormatError("AES-CBC input is not block aligned")
    return _cipher(material).encrypt(data)


def decrypt_outer(data: bytes, material: KeyMaterial) -> tuple[bytes, dict]:
    header = parse_header(data)
    if not header["magic_valid"]:
        raise FormatError("outer magic mismatch")
    version = header["version"]
    if version not in (3, 4):
        raise FormatError(f"version {version} is not AES-encrypted")
    blocks = parse_blocks(data)
    plain = bytearray()
    for block in blocks:
        start = block["payload_offset"]
        encrypted = data[start : start + block["cipher_len"]]
        plain.extend(decrypt_cbc(encrypted, material)[: block["plain_len"]])
    return bytes(plain), {"outer_header": header, "outer_blocks": blocks}


def _inflate(payload: bytes, expected: int) -> tuple[bytes, str]:
    errors: list[str] = []
    for name, wbits in (("zlib", zlib.MAX_WBITS), ("raw-deflate", -zlib.MAX_WBITS)):
        try:
            result = zlib.decompress(payload, wbits)
            if expected and len(result) != expected:
                raise FormatError(f"{name} length {len(result)} != {expected}")
            return result, name
        except (zlib.error, FormatError) as exc:
            errors.append(f"{name}: {exc}")
    raise FormatError("inflate failed: " + "; ".join(errors))


def unpack_compressed(data: bytes, strict_crc: bool = False) -> tuple[bytes, dict]:
    header = parse_header(data)
    if not header["magic_valid"]:
        if data.lstrip().startswith(b"<"):
            return data, {"plain_xml": True}
        raise FormatError("compressed payload magic mismatch")
    words = header["raw_words"]
    if words[4] not in (0, SPLIT_SIZE):
        raise FormatError(f"unsupported split size: {words[4]}")
    if strict_crc:
        expected = words[6]
        actual = crc_final(crc_update(data[:0x18]))
        if expected != actual:
            raise FormatError(f"header CRC mismatch: 0x{actual:08x} != 0x{expected:08x}")
    blocks = []
    offset = HEADER_SIZE
    output = bytearray()
    crc = 0xFFFFFFFF
    while offset < len(data):
        if offset + BLOCK_HEADER_SIZE > len(data):
            raise FormatError("truncated compressed block header")
        raw_len, packed_len, next_flag = struct.unpack_from(">III", data, offset)
        payload_offset = offset + BLOCK_HEADER_SIZE
        end = payload_offset + packed_len
        if packed_len == 0 or end > len(data):
            raise FormatError("invalid compressed block length")
        payload = data[payload_offset:end]
        plain, codec = _inflate(payload, raw_len)
        output.extend(plain[:raw_len])
        crc = crc_update(payload, crc)
        blocks.append({"index": len(blocks), "raw_len": raw_len, "packed_len": packed_len,
                       "next": next_flag, "codec": codec})
        offset = end
        if next_flag == 0:
            break
    if not blocks or blocks[-1]["next"] != 0 or offset != len(data):
        raise FormatError("compressed block chain is invalid")
    if words[2] and len(output) != words[2]:
        raise FormatError(f"content length mismatch: {len(output)} != {words[2]}")
    if strict_crc and crc_final(crc) != words[5]:
        raise FormatError(f"content CRC mismatch: 0x{crc_final(crc):08x} != 0x{words[5]:08x}")
    return bytes(output), {"header": header, "blocks": blocks}


def unpack_db(data: bytes, material: KeyMaterial | None = None, strict_crc: bool = False) -> tuple[bytes, dict]:
    """Unpack all documented database versions 0 through 4."""
    header = parse_header(data)
    if not header["magic_valid"]:
        raise FormatError("database magic mismatch")
    version = header["version"]
    if version == 0:
        xml, inner = unpack_compressed(data, strict_crc)
        return xml, {"version": version, "inner": inner}
    if version == 1:
        xml = data[HEADER_SIZE:]
        if not xml.lstrip().startswith(b"<"):
            raise FormatError("version 1 payload is not XML")
        return xml, {"version": version, "plain_xml": True}
    if version == 2:
        xml, inner = unpack_compressed(data[HEADER_SIZE:], strict_crc)
        return xml, {"version": version, "inner": inner}
    if version in (3, 4):
        if material is None:
            raise FormatError(f"version {version} needs AES key and IV")
        inner_data, outer = decrypt_outer(data, material)
        xml, inner = unpack_compressed(inner_data, strict_crc)
        return xml, {"version": version, "outer": outer, "inner": inner,
                     "key_source": material.source}
    raise FormatError(f"unsupported database version: {version}")


def pack_compressed(xml: bytes, level: int = 9) -> bytes:
    blocks = bytearray()
    crc = 0xFFFFFFFF
    chunks = [xml[i : i + SPLIT_SIZE] for i in range(0, len(xml), SPLIT_SIZE)] or [b""]
    packed_chunks = [zlib.compress(chunk, level) for chunk in chunks]
    block_offsets: list[int] = []
    cursor = HEADER_SIZE
    for packed in packed_chunks:
        block_offsets.append(cursor)
        cursor += BLOCK_HEADER_SIZE + len(packed)
    for index, (chunk, packed) in enumerate(zip(chunks, packed_chunks)):
        next_offset = block_offsets[index + 1] if index + 1 < len(chunks) else 0
        blocks += struct.pack(">III", len(chunk), len(packed), next_offset)
        blocks += packed
        crc = crc_update(packed, crc)
    last_block_offset = block_offsets[-1] if block_offsets else 0
    header = bytearray(make_header([MAGIC, 0, len(xml), last_block_offset,
                                    SPLIT_SIZE, crc_final(crc), 0]))
    header[0x18:0x1C] = p32be(crc_final(crc_update(bytes(header[:0x18]))))
    return bytes(header) + bytes(blocks)


def pack_db(xml: bytes, version: int, material: KeyMaterial | None = None,
            level: int = 9) -> bytes:
    if version == 0:
        return pack_compressed(xml, level)
    if version == 1:
        return make_header([MAGIC, 1]) + xml
    if version == 2:
        return make_header([MAGIC, 2]) + pack_compressed(xml, level)
    if version not in (3, 4):
        raise FormatError(f"unsupported database version: {version}")
    if material is None:
        raise FormatError(f"version {version} needs AES key and IV")
    inner = pack_compressed(xml, level)
    blocks = bytearray()
    chunks = [inner[i : i + SPLIT_SIZE] for i in range(0, len(inner), SPLIT_SIZE)] or [b""]
    for index, chunk in enumerate(chunks):
        padded = chunk + b"\0" * (-len(chunk) % AES_BLOCK)
        if len(padded) == len(chunk):
            padded += b"\0" * AES_BLOCK
        encrypted = encrypt_cbc(padded, material)
        blocks += struct.pack(">III", len(chunk), len(encrypted), int(index + 1 < len(chunks)))
        blocks += encrypted
    return make_header([MAGIC, version]) + bytes(blocks)
