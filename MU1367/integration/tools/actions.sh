#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
CUSTOM=${P%/*}
LOCK=$M/ramdisk/.carplay-guidance-install-lock
# Present only while the install action runs; the Reboot unit action refuses
# while it exists. EXIT removes it (a power cycle clears the RAM disk).
RUNNING=$M/ramdisk/.cpmap-install-running
RUN_OWN=no
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "MU1367_GUIDANCE_V3_SUITE_FAIL=$1";exit 1; }
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK" || :
 fi
}
running_done(){ if [ "$RUN_OWN" = yes ];then rm -f "$RUNNING" || :;fi; }
trap 'cleanup;running_done' EXIT
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
"$P/verify" "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_K4525_OR_P4521_MU1367_REQUIRED
# The two supported trains share this exact JXE. Report the actual train when
# RCC exposes it; a missing RCC file keeps the exact-hash MMX recovery path.
FW_TYPE=K4525_OR_P4521_HASH_MATCH
TRAIN_FILE=$M/net/rcc/dev/shmem/version.txt
if regular "$TRAIN_FILE" && parents "$TRAIN_FILE";then
 TRAIN=$(awk -F ' = ' '$1 == "Current train" {gsub(/["\047\r]/,"",$2);print $2}' "$TRAIN_FILE")
 case "$TRAIN" in
  MHI2_ER_VWG13_P4521|MHI2_ER_VWG13_P4521_*) FW_TYPE=P4521_EXPERIMENTAL;;
  MHI2_ER_VWG13_K4525|MHI2_ER_VWG13_K4525_*) FW_TYPE=K4525;;
  "") :;;
  *) fail UNSUPPORTED_FIRMWARE_TRAIN;;
 esac
fi
echo "MU1367_FIRMWARE_TYPE=$FW_TYPE"
case "$ACTION" in
 lane-status)
  if regular "$M/ramdisk/carplay-route-guidance/lane-evidence.txt";then cat "$M/ramdisk/carplay-route-guidance/lane-evidence.txt";else echo MU1367_NO_LANE_EVIDENCE_YET;fi
  exit 0;;
 status)
  /bin/ksh "$CUSTOM/carplay_mu1367_map_only/actions.sh" status "$CUSTOM/carplay_mu1367_map_only" || exit 1
  if regular "$M/ramdisk/carplay-route-guidance/reader-failure-first.txt";then cat "$M/ramdisk/carplay-route-guidance/reader-failure-first.txt";fi
  if regular "$M/ramdisk/carplay-route-guidance/guidance-evidence.txt";then cat "$M/ramdisk/carplay-route-guidance/guidance-evidence.txt";fi
  for R in "$APP/carplay-mu1367-guidance-v3" "$APP/carplay-mu1367-turn-cards" "$APP/carplay-mu1367-android-auto";do
   echo "LAYER=${R##*/}"
   for F in STATE VERSION;do regular "$R/$F" && cat "$R/$F";done
  done
  /bin/ksh "$CUSTOM/carplay_mu1367_android_auto/control.sh" status "$CUSTOM/carplay_mu1367_android_auto" || :
  exit 0;;
 check-tools|reset-settings|restore-oem)
  # The OEM reset predates default compressed artwork: switch it off first so no stale layer stays behind.
  # The OEM reset predates Android Auto too: put the factory gal back first.
  if [ "$ACTION" = restore-oem ] && [ "$(cat "$APP/carplay-mu1367-android-auto/STATE" 2>/dev/null)" = installed ];then
   /bin/ksh "$APP/carplay-mu1367-android-auto/control.sh" uninstall "$APP/carplay-mu1367-android-auto" || fail ANDROID_AUTO_REMOVAL_FAILED_RUN_RECOVER
  fi
  if [ "$ACTION" = restore-oem ] && [ "$(cat "$APP/carplay-mu1367-artwork-png/STATE" 2>/dev/null)" = installed ];then
   /bin/ksh "$APP/carplay-mu1367-artwork-png/control.sh" uninstall || fail ARTWORK_PNG_REMOVAL_FAILED_RUN_RECOVER
  fi
  exec /bin/ksh "$CUSTOM/carplay_mu1367_map_only/actions.sh" "$ACTION" "$CUSTOM/carplay_mu1367_map_only";;
 install|uninstall|recover|enable-cards|disable-cards|recover-cards|aa-disable|aa-enable) ;;
 *) fail INVALID_ACTION;;
esac
absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST
if [ "$ACTION" = install ];then absent "$M/ramdisk/.cpmap-release-migration-reboot" || fail FULL_REBOOT_REQUIRED_BEFORE_RELEASE_INSTALL;fi
parents "$LOCK" && absent "$LOCK" || fail INSTALLER_LOCKED_REBOOT_DISCONNECTED
if [ "$ACTION" = install ];then
 parents "$RUNNING" && absent "$RUNNING" || fail INSTALL_ALREADY_RUNNING_WAIT_OR_REBOOT
 : > "$RUNNING" || fail RAMDISK_MARKER
 RUN_OWN=yes
fi
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
 # Current experimental main snapshots also own the reader. Validate it
 # before archiving a removed session, including a missing backup/digest.
 case "$(cat "$R/VERSION")" in
 @READER_VERSIONS@) KEYS="$KEYS reader";;
 esac
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
if [ "$ACTION" = install ] && regular "$APP/carplay-mu1367-settings/VERSION";then
 case "$(cat "$APP/carplay-mu1367-settings/VERSION")" in
  MU1367-P4521-settings-e59e7a883ca0)
   fail P4521_EXPERIMENTAL_BASE_USE_RECOVERY_RESTORE_OEM_REBOOT_THEN_INSTALL;;
 esac
fi
if [ "$ACTION" = install ] && [ -d "$APP/carplay-mu1367-reader-recovery" ];then
 [ "$(cat "$APP/carplay-mu1367-reader-recovery/STATE" 2>/dev/null)" = removed ] || fail RESTORE_STANDALONE_READER_TEST_FIRST
fi
CARDS=$APP/carplay-mu1367-turn-cards
MAIN=$APP/carplay-mu1367-guidance-v3
PNG=$APP/carplay-mu1367-artwork-png
# Since v1.4.6 compressed artwork is installed by default. Removal and recovery take it out first,
# from its saved controller; a user who disabled it keeps it disabled (state removed).
png_remove(){
 [ -d "$PNG" ] || return 0
 parents "$PNG/control.sh" && regular "$PNG/control.sh" || fail NO_SAVED_ARTWORK_PNG_CONTROLLER
 case "$(cat "$PNG/STATE" 2>/dev/null)" in
  removed) return 0;;
  installed) /bin/ksh "$PNG/control.sh" "$1" || fail ARTWORK_PNG_REMOVAL_FAILED_RUN_RECOVER;;
  *) /bin/ksh "$PNG/control.sh" recover || fail ARTWORK_PNG_RECOVERY_FAILED;;
 esac
}
AAL=$APP/carplay-mu1367-android-auto
# The Android Auto layer depends on the main layer: it is removed first, from its saved controller.
aa_remove(){
 [ -d "$AAL" ] || return 0
 parents "$AAL/control.sh" && regular "$AAL/control.sh" || fail NO_SAVED_ANDROID_AUTO_CONTROLLER
 case "$(cat "$AAL/STATE" 2>/dev/null)" in
  removed) return 0;;
  installed) /bin/ksh "$AAL/control.sh" uninstall "$AAL" || fail ANDROID_AUTO_REMOVAL_FAILED_RUN_RECOVER;;
  *) /bin/ksh "$AAL/control.sh" recover "$AAL" || fail ANDROID_AUTO_RECOVERY_FAILED;;
 esac
}
case "$ACTION" in
 aa-disable|aa-enable)
  parents "$AAL/control.sh" && regular "$AAL/control.sh" || fail ANDROID_AUTO_NOT_INSTALLED
  exec /bin/ksh "$AAL/control.sh" "${ACTION#aa-}" "$AAL";;
 uninstall|recover)
  aa_remove
  png_remove uninstall
  if ! regular "$MAIN/control.sh" && [ -d "$AAL" ];then echo MU1367_NO_MAIN_LAYER_ANDROID_AUTO_HANDLED;exit 0;fi
  regular "$MAIN/control.sh" || fail NO_SAVED_V3_CONTROLLER
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
 exec /bin/ksh "$CUSTOM/carplay_mu1367_v3_turn_cards/$VARIANT/control.sh" install "$CUSTOM/carplay_mu1367_v3_turn_cards/$VARIANT"
fi
if [ -d "$CARDS" ];then
 regular "$CARDS/STATE" && [ "$(cat "$CARDS/STATE")" = removed ] || fail REMOVE_OR_RECOVER_TURN_CARD_TUNING_FIRST
fi
retain_removed "$MAIN"
# Plan the steps from the same saved layer states the nested installers use:
# video, five base layers, refinements and map-only when the base is not yet
# installed, then this release's guidance layer.
BASE=no
if ! regular "$APP/carplay-mu1367-map-only/STATE" || [ "$(cat "$APP/carplay-mu1367-map-only/STATE")" != installed ];then BASE=yes;fi
# Main release layer and the Android Auto layer (v1.5.0-e).
TOTAL=2
# Compressed artwork (default since v1.4.6) unless the user disabled it.
PNG_STEP=yes
[ "$(cat "$PNG/STATE" 2>/dev/null)" = removed ] && PNG_STEP=no
[ "$PNG_STEP" = yes ] && TOTAL=$((TOTAL+1))
if [ "$BASE" = yes ];then
 TOTAL=$((TOTAL+2))
 [ -d "$APP/carplaymaps" ] || TOTAL=$((TOTAL+1))
 for L in carplay-mu1367 carplay-mu1367-settings carplay-mu1367-lanes carplay-mu1367-wireless carplay-mu1367-artwork;do
  [ -d "$APP/$L" ] || TOTAL=$((TOTAL+1))
 done
fi
echo "MU1367_INSTALL_STEPS=$TOTAL (do not reboot until the final message)"
install_steps(){
 if [ "$BASE" = yes ];then
  /bin/ksh "$CUSTOM/carplay_mu1367_map_only/actions.sh" install "$CUSTOM/carplay_mu1367_map_only" || { echo MU1367_GUIDANCE_V3_SUITE_FAIL=BASE_INSTALL_FAILED_KEEP_SNAPSHOTS;return 1; }
 fi
 /bin/ksh "$P/$VARIANT/control.sh" install "$P/$VARIANT" || { echo MU1367_GUIDANCE_V3_SUITE_FAIL=MAP_ONLY_INSTALL_FAILED_USE_RECOVERY;return 1; }
 if [ "$PNG_STEP" = yes ];then
  # A layer left "installed" by an OEM reset run without the menu no longer has the compressed helper in place:
  # keep its record as a stale archive and install afresh (its snapshot is the original helper, kept).
  if [ "$(cat "$PNG/STATE" 2>/dev/null)" = installed ] && ! "$P/verify" "$APP/carplay-mu1367-artwork/artwork-fetch" "$("$P/verify" "$CUSTOM/carplay_mu1367_artwork_png/artwork-fetch")";then
   absent "$PNG.stale-$$" && mount -uw /mnt/app && mv "$PNG" "$PNG.stale-$$" && sync || { echo MU1367_GUIDANCE_V3_SUITE_FAIL=STALE_ARTWORK_PNG_ARCHIVE_FAILED;return 1; }
   echo "MU1367_STALE_ARTWORK_PNG_RETAINED=$PNG.stale-$$"
  fi
  /bin/ksh "$CUSTOM/carplay_mu1367_artwork_png/control.sh" install "$CUSTOM/carplay_mu1367_artwork_png" || { echo MU1367_GUIDANCE_V3_SUITE_FAIL=ARTWORK_PNG_INSTALL_FAILED_CARPLAY_INSTALLED_USE_RECOVERY;return 1; }
 else echo MU1367_COMPRESSED_ARTWORK_KEPT_DISABLED;fi
 /bin/ksh "$CUSTOM/carplay_mu1367_android_auto/control.sh" install "$CUSTOM/carplay_mu1367_android_auto" || { echo MU1367_GUIDANCE_V3_SUITE_FAIL=ANDROID_AUTO_INSTALL_FAILED_CARPLAY_INSTALLED_USE_RECOVERY;return 1; }
}
# Nested layer installers each report a reboot as if run alone. Number their
# completions instead and request one reboot at the end. Shell builtins only;
# the pipeline status is the final loop's, which returns the steps' status.
progress(){
 N=0;R=1
 while IFS= read -r L;do
  case "$L" in
   __CPMAP_STEPS_RC=*) R=${L#__CPMAP_STEPS_RC=};;
   "A full unit reboot is required."|MU1367_*SUITE_INSTALLED_FULL_REBOOT_REQUIRED) :;;
   CPMAP_INSTALL_OK) N=$((N+1));echo "[$N/$TOTAL] MU1367_VIDEO_INSTALLED";;
   MU1367_INSTALLED_REBOOT_REQUIRED) N=$((N+1));echo "[$N/$TOTAL] MU1367_NATIVE_BASE_INSTALLED";;
   MU1367_ALREADY_INSTALLED) N=$((N+1));echo "[$N/$TOTAL] MU1367_NATIVE_BASE_ALREADY_INSTALLED";;
   MU1367_*_INSTALLED_REBOOT_REQUIRED) N=$((N+1));echo "[$N/$TOTAL] ${L%_REBOOT_REQUIRED}";;
   MU1367_*_ALREADY_INSTALLED) N=$((N+1));echo "[$N/$TOTAL] $L";;
   *_REBOOT_REQUIRED) echo "${L%_REBOOT_REQUIRED}";;
   *) echo "$L";;
  esac
 done
 [ "$N" = "$TOTAL" ] || echo "MU1367_STEP_COUNT=$N/$TOTAL"
 return "$R"
}
{ install_steps;echo "__CPMAP_STEPS_RC=$?"; } 2>&1 | progress || exit 1
echo "MU1367_INSTALL_COMPLETE=$TOTAL/$TOTAL"
echo MU1367_GUIDANCE_V3_SUITE_INSTALLED_FULL_REBOOT_REQUIRED
echo "NEXT: disconnect phone/adapter, then select Reboot unit in this menu"
