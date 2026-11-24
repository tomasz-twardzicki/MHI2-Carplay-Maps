#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Stable v1.6.1: retire saved layers, reboot, resume the checked base, then
# install/adopt the byte-identical, vehicle-confirmed wireless runtime.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
CUSTOM=${P%/*}
BASE=$CUSTOM/carplay_mu1367_guidance_v3
WIRELESS=$CUSTOM/carplay_mu1367_wireless_native
LOCK=$M/ramdisk/.cpmap-release-v161-lock
BOUNDARY=$M/ramdisk/.cpmap-release-v161-reboot
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
parents(){
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
fail(){ echo "MU1367_RELEASE_1_6_1_FAIL=$1";exit 1; }
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK" || :
 fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED_KEEP_SNAPSHOTS_REBOOT_AND_RESUME' HUP INT TERM
for C in cat cp mv rm mkdir sync mount;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
parents "$P/verify" && regular "$P/verify" || fail UNSAFE_PAYLOAD_OR_VERIFIER
check(){ regular "$1" && "$P/verify" "$1" "$2"; }
digest(){ "$P/verify" "$1"; }
check "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_K4525_OR_P4521_MU1367_REQUIRED
. "$P/compatibility.sh" || fail COMPATIBILITY_TABLE
case "$ACTION" in
 status)
  echo MU1367_RELEASE=1.6.1
  for N in $WIRELESS_ROOTS;do
   echo "LAYER=$N"
   for F in STATE VERSION;do regular "$APP/$N/$F" && cat "$APP/$N/$F";done
  done
  [ ! -e "$BOUNDARY" ] || echo FULL_REBOOT_REQUIRED_BEFORE_NEXT_STAGE
  /bin/ksh "$BASE/actions.sh" status "$BASE"
  exit $?;;
 install|uninstall|recover|restore-oem) ;;
 *) fail INVALID_ACTION;;
esac
# Check the entire release SD before invoking any saved controller or writing
# a reboot marker. The native firmware gate is never replaced on the unit.
. "$P/payload-check.sh" || fail SD_PAYLOAD_HASH
if [ "$ACTION" != recover ];then absent "$BOUNDARY" || fail FULL_REBOOT_REQUIRED_BEFORE_NEXT_STAGE;fi
parents "$LOCK" && absent "$LOCK" && mkdir "$LOCK" || fail RELEASE_LOCKED_REBOOT_DISCONNECTED
OWN=yes
ACTIVE=
ACTIVE_STATE=
for N in $WIRELESS_ROOTS;do
 R=$APP/$N
 parents "$R" && [ ! -L "$R" ] || fail UNSAFE_WIRELESS_SNAPSHOT
 absent "$R" && continue
 [ -d "$R" ] && regular "$R/STATE" && regular "$R/VERSION" || fail UNKNOWN_WIRELESS_SNAPSHOT_PRESERVED
 H=$(wireless_controller "$N") || fail UNKNOWN_WIRELESS_GENERATION
 check "$R/control.sh" "$H" || fail UNKNOWN_OR_CHANGED_WIRELESS_CONTROLLER_PRESERVED
 S=$(cat "$R/STATE")
 case "$S" in
  removed) continue;;
  installed|installing|prepared) ;;
  *) fail UNKNOWN_WIRELESS_STATE_PRESERVED;;
 esac
 [ -z "$ACTIVE" ] || fail MULTIPLE_ACTIVE_WIRELESS_LAYERS_PRESERVED
 ACTIVE=$N
 ACTIVE_STATE=$S
done
mark_reboot(){
 parents "$BOUNDARY" && { absent "$BOUNDARY" || regular "$BOUNDARY"; } || fail UNSAFE_REBOOT_MARKER
 echo "$ACTION" > "$BOUNDARY" && sync || fail REBOOT_MARKER_WRITE
}
prepared_originals_ok(){
 PR=$APP/$ACTIVE
 regular "$PR/BACKUPS_READY" && regular "$PR/backup.index.sha256" &&
  check "$PR/backup.index" "$(cat "$PR/backup.index.sha256")" || return 1
 EXPECTED=$(legacy_keys "$ACTIVE") || return 1
 SEEN=
 while read PK PH PE;do
  case " $EXPECTED " in *" $PK "*) ;; *) return 1;;esac
  case " $SEEN " in *" $PK "*) return 1;;esac
  [ -z "$PE" ] || return 1
  PT=$(legacy_target "$ACTIVE" "$PK") || return 1
  # A missing original may also have had a missing parent directory.
  PD=${PT%/*}
  while [ -n "$PD" ] && [ "$PD" != / ];do
   [ ! -L "$PD" ] || return 1
   if [ -e "$PD" ];then [ -d "$PD" ] || return 1;fi
   PD=${PD%/*}
  done
  parents "$PR/backup/$PK" || return 1
  if [ "$PH" = MISSING ];then absent "$PT" && absent "$PR/backup/$PK" || return 1
  else
   [ "${#PH}" = 64 ] || return 1
   case "$PH" in *[!0123456789abcdef]*) return 1;;esac
   check "$PR/backup/$PK" "$PH" && check "$PT" "$PH" || return 1
  fi
  SEEN="$SEEN $PK"
 done < "$PR/backup.index"
 for PK in $EXPECTED;do case " $SEEN " in *" $PK "*) ;; *) return 1;;esac;done
}
retain_prepared(){
 PR=$APP/$ACTIVE
 N=$$
 COUNT=0
 BACK=$PR.prepared-$N
 while ! absent "$BACK";do
  COUNT=$((COUNT+1));[ "$COUNT" -lt 10000 ] || fail PREPARED_ARCHIVE_NAMES_EXHAUSTED
  N=$((N+1));BACK=$PR.prepared-$N
 done
 if [ -z "$M" ];then mount -uw /mnt/app || fail APP_REMOUNT;fi
 mv "$PR" "$BACK" && sync || fail RETAIN_PREPARED_SNAPSHOT
 echo "MU1367_PREPARED_SNAPSHOT_RETAINED=$BACK"
}
retire_wireless(){
 R=$APP/$ACTIVE
 CMD=recover
 if [ "$ACTIVE_STATE" = installed ] && [ "$ACTION" != recover ];then CMD=uninstall;fi
 mark_reboot
 if [ "$ACTIVE_STATE" = prepared ] && prepared_originals_ok;then retain_prepared
 else /bin/ksh "$R/control.sh" "$CMD" "$R" || fail WIRELESS_RESTORE_FAILED_KEEP_SNAPSHOT;fi
 echo MU1367_WIRELESS_PREVIOUS_LAYER_RESTORED_FULL_REBOOT_THEN_REPEAT_ACTION
 echo 'NEXT: fully reboot with phones disconnected, then repeat the same action from this SD.'
}
base_ready(){
 baseline_ok || return 1
 for K in $KEYS;do
  T=$(target "$K") || return 1
  before_ok "$K" "$T" || return 1
 done
}
# A completed old OEM reset is a retained snapshot, not permission to overwrite
# a new installation. Move it aside without replacing any earlier archive.
retain_completed_oem(){
 R=$APP/carplay-mu1367-oem-reset
 [ -d "$R" ] || return 0
 regular "$R/STATE" || fail UNKNOWN_OEM_SNAPSHOT_PRESERVED
 [ "$(cat "$R/STATE")" = complete ] || return 0
 parents "$R/control.sh" && [ ! -L "$R" ] && regular "$R/control.sh" || fail UNSAFE_OEM_SNAPSHOT
 OEM=$CUSTOM/carplay_mu1367_oem_reset
 if /bin/ksh "$OEM/control.sh" verify "$OEM" >/dev/null 2>&1;then return 0;fi
 N=$$
 COUNT=0
 BACK=$R.complete-$N
 while ! absent "$BACK";do
  COUNT=$((COUNT+1));[ "$COUNT" -lt 10000 ] || fail OEM_ARCHIVE_NAMES_EXHAUSTED
  N=$((N+1));BACK=$R.complete-$N
 done
 if [ -z "$M" ];then mount -uw /mnt/app || fail APP_REMOUNT;fi
 mv "$R" "$BACK" && sync || fail RETAIN_OLD_OEM_RESET
 echo "MU1367_RETAINED_OEM_SNAPSHOT=$BACK"
}
case "$ACTION" in
 install)
  if [ -n "$ACTIVE" ];then
   if [ "$ACTIVE" = "$CURRENT_WIRELESS_ROOT" ] && [ "$ACTIVE_STATE" = installed ];then
    # No runtime replacement: stable adopts exactly the tested component set.
    /bin/ksh "$WIRELESS/control.sh" install "$WIRELESS" || fail INSTALLED_WIRELESS_INTEGRITY
    echo MU1367_RELEASE_1_6_1_ALREADY_INSTALLED
   else retire_wireless;fi
   exit 0
  fi
  mark_reboot
  if base_ready;then
   /bin/ksh "$WIRELESS/control.sh" install "$WIRELESS" || fail WIRELESS_INSTALL_FAILED_KEEP_SNAPSHOT
   echo MU1367_RELEASE_1_6_1_INSTALLED_FULL_REBOOT_REQUIRED
  else
   /bin/ksh "$BASE/actions.sh" install "$BASE" || fail BASE_INSTALL_FAILED_KEEP_SNAPSHOTS
   echo MU1367_RELEASE_BASE_STAGE_COMPLETE_FULL_REBOOT_THEN_RUN_INSTALL_AGAIN
  fi
  echo 'NEXT: fully reboot with phones disconnected, then run Install again until v1.6.1 is complete.';;
 uninstall|recover)
  if [ -n "$ACTIVE" ];then retire_wireless
  else
   mark_reboot
   /bin/ksh "$BASE/actions.sh" "$ACTION" "$BASE" || fail BASE_RECOVERY_FAILED_KEEP_SNAPSHOTS
   echo MU1367_BASE_LAYER_RESTORED_FULL_REBOOT_REQUIRED
  fi;;
 restore-oem)
  if [ -n "$ACTIVE" ];then retire_wireless
  else
   OEM=$CUSTOM/carplay_mu1367_oem_reset
   if regular "$APP/carplay-mu1367-oem-reset/STATE" && [ "$(cat "$APP/carplay-mu1367-oem-reset/STATE")" = complete ] &&
      /bin/ksh "$OEM/control.sh" verify "$OEM";then
    echo MU1367_OEM_RESET_ALREADY_COMPLETE_REBOOT_IF_NEEDED
    exit 0
   fi
   mark_reboot
   retain_completed_oem
   /bin/ksh "$BASE/actions.sh" restore-oem "$BASE" || fail OEM_RESTORE_FAILED_REPEAT_AFTER_REBOOT
   echo MU1367_RELEASE_COMPLETE_OEM_RESTORE_FULL_REBOOT_REQUIRED
  fi;;
esac
