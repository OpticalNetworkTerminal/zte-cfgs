"""Key material loading and INDIVKEY/tagparam derivation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .format import KeyMaterial

DEFAULT_IV = "667b02a85c61c786def4521b060265e8"
DEFAULT_DB_KEY = "PON_Dkey"
DEFAULT_DB_IV = "PON_DIV"
# Compatibility default documented by zxcfg for the older fixed-user-key
# generation path.  New devices should use the local INDIVKEY instead.
LEGACY_USER_KEY = "8cc72b05705d5c46f412af8cbed55aad"
INDIVKEY_ID = 1824
INDIVKEY_TAG = 0x0720


class KeyError(ValueError):
    """Raised when a key source is missing or malformed."""


def _tag_candidates(data: bytes, tag_id: int) -> list[dict]:
    results: list[dict] = []
    for offset in range(0, max(0, len(data) - 6)):
        ident = int.from_bytes(data[offset:offset + 2], "little")
        max_len = int.from_bytes(data[offset + 2:offset + 4], "little")
        value_len = int.from_bytes(data[offset + 4:offset + 6], "little")
        if ident != tag_id or not 0 < value_len <= max_len <= 1024:
            continue
        end = offset + 6 + value_len
        if end > len(data):
            continue
        value = data[offset + 6:end]
        if not all(32 <= byte < 127 for byte in value):
            continue
        results.append({"offset": offset, "id": ident, "value": value.decode("ascii")})
    return results


def read_indivkey(path: Path) -> dict:
    data = path.read_bytes()
    candidates = [item for item in _tag_candidates(data, INDIVKEY_TAG) if len(item["value"]) >= 16]
    if not candidates:
        raise KeyError(f"INDIVKEY tag 0x{INDIVKEY_TAG:04x} was not found in {path}")
    item = candidates[0]
    item = {**item, "tag_name": "INDIVKEY", "id_decimal": INDIVKEY_ID,
            "value_hex": item["value"].encode("ascii").hex()}
    return item


def _slot(value: str, full: bool) -> str:
    return value if full else value[:31]


def indivkey_materials(seed: str, iv: str = DEFAULT_IV, mode: str = "auto") -> list[KeyMaterial]:
    modes = ["md5-nul-truncated", "md5-nul-full", "md5-truncated", "md5-full"]
    if mode != "auto":
        modes = [mode]
    result: list[KeyMaterial] = []
    for selected in modes:
        nul = selected.startswith("md5-nul")
        full = selected.endswith("full")
        digest = hashlib.md5(seed.encode("ascii") + (b"\0" if nul else b"")).hexdigest()
        result.append(KeyMaterial(_slot(digest, full), _slot(iv, full), selected))
    return result


def default_material() -> KeyMaterial:
    return KeyMaterial(DEFAULT_DB_KEY, DEFAULT_DB_IV, "built-in-default")


def load_profiles(path: Path | None) -> dict[str, dict]:
    candidates = [path] if path else [Path.cwd() / "zte-cfg-keys.json", Path.cwd() / "db_keys.json"]
    for candidate in candidates:
        if candidate and candidate.expanduser().exists():
            data = json.loads(candidate.expanduser().read_text(encoding="utf-8"))
            return data.get("profiles", data)
    return {}


def profile_materials(profile: str, profiles: dict[str, dict], key: str | None = None,
                      iv: str | None = None, indivkey: str | None = None,
                      iv_override: str | None = None) -> list[KeyMaterial]:
    if key and iv:
        return [KeyMaterial(key, iv, "explicit")]
    if indivkey:
        return indivkey_materials(indivkey, iv_override or DEFAULT_IV,
                                  "auto" if profile in ("auto", "user", "backup") else profile)
    selected = "user" if profile in ("auto", "user", "backup") else profile
    entry = profiles.get(selected)
    if entry and entry.get("key_string") and entry.get("iv_string"):
        return [KeyMaterial(entry["key_string"], entry["iv_string"], f"profile:{selected}")]
    if selected == "default":
        return [default_material()]
    if selected in ("user", "backup"):
        return [KeyMaterial(LEGACY_USER_KEY, DEFAULT_IV, "legacy-fixed-user")]
    return []


def write_key_file(path: Path, indivkey: str, iv: str = DEFAULT_IV) -> dict:
    materials = indivkey_materials(indivkey, iv)
    data = {"profiles": {
        "user": {"key_string": materials[0].key_string, "iv_string": materials[0].iv_string,
                  "source": "tagparam INDIVKEY", "indivkey": indivkey},
        "backup": {"key_string": materials[0].key_string, "iv_string": materials[0].iv_string,
                   "source": "tagparam INDIVKEY", "indivkey": indivkey},
        "default": {"key_string": DEFAULT_DB_KEY, "iv_string": DEFAULT_DB_IV,
                    "source": "known DBDefAESCBC defaults"},
    }}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data
