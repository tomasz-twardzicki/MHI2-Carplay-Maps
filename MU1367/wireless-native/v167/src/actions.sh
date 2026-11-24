#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# SD-only profile and migration entry. The test2 parent runtime is unchanged.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
BOUNDARY=$M/ramdisk/.cpmap-profile-v167-reboot
CURRENT=carplay-mu1367-profile-790-v167
PARENT=$APP/carplay-mu1367-wireless-native-v165t2
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "V167_PROFILE_FAIL=$1";exit 1; }
@HISTORICAL@
pin(){
 if [ "$1" = "$CURRENT" ];then echo @SHA790@;else known "$1";fi
}
for C in cat sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
for D in "$APP" "$M/ramdisk";do
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || fail UNSAFE_PARENT
  D=${D%/*}
 done
done
inspect_saved(){
 R=$APP/$1
 absent "$R" && return 0
 [ -d "$R" ] && [ ! -L "$R" ] && regular "$R/STATE" && regular "$R/control.sh" || fail UNKNOWN_SNAPSHOT_PRESERVED
 H=$(pin "$1") || fail UNKNOWN_CONTROLLER
 "$P/790/verify" "$R/control.sh" "$H" || fail CHANGED_SAVED_CONTROLLER_PRESERVED
 S=$(cat "$R/STATE")
 case "$S" in removed) return 0;;installed|collecting|prepared|installing) return 1;;*) fail UNKNOWN_STATE_PRESERVED;;esac
}
ACTIVE=
for N in @OLD_CHILDREN@ "$CURRENT";do
 if ! inspect_saved "$N";then
  [ -z "$ACTIVE" ] || fail MULTIPLE_CHILDREN_PRESERVED
  ACTIVE=$N
 fi
done
OLD_PARENT=
if ! inspect_saved carplay-mu1367-wireless-native-v166;then OLD_PARENT=carplay-mu1367-wireless-native-v166;fi
if [ "$ACTION" = status ];then
 echo "V167_BASELINE=1.6.5-e-test2 CHILD=${ACTIVE:-none} RETIRE_PARENT=${OLD_PARENT:-none}"
 for N in "$ACTIVE" "$OLD_PARENT";do
  [ -n "$N" ] || continue
  /bin/ksh "$APP/$N/control.sh" status "$APP/$N" || exit 1
 done
 exit 0
fi
case "$ACTION" in
 tune-*) [ "$ACTIVE" = "$CURRENT" ] && [ -z "$OLD_PARENT" ] || fail SELECT_CURRENT_790_FIRST
  absent "$BOUNDARY" || fail FULL_REBOOT_REQUIRED
  exec /bin/ksh "$P/tune.sh" "${ACTION#tune-}" "$P/790";;
 select-790) WANT=$CURRENT;;
 select-791|remove|base-install|base-uninstall|base-recover|base-restore-oem|base-wireless-uninstall|base-wireless-recover) WANT=none;;
 *) fail INVALID_ACTION;;
esac
absent "$BOUNDARY" || fail FULL_REBOOT_REQUIRED
retire(){
 R=$APP/$1
 CMD=uninstall
 [ "$(cat "$R/STATE")" = installed ] || CMD=recover
 /bin/ksh "$R/control.sh" "$CMD" "$R" || fail SAVED_LAYER_RESTORE_FAILED_KEEP_BACKUPS
 # RAM boundary is written only after the real controller restored its layer.
 (umask 077;set -C;echo "$ACTION" > "$BOUNDARY") && sync || fail REBOOT_MARKER
 echo "V167_RESTORED=$1 FULL_REBOOT_THEN_REPEAT_ACTION"
}
if [ -n "$ACTIVE" ] && [ "$ACTIVE" != "$WANT" ];then retire "$ACTIVE";exit 0;fi
if [ -n "$OLD_PARENT" ];then
 [ -z "$ACTIVE" ] || fail RESTORE_CHILD_BEFORE_PARENT
 retire "$OLD_PARENT";exit 0
fi
case "$ACTION" in
 select-790)
  /bin/ksh "$P/790/control.sh" install "$P/790" || fail PROFILE_INSTALL_FAILED
  (umask 077;set -C;echo "$ACTION" > "$BOUNDARY") && sync || fail REBOOT_MARKER
  echo V167_PROFILE_790_FULL_REBOOT_REQUIRED;;
 select-791)
  regular "$PARENT/STATE" && [ "$(cat "$PARENT/STATE")" = installed ] || fail FINISH_TEST2_BASELINE_INSTALL_AND_REBOOT_FIRST
  "$P/790/verify" "$PARENT/control.sh" @PARENT_SHA@ || fail TEST2_BASELINE_CHANGED
  [ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail RESTORE_790_PROFILE_FIRST
  echo V167_PROFILE_791_ORIGINAL_TEST2_INPUT;;
 remove) echo V167_PROFILE_ALREADY_REMOVED;;
 base-wireless-*) exec /bin/ksh "${P%/*}/carplay_mu1367_wireless_native/control.sh" "${ACTION#base-wireless-}" "${P%/*}/carplay_mu1367_wireless_native";;
 base-*) exec /bin/ksh "${P%/*}/carplay_mu1367_release/control.sh" "${ACTION#base-}" "${P%/*}/carplay_mu1367_release";;
esac
