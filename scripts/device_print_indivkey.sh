#!/bin/sh
# BusyBox ash compatible.  No command(1), dd(1), bash or readlink required.
# Copy this file to the ONU and run: ash device_print_indivkey.sh

set -u
PATH="/bin:/sbin:/usr/bin:/usr/sbin:${PATH:-}"
PARAMTAG="${PARAMTAG:-/tagparam/paramtag}"
IV="${DB_USER_AES_IV_STRING:-667b02a85c61c786def4521b060265e8}"

die() { echo "ERROR: $*" >&2; exit 1; }
[ -r "$PARAMTAG" ] || die "cannot read $PARAMTAG"

# tag 0x0720, little-endian header: 20 07 20 00 20 00
HEX="$(hexdump -v -e '1/1 "%02x"' "$PARAMTAG" 2>/dev/null)" || die "hexdump failed"
POS="$(awk -v h="$HEX" 'BEGIN { print index(h, "200720002000") }')"
[ "${POS:-0}" -gt 0 ] 2>/dev/null || die "INDIVKEY tag 0x0720 not found"
TAG_OFF=$(( (POS - 1) / 2 ))
VALUE_OFF=$(( TAG_OFF + 6 ))
INDIVKEY="$(hexdump -v -s "$VALUE_OFF" -n 32 -e '1/1 "%_p"' "$PARAMTAG" 2>/dev/null)" || die "cannot read INDIVKEY"
[ "$(printf '%s' "$INDIVKEY" | wc -c | awk '{print $1}')" = 32 ] || die "INDIVKEY is not 32 bytes"

# cspd calls CspGetMD5(seed, 33, out), so the terminating NUL is included.
KEY_FULL="$(printf '%s\0' "$INDIVKEY" | md5sum | awk '{print $1}')"
KEY_STRING="$(printf '%s' "$KEY_FULL" | awk '{print substr($0, 1, 31)}')"
IV_STRING="$(printf '%s' "$IV" | awk '{print substr($0, 1, 31)}')"

echo "paramtag=$PARAMTAG"
echo "indivkey_id=1824"
echo "indivkey_tag=0x0720"
echo "indivkey_offset=$TAG_OFF"
echo "INDIVKEY=$INDIVKEY"
echo "DB_USER_AES_KEY_STRING=$KEY_STRING"
echo "DB_USER_AES_IV_STRING=$IV_STRING"
echo "export DB_USER_AES_KEY_STRING='$KEY_STRING'"
echo "export DB_USER_AES_IV_STRING='$IV_STRING'"
echo "export DB_AES_KEY_STRING='$KEY_STRING'"
echo "export DB_AES_IV_STRING='$IV_STRING'"

