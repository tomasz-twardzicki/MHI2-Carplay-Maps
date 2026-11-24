#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Entire action runs on MMX; the GEM wrapper forwards from RCC if necessary.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "MU1367_SUITE_FAIL=$1";exit 1; }
parents(){
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK" || :
 fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED_KEEP_BACKUPS' HUP INT TERM
for C in cat cp mv rm mkdir chmod sync mount ls awk grep basename touch;do
 command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C"
done
regular "$P/verify" && parents "$P/verify" || fail VERIFIER_MISSING_OR_UNSAFE
"$P/verify" "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_K4525_MU1367_REQUIRED
case "$ACTION" in
 check-tools) echo MU1367_SUITE_REQUIRED_TOOLS_AVAILABLE_NO_FILES_CHANGED;exit 0;;
 status)
  for N in carplay-mu1367 carplay-mu1367-settings carplay-mu1367-lanes carplay-mu1367-wireless carplay-mu1367-artwork carplay-mu1367-card-scene carplay-mu1367-road-name carplay-mu1367-refinements;do
   echo "LAYER=$N";for F in STATE VERSION;do regular "$APP/$N/$F" && cat "$APP/$N/$F";done
  done
  for F in "$M/ramdisk/carplay-route-guidance/adapter-status.txt" "$M/ramdisk/cpmap-card-status.txt";do regular "$F" && cat "$F";done
  exit 0;;
 install|reset-settings|restore-oem|uninstall|recover) ;;
 *) fail INVALID_ACTION;;
esac
absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST
parents "$LOCK" && absent "$LOCK" || fail INSTALLER_LOCKED_REBOOT_DISCONNECTED
# Check the complete selected SD payload before any persistent write.
echo MU1367_SUITE_VERIFYING_SD_PAYLOAD
. "$P/payload-check.sh" || fail SD_PAYLOAD_HASH
if [ "$ACTION" = reset-settings ];then
 PREF=$M/mnt/icab/persistent/cpmap-ui
 parents "$PREF" && [ ! -L "$PREF" ] || fail SETTINGS_PARENT_UNSAFE
 absent "$PREF" || [ -d "$PREF" ] || fail SETTINGS_NOT_DIRECTORY
 BACK=$PREF.saved-$$
 absent "$BACK" || fail SETTINGS_ARCHIVE_ALREADY_EXISTS
 mkdir "$LOCK" || fail LOCK_FAILED;OWN=yes
 PROBE=${PREF%/*}/.cpmap-ui-reset-write-$$
 absent "$PROBE" || fail SETTINGS_WRITE_PROBE_EXISTS
 (umask 077;set -C;: > "$PROBE") || fail SETTINGS_FILESYSTEM_READONLY_NO_SETTINGS_CHANGED
 rm "$PROBE" || fail SETTINGS_WRITE_PROBE_REMOVE
 if [ -d "$PREF" ];then mv "$PREF" "$BACK" || fail SETTINGS_ARCHIVE_FAILED;echo "MU1367_SETTINGS_ARCHIVE=$BACK";fi
 # A missing directory is the shared Java/native default state. Keeping it
 # absent also makes interruption after the rename a completed reset.
 sync
 echo MU1367_SETTINGS_RESET_FULL_REBOOT_REQUIRED_CARD_OFF_SELECT_30_5_AGAIN
 exit 0
fi
CUSTOM=${P%/*}
if [ "$ACTION" = restore-oem ];then
 SAVED=$APP/carplay-mu1367-oem-reset
 parents "$SAVED" && [ ! -L "$SAVED" ] || fail RESET_DIRECTORY_UNSAFE
 if [ -d "$SAVED" ] && regular "$SAVED/STATE" && [ "$(cat "$SAVED/STATE")" = complete ];then
  PREVIOUS=$SAVED.completed-$$
  absent "$PREVIOUS" || fail RESET_ARCHIVE_EXISTS
  mount -uw /mnt/app || fail APP_REMOUNT_FAILED_NO_FILES_CHANGED
  mv "$SAVED" "$PREVIOUS" || fail RETAIN_COMPLETED_RESET_FAILED
  sync;echo "MU1367_PREVIOUS_RESET_RETAINED=$PREVIOUS"
 fi
 exec /bin/ksh "$CUSTOM/carplay_mu1367_oem_reset/control.sh" restore "$CUSTOM/carplay_mu1367_oem_reset"
fi
if [ "$ACTION" = uninstall ] || [ "$ACTION" = recover ];then
 regular "$APP/carplay-mu1367-refinements/control.sh" || fail NO_SAVED_UPDATE_CONTROLLER
 exec /bin/ksh "$APP/carplay-mu1367-refinements/control.sh" "$ACTION"
fi
# All inherited controllers keep their own fingerprints, snapshots and lock.
# Validate the whole prefix before starting; skip only matching installed layers.
VARIANT=6
if [ -d "$APP/carplay-mu1367-card-scene" ];then
 regular "$APP/carplay-mu1367-card-scene/STATE" || fail CARD_SCENE_STATE_UNKNOWN
 case "$(cat "$APP/carplay-mu1367-card-scene/STATE")" in installed) VARIANT=7;;removed) :;;*) fail CARD_SCENE_INTERRUPTED_RECOVER_FIRST;;esac
fi
if [ -d "$APP/carplay-mu1367-road-name" ];then
 regular "$APP/carplay-mu1367-road-name/STATE" || fail ROAD_NAME_STATE_UNKNOWN
 case "$(cat "$APP/carplay-mu1367-road-name/STATE")" in installed) VARIANT=$VARIANT-road;;removed) :;;*) fail ROAD_NAME_INTERRUPTED_RECOVER_FIRST;;esac
fi
GAP=no
for N in carplay_mu1367 carplay_mu1367_settings carplay_mu1367_lanes carplay_mu1367_wireless carplay_mu1367_artwork;do
 case "$N" in carplay_mu1367) LIVE=carplay-mu1367;; *) LIVE=carplay-mu1367-${N#carplay_mu1367_};;esac
 R=$APP/$LIVE
 parents "$R" && [ ! -L "$R" ] || fail UNSAFE_LAYER
 if [ -d "$R" ];then
  regular "$R/STATE" && regular "$R/VERSION" || fail "INCOMPLETE_LAYER_$LIVE"
  [ "$(cat "$R/STATE")" = installed ] || fail "RESTORE_OEM_OR_RECOVER_LAYER_$LIVE"
  [ "$(cat "$R/VERSION")" = "$(cat "$CUSTOM/$N/VERSION")" ] || fail "UNKNOWN_LAYER_$LIVE"
  [ "$GAP" = no ] || fail LAYER_ORDER_INCONSISTENT_USE_OEM_RESET
 else GAP=yes;fi
done
parents "$APP/carplaymaps" && [ ! -L "$APP/carplaymaps" ] || fail VIDEO_DIRECTORY_UNSAFE
if [ -d "$APP/carplaymaps" ];then
 regular "$APP/carplaymaps/PROFILE" && [ "$(cat "$APP/carplaymaps/PROFILE")" = MU1367/791 ] || fail WRONG_VIDEO_PROFILE
else
 [ ! -d "$APP/carplay-mu1367" ] || fail VIDEO_MISSING_FROM_EXISTING_NATIVE_INSTALL
 MAPS=$CUSTOM/carplay_maps_vc/payload
 /bin/ksh "$MAPS/common/install-carplay-maps.sh" "$MAPS" MU1367 791 || fail VIDEO_INSTALL_FAILED_KEEP_BACKUPS
fi
for N in carplay_mu1367 carplay_mu1367_settings carplay_mu1367_lanes carplay_mu1367_wireless carplay_mu1367_artwork;do
 case "$N" in carplay_mu1367) LIVE=carplay-mu1367;; *) LIVE=carplay-mu1367-${N#carplay_mu1367_};;esac
 if [ ! -d "$APP/$LIVE" ];then
  /bin/ksh "$CUSTOM/$N/control.sh" install "$CUSTOM/$N" || fail "INSTALL_FAILED_$LIVE"
 fi
done
UPDATE=$P/$VARIANT
if [ -d "$APP/carplay-mu1367-refinements" ];then
 # Use the saved baseline choice for repeat validation; do not guess it anew.
 regular "$APP/carplay-mu1367-refinements/control.sh" || fail UPDATE_CONTROLLER_MISSING
 /bin/ksh "$APP/carplay-mu1367-refinements/control.sh" install "$UPDATE" || fail UPDATE_FAILED_USE_RECOVERY_SUBMENU
else
 /bin/ksh "$UPDATE/control.sh" install "$UPDATE" || fail UPDATE_FAILED_KEEP_BACKUPS
fi
echo MU1367_SUITE_INSTALLED_FULL_REBOOT_REQUIRED
