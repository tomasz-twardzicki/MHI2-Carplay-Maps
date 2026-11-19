#!/bin/ksh
# Read diagnostics on MMX; keep output on the SD that supplies the collector.
set -u
M=${CPMAP_TEST_ROOT:-}
REMOTE=no
MEDIA=${CPMAP_TEST_MEDIA:-/fs/sda0 /fs/sdb0}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then
 REMOTE=yes
 MEDIA="/net/mmx/fs/sda0 /net/mmx/fs/sdb0"
fi
DATA=""
for V in $MEDIA;do
 C=$V/Toolbox/scripts/cpmap_wireless_collect_data.sh
 if [ -f "$C" ] && [ ! -L "$C" ];then DATA=$C;break;fi
done
if [ -z "$DATA" ];then echo WIRELESS_DIAG_SD_NOT_FOUND;exit 1;fi
if [ "$REMOTE" = yes ];then
 command -v on >/dev/null 2>&1 || { echo WIRELESS_DIAG_MISSING_on_RUN_FROM_MMX;exit 1; }
 V=${V#/net/mmx}
 exec on -f mmx /bin/ksh "$V/Toolbox/scripts/cpmap_wireless_collect_data.sh" "$V"
fi
exec /bin/ksh "$DATA" "${V#"$M"}"
