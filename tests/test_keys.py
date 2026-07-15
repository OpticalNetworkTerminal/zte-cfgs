from pathlib import Path
import struct

from zte_cfgs.keys import indivkey_materials, load_profiles, read_indivkey


def test_indivkey_derivation_modes():
    materials = indivkey_materials("cKZF6ufRy2ecKZHfYPh7FfP9cUDPzbuE")
    assert len(materials) == 4
    assert materials[0].key_string == "e64c0347a55b5f2423fa487c3e646ac"
    assert materials[0].iv_string == "667b02a85c61c786def4521b060265e"


def test_paramtag_indivkey():
    path = Path(__file__).parents[2] / "tagparam/paramtag"
    if path.exists():
        assert read_indivkey(path)["value"]


def test_keys_file_accepts_raw_tagh_paramtag(tmp_path: Path):
    path = tmp_path / "paramtag"
    value = b"cKZF6ufRy2ecKZHfYPh7FfP9cUDPzbuE"
    path.write_bytes(b"TAGH0201" + b"\0" * 20 + struct.pack("<HHH", 0x0720, 32, 32) + value)
    profiles = load_profiles(path)
    assert profiles["user"]["key_string"] == "e64c0347a55b5f2423fa487c3e646ac"
