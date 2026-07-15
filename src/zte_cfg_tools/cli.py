"""Command line interface for zte-cfg-tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .e8 import extract_db, parse_cfg, repack_cfg
from .format import FormatError, KeyMaterial, parse_header, pack_db, unpack_db
from .keys import (DEFAULT_IV, indivkey_materials, load_profiles, profile_materials,
                   read_indivkey, write_key_file)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _is_cfg(data: bytes) -> bool:
    return data.startswith(bytes.fromhex("999999994444444455555555aaaaaaaa"))


def output_xml_name(filename: str) -> str:
    """Keep a single .xml suffix for both cfg-like and XML-like inputs."""
    return filename if filename.lower().endswith(".xml") else f"{filename}.xml"


def _version_for_pack(value: str, source: Path | None, profile: str,
                      pack_type: str | None = None) -> int:
    if value == "auto" and pack_type is not None:
        return {"0": 0, "1": 3, "2": 4}[pack_type]
    if value != "auto":
        return int(value)
    if source and source.exists():
        version = parse_header(source.read_bytes())["version"]
        return version
    return {"default": 3, "user": 4, "backup": 4}.get(profile, 4)


def _materials(args: argparse.Namespace, path: Path) -> list[KeyMaterial]:
    profiles = load_profiles(args.keys_file)
    profile = args.profile
    if profile == "auto":
        profile = "default" if "default" in path.name.lower() else "user"
    if args.paramtag:
        item = read_indivkey(args.paramtag)
        args.indivkey = args.indivkey or item["value"]
    return profile_materials(profile, profiles, args.key_string, args.iv_string,
                             args.indivkey, args.iv_string)


def cmd_info(args: argparse.Namespace) -> int:
    data = args.input.read_bytes()
    if _is_cfg(data):
        result = {"type": "e8-cfg", **parse_cfg(data)}
    else:
        result = {"type": "db", "size": len(data), "header": parse_header(data)}
    print(_json(result))
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    item = read_indivkey(args.paramtag)
    data = write_key_file(args.output, item["value"], args.iv)
    result = {"paramtag": str(args.paramtag), "indivkey": item, "key_file": str(args.output),
              "profiles": data["profiles"]}
    print(_json(result))
    return 0


def _unpack_db_path(path: Path, args: argparse.Namespace, output_dir: Path) -> dict:
    data = path.read_bytes()
    version = parse_header(data)["version"]
    chosen: KeyMaterial | None = None
    errors: list[str] = []
    if version in (3, 4):
        for material in _materials(args, path):
            try:
                xml, metadata = unpack_db(data, material, args.strict_crc)
                chosen = material
                break
            except FormatError as exc:
                errors.append(f"{material.source}: {exc}")
        else:
            hint = " ; ".join(errors) if errors else "no key material"
            raise FormatError(f"cannot decrypt {path}: {hint}")
    else:
        xml, metadata = unpack_db(data, None, args.strict_crc)
    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / output_xml_name(path.name)
    xml_path.write_bytes(xml)
    meta = {"input": str(path), "output": str(xml_path), "metadata": metadata}
    if chosen:
        meta["key_material"] = {"source": chosen.source, "key_string": chosen.key_string,
                                 "iv_string": chosen.iv_string}
    (output_dir / f"{path.name}.json").write_text(_json(meta) + "\n", encoding="utf-8")
    return meta


def cmd_unpack(args: argparse.Namespace) -> int:
    data = args.input.read_bytes()
    if args.type == "e8" or (args.type == "auto" and _is_cfg(data)):
        embedded, info = extract_db(args.input)
        tmp = args.output / f"{args.input.name}.embedded.db"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(embedded)
        result = _unpack_db_path(tmp, args, args.output)
        print(_json({"container": "e8-cfg", "wrapper": info, "result": result}))
        return 0
    result = _unpack_db_path(args.input, args, args.output)
    print(_json(result))
    return 0


def _pack_key(args: argparse.Namespace, output: Path, version: int) -> KeyMaterial | None:
    if version not in (3, 4):
        return None
    profiles = load_profiles(args.keys_file)
    profile = args.profile
    if profile == "auto":
        profile = "default" if version == 3 else "user"
    materials = profile_materials(profile, profiles, args.key_string, args.iv_string,
                                  args.indivkey, args.iv_string)
    if not materials:
        raise FormatError("encrypted version needs --key-string/--iv-string, --indivkey, or a key file")
    return materials[0]


def cmd_pack(args: argparse.Namespace) -> int:
    version = _version_for_pack(args.version, args.template, args.profile, args.pack_type)
    material = _pack_key(args, args.output, version)
    data = pack_db(args.input.read_bytes(), version, material, args.level)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(_json({"output": str(args.output), "size": len(data), "version": version,
                 "key_source": material.source if material else None}))
    return 0


def cmd_e8_pack(args: argparse.Namespace) -> int:
    info = repack_cfg(args.template, args.database, args.output, args.model)
    print(_json({"output": str(args.output), **info}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zte-cfg",
        description="ZTE ONU db_user_cfg.xml / db_default_cfg.xml / ctce8_*.cfg offline tool",
        epilog=("Typical flow: zte-cfg keys paramtag -o zte-cfg-keys.json; "
                "zte-cfg unpack db_user_cfg.xml -o out --keys-file zte-cfg-keys.json; "
                "zte-cfg pack edited.xml db_user_cfg.new.xml --profile user --keys-file zte-cfg-keys.json"),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="show DB or e8 cfg headers")
    p.add_argument("input", type=Path)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("keys", help="read tag 0x0720/INDIVKEY and write a key profile JSON")
    p.add_argument("paramtag", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("zte-cfg-keys.json"))
    p.add_argument("--iv", default=DEFAULT_IV, help="user DB IV string; default is the known cspd IV")
    p.set_defaults(func=cmd_keys)

    def add_crypto_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("--profile", choices=("auto", "default", "user", "backup"), default="auto")
        command.add_argument("--keys-file", type=Path)
        command.add_argument("--key-string")
        command.add_argument("--iv-string")
        command.add_argument("--indivkey", help="raw INDIVKEY seed from tagparam")
        command.add_argument("--paramtag", type=Path, help="read INDIVKEY from this tagparam file")

    p = sub.add_parser("unpack", help="decrypt/decompress a DB or e8 USB backup")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("zte-cfg-out"))
    p.add_argument("--type", choices=("auto", "db", "e8"), default="auto")
    p.add_argument("--strict-crc", action="store_true")
    add_crypto_options(p)
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser("pack", help="compress/encrypt edited XML into a DB container")
    p.add_argument("input", type=Path, help="plain XML")
    p.add_argument("output", type=Path)
    p.add_argument("--version", choices=("auto", "0", "1", "2", "3", "4"), default="auto")
    p.add_argument("--pack-type", choices=("0", "1", "2"),
                    help="zxcfg-compatible alias: 0=plain, 1=default AES, 2=user AES")
    p.add_argument("--template", type=Path, help="copy DB version from an original container")
    p.add_argument("--level", type=int, choices=range(1, 10), default=9)
    add_crypto_options(p)
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("e8-pack", help="put a packed DB container back into a ctce8 cfg template")
    p.add_argument("template", type=Path)
    p.add_argument("database", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--model")
    p.set_defaults(func=cmd_e8_pack)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FormatError, OSError, ValueError) as exc:
        print(f"zte-cfg: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
