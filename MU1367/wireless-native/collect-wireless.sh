#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Read unit state; write diagnostics only to the selected SD card.
# Run on MMX: /bin/ksh /fs/sda0/collect-wireless.sh /fs/sda0
set -u
M=${CPMAP_TEST_ROOT:-}
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
for C in cat cp mkdir ls grep sync mount;do
 command -v "$C" >/dev/null 2>&1 || { echo "WIRELESS_DIAG_MISSING_$C";exit 1; }
done
regular "$M/ifs/lsd.jxe" || { echo WIRELESS_DIAG_RUN_ON_MMX_FIRST;exit 1; }
V=${1:-/fs/sda0}
case "$V" in /fs/sda0|/fs/sdb0) ;; *) echo WIRELESS_DIAG_SD_PATH_REQUIRED;exit 1;;esac
VOL=$M$V
[ -d "$VOL" ] && [ ! -L "$VOL" ] && [ ! -L "$VOL/Log" ] || { echo WIRELESS_DIAG_SD_UNSAFE_OR_MISSING;exit 1; }
if [ -z "$M" ];then mount -uw "$V" || exit 1;fi
N=$$
OUT=$VOL/Log/wireless-diag-$N
while ! absent "$OUT";do N=$((N+1));OUT=$VOL/Log/wireless-diag-$N;done
mkdir -p "$OUT/logs" "$OUT/state" "$OUT/scopes" "$OUT/preferences" || exit 1
APP=$M/mnt/app
copy_file(){
 if regular "$1";then cp -p "$1" "$2" || echo "COPY_FAILED=$1" >> "$OUT/summary.txt"
 else echo "ABSENT_OR_UNSAFE=$1" >> "$OUT/summary.txt";fi
}
{
 echo 'Wireless AID diagnostics; capture while connected over Wi-Fi, USB unplugged.'
 echo '=== managed layer state'
 for L in carplay-mu1367-wireless-native carplay-mu1367-guidance-v3;do
  echo "$L"
  for F in VERSION STATE;do regular "$APP/$L/$F" && cat "$APP/$L/$F";done
 done
 echo '=== runtime fingerprints'
 if regular "$APP/carplay-mu1367-wireless-native/verify";then
  for F in carplay-cluster-supervisor wireless-entry wireless-receiver-exec libomonob-wireless-maps.so;do
   echo "$F";"$APP/carplay-mu1367-wireless-native/verify" "$APP/carplaymaps/$F"
  done
 fi
 echo '=== wireless flags'
 for F in btwcp_enable btwcp_off wcp_autostart wcp_cp_off wcp_hs_off wcp_alt_off wcp_alt_probe altscreen.conf omonob-phone/cluster-profile v75-wireless-display.conf;do
  echo "$F";if regular "$M/mnt/persist/$F";then echo present;cat "$M/mnt/persist/$F";else echo absent;fi
 done
 echo '=== HMI launch hooks'
 grep -n -E 'OMONOB|start-wireless|BOOTCLASSPATH|LD_PRELOAD|^[[:space:]]*\$J9' "$APP/eso/hmi/lsd/lsd.sh"
 echo '=== MMX process names (no environment or command arguments)'
 if [ -z "$M" ] && command -v pidin >/dev/null 2>&1;then
  pidin -F '%a %N' 2>&1 | grep -i -E 'wcp|wireless|omonob|carplay|dio|supervisor|j9|lsd|gal'
 fi
} > "$OUT/summary.txt" 2>&1
for F in wcp_autostart.log wcp.log wcp_video.log omonob-phone.log;do
 copy_file "$M/dev/shmem/$F" "$OUT/logs/$F"
done
for F in omonob-791-input.log carplay-cluster-supervisor.log altscreen-most-bridge.log omonob-phone.log;do
 copy_file "$M/ramdisk/$F" "$OUT/logs/ramdisk-$F"
done
for F in wcp_receiver.pid wcp_video.pid wcp_cp_session wcp_alt_probe;do
 copy_file "$M/dev/shmem/$F" "$OUT/state/$F"
done
for F in v75-wireless-native.owner v75-wireless-transport.intent omonob-791-input.pid carplay-dio-manager.pid carplay-cluster-supervisor.pid carplay-altstream.ready;do
 copy_file "$M/ramdisk/$F" "$OUT/state/$F"
done
for S in "$M/ramdisk"/.v75-native-*;do
 [ -d "$S" ] && [ ! -L "$S" ] || continue
 NAME=${S##*/}
 TOKEN=${NAME#.v75-native-}
 [ "${#TOKEN}" = 32 ] || continue
 case "$TOKEN" in *[!0123456789abcdef]*) continue;;esac
 mkdir "$OUT/scopes/$NAME" || exit 1
 # Allowlist state only: never copy the entire receiver scope or pairing store.
 for F in cluster-feed.state cluster-session.accepted settings.state settings.previous maps.state maps.previous;do
  copy_file "$S/$F" "$OUT/scopes/$NAME/$F"
 done
done
for F in settings.state settings.previous wireless-carplay.state wireless-carplay.previous;do
 copy_file "$M/mnt/icab/persistent/cpmap-ui/$F" "$OUT/preferences/$F"
done
sync
echo "WIRELESS_DIAG_OK=$OUT"
echo 'Review logs for phone/vehicle identifiers before sharing. Pairing stores and hotspot configuration were excluded.'
