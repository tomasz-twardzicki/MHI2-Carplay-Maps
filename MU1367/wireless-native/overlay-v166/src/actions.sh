#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
BOUNDARY=$M/ramdisk/.cpmap-profile-test-reboot
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "EXPERIMENTAL_PROFILE_FAIL=$1";exit 1; }
root(){ case "$1" in 790) echo "$APP/carplay-mu1367-profile-790-test";;791) echo "$APP/carplay-mu1367-overlay-touch-test";;esac; }
expected(){ case "$1" in 790) echo @SHA790@;;791) echo @SHA791@;;esac; }
case "$ACTION" in tune-*) exec /bin/ksh "$P/tune.sh" "${ACTION#tune-}" "$P/790";;esac
ACTIVE=
for N in 790 791;do
 R=$(root "$N")
 if ! absent "$R";then
  [ -d "$R" ] && [ ! -L "$R" ] && regular "$R/STATE" && regular "$R/control.sh" || fail UNKNOWN_SNAPSHOT_PRESERVED
  "$P/$N/verify" "$R/control.sh" "$(expected "$N")" || fail CHANGED_SAVED_CONTROLLER_PRESERVED
  S=$(cat "$R/STATE")
  case "$S" in removed) continue;;installed|collecting|prepared|installing) :;;*) fail UNKNOWN_STATE_PRESERVED;;esac
  [ -z "$ACTIVE" ] || fail MULTIPLE_PROFILES_PRESERVED
  ACTIVE=$N
 fi
done
if [ "$ACTION" = status ];then
 echo "EXPERIMENTAL_PROFILE=${ACTIVE:-none}"
 [ -z "$ACTIVE" ] || /bin/ksh "$P/$ACTIVE/control.sh" status "$P/$ACTIVE"
 exit 0
fi
absent "$BOUNDARY" || fail FULL_REBOOT_REQUIRED
case "$ACTION" in select-790) WANT=790;;select-791) WANT=791;;remove|base-install|base-uninstall|base-recover|base-restore-oem|base-wireless-uninstall|base-wireless-recover) WANT=none;;*) fail INVALID_ACTION;;esac
if [ -n "$ACTIVE" ] && [ "$ACTIVE" != "$WANT" ];then
 R=$(root "$ACTIVE")
 CMD=uninstall
 [ "$(cat "$R/STATE")" = installed ] || CMD=recover
 /bin/ksh "$R/control.sh" "$CMD" "$R" || fail SNAPSHOT_RESTORE_FAILED_KEEP_BACKUPS
 echo "$ACTION" > "$BOUNDARY" && sync || fail REBOOT_MARKER
 echo EXPERIMENTAL_PROFILE_REMOVED_FULL_REBOOT_THEN_REPEAT_ACTION
 exit 0
fi
case "$ACTION" in
 select-*) /bin/ksh "$P/$WANT/control.sh" install "$P/$WANT" || fail PROFILE_INSTALL_FAILED
  echo "$ACTION" > "$BOUNDARY" && sync || fail REBOOT_MARKER
  echo "EXPERIMENTAL_PROFILE=$WANT FULL_REBOOT_REQUIRED";;
 remove) echo EXPERIMENTAL_PROFILE_ALREADY_REMOVED;;
 base-wireless-*) exec /bin/ksh "${P%/*}/carplay_mu1367_wireless_native/control.sh" "${ACTION#base-wireless-}" "${P%/*}/carplay_mu1367_wireless_native";;
 base-*) exec /bin/ksh "${P%/*}/carplay_mu1367_release/control.sh" "${ACTION#base-}" "${P%/*}/carplay_mu1367_release";;
esac
