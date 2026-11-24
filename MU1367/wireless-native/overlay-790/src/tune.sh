#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-${0%/*}/790}
M=${CPMAP_TEST_ROOT:-}
ROOT=$M/mnt/app/carplay-mu1367-profile-790-test
CONF=$M/mnt/persist/altscreen.conf
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "PROFILE790_TUNING_FAIL=$1";exit 1; }
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK"
 fi
}
trap cleanup EXIT
for C in awk cat cp mv rm mkdir chmod mount sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
for D in "$ROOT" "$M/mnt/persist" "$M/ramdisk";do
 while [ -n "$D" ] && [ "$D" != / ];do [ -d "$D" ] && [ ! -L "$D" ] || fail UNSAFE_PARENT;D=${D%/*};done
done
regular "$P/geometry.sh" && regular "$P/verify" && regular "$P/control.sh" || fail INVALID_SD
"$P/verify" "$P/geometry.sh" @GEOMETRY_SHA@ || fail INVALID_GEOMETRY_HELPER
. "$P/geometry.sh"
regular "$ROOT/control.sh" && "$P/verify" "$ROOT/control.sh" @CONTROLLER_SHA@ || fail UNKNOWN_SAVED_CONTROLLER
[ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail INSTALL_790_PROFILE_FIRST
cfg_ok "$CONF" || fail INVALID_CURRENT_GEOMETRY_PRESERVED
X=$(awk -F= '$1=="safex"{print $2}' "$CONF")
Y=$(awk -F= '$1=="safey"{print $2}' "$CONF")
W=$(awk -F= '$1=="safew"{print $2}' "$CONF")
H=$(awk -F= '$1=="safeh"{print $2}' "$CONF")
case "$ACTION" in
 status) echo "PROFILE790_SAFEAREA=$X,$Y,$W,$H STREAM=1010x376";exit 0;;
 x-up) X=$((X+10));;x-down) X=$((X-10));;
 y-up) Y=$((Y+10));;y-down) Y=$((Y-10));;
 width-up) W=$((W+10));;width-down) W=$((W-10));;
 height-up) H=$((H+10));;height-down) H=$((H-10));;
 reset) X=202;Y=16;W=606;H=344;;
 set) [ "$#" = 6 ] || fail SET_REQUIRES_X_Y_WIDTH_HEIGHT;X=$3;Y=$4;W=$5;H=$6;;
 *) fail INVALID_ACTION;;
esac
for V in "$X" "$Y" "$W" "$H";do
 case "$V" in ''|*[!0-9]*) fail OUT_OF_BOUNDS_NO_CHANGE;;esac
 [ "${#V}" -le 4 ] || fail OUT_OF_BOUNDS_NO_CHANGE
done
for F in "$M/dev/ipod0" "$M/dev/shmem/wcp_cp_session" "$M/ramdisk/carplay-altstream.ready";do absent "$F" || fail DISCONNECT_AND_FULL_REBOOT_FIRST;done
/bin/ksh "$ROOT/control.sh" install "$P" || fail INSTALLED_FILES_CHANGED
absent "$LOCK" && mkdir "$LOCK" || fail INSTALLER_LOCKED
OWN=yes
if [ -z "$M" ];then mount -uw /mnt/persist || fail PERSIST_REMOUNT;fi
NEW=$CONF.profile790-new-$$
absent "$NEW" || fail STAGE_EXISTS
{
 echo width=1010;echo height=376;echo fps=60;echo maxfps=60
 echo "safex=$X";echo "safey=$Y";echo "safew=$W";echo "safeh=$H"
 awk -v x="$X" 'BEGIN{print "nsafex=" (x-160)}'
 echo "nsafey=$Y";echo "nsafew=$W";echo "nsafeh=$H"
 echo alturl=maps:/car/instrumentcluster/map
} > "$NEW" || fail STAGE_WRITE
if ! cfg_ok "$NEW";then rm -f "$NEW";fail OUT_OF_BOUNDS_NO_CHANGE;fi
chmod 644 "$NEW" && mv "$NEW" "$CONF" && sync || fail COMMIT
echo "PROFILE790_SAFEAREA=$X,$Y,$W,$H FULL_REBOOT_REQUIRED"
