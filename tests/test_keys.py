from pathlib import Path

from zte_cfg_tools.keys import indivkey_materials, read_indivkey


def test_indivkey_derivation_modes():
    materials = indivkey_materials("cKZF6ufRy2ecKZHfYPh7FfP9cUDPzbuE")
    assert len(materials) == 4
    assert materials[0].key_string == "e64c0347a55b5f2423fa487c3e646ac"
    assert materials[0].iv_string == "667b02a85c61c786def4521b060265e"


def test_paramtag_indivkey():
    path = Path(__file__).parents[2] / "tagparam/paramtag"
    if path.exists():
        assert read_indivkey(path)["value"]

