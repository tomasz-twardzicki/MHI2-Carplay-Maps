#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Retire the exact test-1 child before installing the independent test-2 child.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
BOUNDARY=$M/ramdisk/.cpmap-profile-test-reboot
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "EXPERIMENTAL_PROFILE_FAIL=$1";exit 1; }
root(){ case "$1" in
 790) echo "$APP/carplay-mu1367-profile-790-test2";;
 791) echo "$APP/carplay-mu1367-overlay-touch-test";;
 legacy790) echo "$APP/carplay-mu1367-profile-790-test";;
esac; }
expected(){ case "$1" in
 790) echo @SHA790@;;
 791) echo @SHA791@;;
 legacy790) echo 0e7678f4f633fe36c74785be6d8a498a68b3ad6b464ca9ef1d0a19a4a51f0307;;
esac; }
# Check required commands before creating a reboot marker or restoring files.
for C in cat sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
ACTIVE=
for N in legacy790 790 791;do
 R=$(root "$N")
 if ! absent "$R";then
  [ -d "$R" ] && [ ! -L "$R" ] && regular "$R/STATE" && regular "$R/control.sh" || fail UNKNOWN_SNAPSHOT_PRESERVED
  "$P/790/verify" "$R/control.sh" "$(expected "$N")" || fail CHANGED_SAVED_CONTROLLER_PRESERVED
  S=$(cat "$R/STATE")
  case "$S" in removed) continue;;installed|collecting|prepared|installing) :;;*) fail UNKNOWN_STATE_PRESERVED;;esac
  [ -z "$ACTIVE" ] || fail MULTIPLE_PROFILES_PRESERVED
  ACTIVE=$N
 fi
done
if [ "$ACTION" = status ];then
 echo "EXPERIMENTAL_PROFILE=${ACTIVE:-none}"
 if [ -n "$ACTIVE" ];then R=$(root "$ACTIVE");/bin/ksh "$R/control.sh" status "$R";fi
 exit 0
fi
case "$ACTION" in tune-*) exec /bin/ksh "$P/tune.sh" "${ACTION#tune-}" "$P/790";;esac
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
