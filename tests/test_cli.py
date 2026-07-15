from argparse import Namespace
from pathlib import Path

from zte_cfgs.cli import cmd_scripts, output_xml_name


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
