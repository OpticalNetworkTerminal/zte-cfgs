from pathlib import Path
import struct

from zte_cfg_tools.e8 import MODEL_MAGIC, WRAP_MAGIC, extract_db, parse_cfg, repack_cfg
from zte_cfg_tools.format import KeyMaterial, pack_db


def test_current_e8_sample_round_trip(tmp_path: Path):
    source = Path(__file__).parents[2] / "e8_Config_Backup/ctce8_G7615-G-C.cfg"
    if not source.exists():
        database = pack_db(b"<DB/>\n", 4, KeyMaterial("key", "iv"))
        data = bytearray(128)
        data[:16] = WRAP_MAGIC
        struct.pack_into("<I", data, 0x18, 4)
        struct.pack_into("<I", data, 0x44, 128)
        struct.pack_into("<I", data, 0x48, 16 + len("TEST") + len(database))
        struct.pack_into("<I", data, 0x40, 2)
        source = tmp_path / "template.cfg"
        source.write_bytes(bytes(data) + MODEL_MAGIC + b"\0\0\0\0" + struct.pack(">I", 4) + b"TEST" + database)
    db, info = extract_db(source)
    assert info["model"] == "G7615-G-C"
    db_path = tmp_path / "db.xml"
    db_path.write_bytes(db)
    out = tmp_path / "repacked.cfg"
    rebuilt = repack_cfg(source, db_path, out)
    assert rebuilt["embedded_db_version"] == 4
    assert out.read_bytes() == source.read_bytes()
