from zte_cfg_tools.cli import output_xml_name


def test_output_xml_name_does_not_duplicate_suffix():
    assert output_xml_name("db_default_Henan_cfg.xml") == "db_default_Henan_cfg.xml"
    assert output_xml_name("db_user_cfg") == "db_user_cfg.xml"
    assert output_xml_name("DB_USER_CFG.XML") == "DB_USER_CFG.XML"
