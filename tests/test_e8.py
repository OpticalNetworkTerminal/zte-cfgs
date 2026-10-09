from pathlib import Path
import struct

from zte_cfgs.e8 import (MODEL_MAGIC, WRAP_MAGIC, extract_db, parse_cfg,
                         repack_cfg, xor_data)
from zte_cfgs.format import (DB_VARIANT_ECB_ZERO, KeyMaterial, pack_db,
                             unpack_db)


def make_cfg(database: bytes, model: str = "TEST", xor: bool = False) -> bytes:
    model_data = model.encode("ascii")
    payload = MODEL_MAGIC + b"\0\0\0\0" + struct.pack(">I", len(model_data))
    payload += model_data + database
    stored_payload = xor_data(payload) if xor else payload
    data = bytearray(128)
    data[:16] = WRAP_MAGIC
    struct.pack_into("<I", data, 0x18, 4)
    struct.pack_into("<I", data, 0x44, 128)
    struct.pack_into("<I", data, 0x48, len(stored_payload))
    struct.pack_into("<I", data, 0x40, 2)
    return bytes(data) + stored_payload


def test_current_e8_sample_round_trip(tmp_path: Path):
    source = Path(__file__).parents[2] / "e8_Config_Backup/ctce8_G7615-G-C.cfg"
    expected_model = "G7615-G-C"
    if not source.exists():
        database = pack_db(b"<DB/>\n", 4, KeyMaterial("key", "iv"))
        source = tmp_path / "template.cfg"
        source.write_bytes(make_cfg(database))
        expected_model = "TEST"
    db, info = extract_db(source)
    assert info["model"] == expected_model
    db_path = tmp_path / "db.xml"
    db_path.write_bytes(db)
    out = tmp_path / "repacked.cfg"
    rebuilt = repack_cfg(source, db_path, out)
    assert rebuilt["embedded_db_version"] == 4
    assert out.read_bytes() == source.read_bytes()


def test_h2_web_config_xor_extract_and_repack(tmp_path: Path):
    xml = b"<DB><Tbl name=\"H2-3e\"/></DB>\n"
    database = pack_db(xml, 0, variant=DB_VARIANT_ECB_ZERO)
    source = tmp_path / "config.bin"
    source.write_bytes(make_cfg(database, model="H2-3e", xor=True))

    extracted, info = extract_db(source)
    assert extracted == database
    assert info["model"] == "H2-3e"
    assert info["payload_encoding"] == "xor-89"
    assert unpack_db(extracted, strict_crc=True)[0] == xml

    db_path = tmp_path / "config.db"
    db_path.write_bytes(extracted)
    output = tmp_path / "config.repacked.bin"
    rebuilt = repack_cfg(source, db_path, output)
    assert rebuilt["payload_encoding"] == "xor-89"
    assert output.read_bytes() == source.read_bytes()
