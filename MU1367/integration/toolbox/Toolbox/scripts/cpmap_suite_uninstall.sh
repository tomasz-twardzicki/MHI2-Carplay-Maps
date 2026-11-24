#!/bin/ksh
set -u
M=${CPMAP_TEST_ROOT:-}
REMOTE=no
MEDIA=${CPMAP_TEST_MEDIA:-/fs/sda0 /fs/sdb0}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then
 REMOTE=yes
 MEDIA="/net/mmx/fs/sda0 /net/mmx/fs/sdb0"
fi
P=""
for V in $MEDIA;do
 if [ -s "$V/Custom/carplay_mu1367_guidance_v3/actions.sh" ];then P=$V/Custom/carplay_mu1367_guidance_v3;break;fi
done
if [ -z "$P" ];then echo MU1367_OEM_RESET_SD_NOT_FOUND_USE_MMX_SHELL;exit 1;fi
if [ "$REMOTE" = yes ];then
 command -v on >/dev/null 2>&1 || { echo MU1367_OEM_RESET_MISSING_on_RUN_FROM_MMX;exit 1; }
 P=${P#/net/mmx}
 exec on -f mmx /bin/ksh "$P/actions.sh" uninstall "$P"
fi
exec /bin/ksh "$P/actions.sh" uninstall "$P"
