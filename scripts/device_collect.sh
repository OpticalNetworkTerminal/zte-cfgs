#!/bin/sh
# Collect only files needed by zte-cfg-tools.  Run as root on the ONU.

set -u
PATH="/bin:/sbin:/usr/bin:/usr/sbin:${PATH:-}"
TS="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo now)"
OUT="/tmp/zte-cfg-tools-$TS"
mkdir -p "$OUT/cfg" "$OUT/tagparam"

copy() { [ -r "$1" ] && cp "$1" "$2" 2>/dev/null || true; }
copy /userconfig/cfg/db_user_cfg.xml "$OUT/cfg/db_user_cfg.xml"
copy /userconfig/cfg/db_backup_cfg.xml "$OUT/cfg/db_backup_cfg.xml"
copy /userconfig/cfg/db_default_cfg.xml "$OUT/cfg/db_default_cfg.xml"
copy /tagparam/paramtag "$OUT/tagparam/paramtag"
copy /wlan/paramtag "$OUT/tagparam/wlan_paramtag"
copy /etc/hardcode "$OUT/hardcode"

if [ -d /etc/hardcodefile ]; then
    mkdir -p "$OUT/hardcodefile"
    for f in /etc/hardcodefile/*; do
        [ -f "$f" ] && cp "$f" "$OUT/hardcodefile/" 2>/dev/null || true
    done
fi

{
    echo "timestamp=$TS"
    echo "model=$(cat /proc/csp/productclass 2>/dev/null)"
    md5sum "$OUT"/cfg/*.xml 2>/dev/null || true
} > "$OUT/manifest.txt"

tar -czf "$OUT.tgz" -C /tmp "$(basename "$OUT")" || die="tar failed"
echo "$OUT.tgz"

