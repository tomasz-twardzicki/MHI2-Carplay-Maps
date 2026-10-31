#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
CUSTOM=${P%/*}
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "MU1367_MAP_ONLY_SUITE_FAIL=$1";exit 1; }
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK" || :
 fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED_KEEP_SNAPSHOTS' HUP INT TERM
parents(){
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
for C in cat cp mv rm mkdir chmod sync mount ls awk grep basename touch;do
 command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C"
done
regular "$P/verify" && parents "$P/verify" || fail VERIFIER_MISSING_OR_UNSAFE
"$P/verify" "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_K4525_MU1367_REQUIRED
case "$ACTION" in
 lane-status)
  if regular "$M/ramdisk/carplay-route-guidance/lane-evidence.txt";then cat "$M/ramdisk/carplay-route-guidance/lane-evidence.txt";else echo MU1367_NO_LANE_EVIDENCE_YET;fi
  exit 0;;
 status)
  /bin/ksh "$CUSTOM/carplay_mu1367_refinements/actions.sh" status "$CUSTOM/carplay_mu1367_refinements" || exit 1
  for R in "$APP/carplay-mu1367-map-only" "$APP/carplay-mu1367-turn-cards";do
   echo "LAYER=${R##*/}"
   for F in STATE VERSION;do regular "$R/$F" && cat "$R/$F";done
  done
  exit 0;;
 check-tools|reset-settings|restore-oem)
  exec /bin/ksh "$CUSTOM/carplay_mu1367_refinements/actions.sh" "$ACTION" "$CUSTOM/carplay_mu1367_refinements";;
 install|uninstall|recover|enable-cards|disable-cards|recover-cards) ;;
 *) fail INVALID_ACTION;;
esac
absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST
parents "$LOCK" && absent "$LOCK" || fail INSTALLER_LOCKED_REBOOT_DISCONNECTED
. "$P/payload-check.sh" || fail SD_PAYLOAD_HASH

# Removed sessions can be reused without deleting their first snapshots.
# Verify the complete restored snapshot before archiving; incomplete sessions
# always go through recover instead. No archive is overwritten.
retain_removed(){
 R=$1
 parents "$R" && [ ! -L "$R" ] || fail UNSAFE_LAYER
 [ -d "$R" ] || return 0
 regular "$R/STATE" || fail LAYER_STATE_MISSING
 [ "$(cat "$R/STATE")" = removed ] || return 0
 regular "$R/BACKUPS_READY" && [ -d "$R/backup" ] && [ ! -L "$R/backup" ] || fail REMOVED_SNAPSHOT_INCOMPLETE
 # Every generated snapshot has these keys; card tuning leaves guidance alone.
 case "$R" in *turn-cards) KEYS='core menu parent';;*) KEYS='core guidance menu parent';;esac
 for K in $KEYS;do
  regular "$R/backup/$K" && regular "$R/backup/$K.sha256" || fail SNAPSHOT_HASH_MISSING
  "$P/verify" "$R/backup/$K" "$(cat "$R/backup/$K.sha256")" || fail REMOVED_SNAPSHOT_DAMAGED
 done
 # Original controllers contain exact before hashes; the runtime is separately
 # checked by the next installer. Archive only after full snapshot validation.
 BACK=$R.removed-$$
 absent "$BACK" || fail RETAINED_SESSION_EXISTS
 mkdir "$LOCK" || fail INSTALLER_LOCKED
 OWN=yes
 mount -uw /mnt/app || fail APP_REMOUNT
 mv "$R" "$BACK" && sync || fail RETAIN_REMOVED_SESSION_FAILED
 echo "MU1367_RETAINED_SESSION=$BACK"
 cleanup
 [ ! -e "$LOCK" ] || fail LOCK_CLEANUP_FAILED
 OWN=no
}
CARDS=$APP/carplay-mu1367-turn-cards
MAIN=$APP/carplay-mu1367-map-only
case "$ACTION" in
 uninstall|recover)
  regular "$MAIN/control.sh" || fail NO_SAVED_MAP_ONLY_CONTROLLER
  exec /bin/ksh "$MAIN/control.sh" "$ACTION";;
 disable-cards|recover-cards)
  regular "$CARDS/control.sh" || fail NO_SAVED_TUNING_CONTROLLER
  case "$ACTION" in disable-cards) CMD=uninstall;;*) CMD=recover;;esac
  exec /bin/ksh "$CARDS/control.sh" "$CMD";;
esac
VARIANT=6
if [ -d "$APP/carplay-mu1367-card-scene" ];then
 regular "$APP/carplay-mu1367-card-scene/STATE" || fail CARD_SCENE_UNKNOWN
 case "$(cat "$APP/carplay-mu1367-card-scene/STATE")" in installed) VARIANT=7;;removed) :;;*) fail CARD_SCENE_INTERRUPTED;;esac
fi
if [ -d "$APP/carplay-mu1367-road-name" ];then
 regular "$APP/carplay-mu1367-road-name/STATE" || fail ROAD_NAME_UNKNOWN
 case "$(cat "$APP/carplay-mu1367-road-name/STATE")" in installed) VARIANT=$VARIANT-road;;removed) :;;*) fail ROAD_NAME_INTERRUPTED;;esac
fi
if [ "$ACTION" = enable-cards ];then
 retain_removed "$CARDS"
 exec /bin/ksh "$CUSTOM/carplay_mu1367_turn_cards/$VARIANT/control.sh" install "$CUSTOM/carplay_mu1367_turn_cards/$VARIANT"
fi
if [ -d "$CARDS" ];then
 regular "$CARDS/STATE" && [ "$(cat "$CARDS/STATE")" = removed ] || fail REMOVE_OR_RECOVER_TURN_CARD_TUNING_FIRST
fi
retain_removed "$MAIN"
if [ ! -d "$MAIN" ];then
 /bin/ksh "$CUSTOM/carplay_mu1367_refinements/actions.sh" install "$CUSTOM/carplay_mu1367_refinements" || fail BASE_INSTALL_FAILED_KEEP_SNAPSHOTS
fi
/bin/ksh "$P/$VARIANT/control.sh" install "$P/$VARIANT" || fail MAP_ONLY_INSTALL_FAILED_USE_RECOVERY
echo MU1367_MAP_ONLY_SUITE_INSTALLED_FULL_REBOOT_REQUIRED
