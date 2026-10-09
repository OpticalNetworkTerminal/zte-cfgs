from argparse import Namespace
from pathlib import Path
import struct

from zte_cfgs.cli import cmd_scripts, main, output_xml_name
from zte_cfgs.e8 import MODEL_MAGIC, WRAP_MAGIC, extract_db, xor_data
from zte_cfgs.format import DB_VARIANT_ECB_ZERO, pack_db, unpack_db


def test_output_xml_name_does_not_duplicate_suffix():
    assert output_xml_name("db_default_Henan_cfg.xml") == "db_default_Henan_cfg.xml"
    assert output_xml_name("db_user_cfg") == "db_user_cfg.xml"
    assert output_xml_name("DB_USER_CFG.XML") == "DB_USER_CFG.XML"


def test_scripts_exports_packaged_device_scripts(tmp_path: Path):
    result = cmd_scripts(Namespace(output=tmp_path, force=False))
    assert result == 0
    for name in ("device_collect.sh", "device_print_indivkey.sh"):
        path = tmp_path / name
        assert path.exists()
        assert path.stat().st_mode & 0o111
        assert path.read_text().startswith("#!/bin/sh")


def test_h2_config_cli_unpack_and_one_step_repack(tmp_path: Path):
    original_xml = b"<DB><Tbl name=\"Original\"/></DB>\n"
    database = pack_db(original_xml, 0, variant=DB_VARIANT_ECB_ZERO)
    model = b"H2-3e"
    payload = MODEL_MAGIC + b"\0\0\0\0" + struct.pack(">I", len(model)) + model + database
    wrapper = bytearray(128)
    wrapper[:16] = WRAP_MAGIC
    struct.pack_into("<I", wrapper, 0x18, 4)
    struct.pack_into("<I", wrapper, 0x40, 2)
    struct.pack_into("<I", wrapper, 0x44, 128)
    struct.pack_into("<I", wrapper, 0x48, len(payload))
    source = tmp_path / "config.bin"
    source.write_bytes(bytes(wrapper) + xor_data(payload))

    unpack_dir = tmp_path / "out"
    assert main(["unpack", str(source), "-o", str(unpack_dir), "--strict-crc"]) == 0
    unpacked_path = unpack_dir / "config.embedded.xml"
    assert unpacked_path.read_bytes() == original_xml

    edited_xml = b"<DB><Tbl name=\"Edited\"/></DB>\n"
    unpacked_path.write_bytes(edited_xml)
    output = tmp_path / "config.new.bin"
    assert main([
        "pack", str(unpacked_path), str(output), "--template", str(source)
    ]) == 0

    rebuilt_db, info = extract_db(output)
    assert info["model"] == "H2-3e"
    assert info["payload_encoding"] == "xor-89"
    assert unpack_db(rebuilt_db, strict_crc=True)[0] == edited_xml
