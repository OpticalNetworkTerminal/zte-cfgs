from zte_cfgs.format import (DB_VARIANT_ECB_ZERO, HEADER_SIZE, KeyMaterial,
                             pack_db, parse_header, unpack_db)


XML = b'<DB>\n  <Tbl name="Example"/>\n</DB>\n'
KEY = KeyMaterial("test-key", "test-iv")


def test_all_database_versions_round_trip():
    for version in range(5):
        material = KEY if version in (3, 4) else None
        packed = pack_db(XML, version, material)
        assert parse_header(packed)["version"] == version
        unpacked, _ = unpack_db(packed, material, strict_crc=True)
        assert unpacked == XML


def test_encrypted_data_changes_with_key():
    first = pack_db(XML, 4, KEY)
    second = pack_db(XML, 4, KeyMaterial("other-key", "test-iv"))
    assert first != second


def test_h2_ecb_zero_variant_round_trip_across_blocks():
    xml = b"<DB>" + b"x" * 70000 + b"</DB>"
    packed = pack_db(xml, 0, variant=DB_VARIANT_ECB_ZERO)

    assert xml[:16] not in packed[HEADER_SIZE:]
    unpacked, metadata = unpack_db(packed, strict_crc=True)

    assert unpacked == xml
    assert metadata["variant"] == DB_VARIANT_ECB_ZERO
    assert len(metadata["inner"]["blocks"]) == 2
