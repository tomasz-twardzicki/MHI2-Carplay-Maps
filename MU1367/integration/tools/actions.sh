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
  MHI2_ER_VWG13_P4521|MHI2_ER_VWG13_P4521_*) FW_TYPE=P4521;;
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
 snapshots|snapshot-next|snapshot-remove|snapshots-remove-all) ;;
 stream-show|stream-fps-up5|stream-fps-down5|stream-fps-up1|stream-fps-down1|stream-idr-up|stream-idr-down|stream-reset) ;;
 *) fail INVALID_ACTION;;
esac
# v1.5.4: stream test. It writes only stream-test.conf next to the MU UI settings, so it runs
# without the installer lock.
case "$ACTION" in stream-*)
 PREF=$M/mnt/icab/persistent/cpmap-ui;TEST=$PREF/stream-test.conf
 HLOG=$M/ramdisk/carplay_altscreen_handshake/handshake.log
 # The last N lines containing any of the |-separated plain strings (empty: every line). The factory has no tail and its
 # awk aborts on a regular expression passed in a variable, so this matches with index().
 last(){ awk -v n="$1" -v pats="$2" 'BEGIN{n=n+0;c=0;k=0;if(pats!="")k=split(pats,p,"|")} {m=(k==0);for(j=1;j<=k&&!m;j++)if(index($0,p[j])>0)m=1;if(m){a[c%n]=$0;c++}} END{s=0;if(c>n)s=c-n;for(i=s;i<c;i++)print a[i%n]}' "$3"; }
 # MU UI stream values 0..6 -> fps (the core's table); no or unreadable display.state: 40 fps default.
 # Sets FPS without a nested command substitution: the factory ksh aborts on $(f) when f runs case "$(...)".
 ui_fps(){ U=;regular "$PREF/display.state" && U=$(awk -F= '$1=="stream"{print $2}' "$PREF/display.state");case "$U" in 0|2) FPS=30;;4) FPS=25;;*) FPS=40;;esac; }
 load(){
  ui_fps;IDR=5;SRC=MU_UI
  if regular "$TEST";then
   F=$(awk -F= 'NR==1&&$1=="fps"{print $2}' "$TEST");I=$(awk -F= 'NR==2&&$1=="idr"{print $2}' "$TEST");SRC=INVALID_TEST_FILE_IGNORED
   case "$F" in ""|*[!0-9]*) F=0;;esac;case "$I" in ""|*[!0-9]*) I=0;;esac
   if [ "$F" -ge 20 ] && [ "$F" -le 40 ] && [ "$I" -ge 5 ] && [ "$I" -le 15 ];then FPS=$F;IDR=$I;SRC=TOOLBOX_TEST;fi
  fi
 }
 show(){
  echo "MU1367_STREAM_SOURCE=$SRC";echo "MU1367_STREAM_FPS=$FPS";echo "MU1367_STREAM_KEYFRAME_EVERY_FRAMES=$IDR"
  echo "Applies on the next phone connection: disconnect, wait 5 s, reconnect."
  if regular "$HLOG";then echo "Last stream asked of the phone:";last 2 'stream-settings|stream-idr-interval' "$HLOG";fi
 }
 save(){
  parents "$PREF" && [ ! -L "$PREF" ] || fail STREAM_TEST_SETTINGS_PARENT_UNSAFE
  [ -d "$PREF" ] || mkdir "$PREF" || fail STREAM_TEST_DIRECTORY
  { echo "fps=$1";echo "idr=$2"; } > "$TEST.new-$$" && mv "$TEST.new-$$" "$TEST" || { rm -f "$TEST.new-$$";fail STREAM_TEST_WRITE; }
  sync;load
  [ "$SRC" = TOOLBOX_TEST ] || fail STREAM_TEST_READBACK
 }
 load
 case "$ACTION" in
  stream-show) show;exit 0;;
  stream-reset) rm -f "$TEST";sync;load;echo MU1367_STREAM_TEST_OFF;show;exit 0;;
  stream-fps-up5) N=$((FPS+5));[ "$N" -le 40 ] || N=40;save "$N" "$IDR";;
  stream-fps-down5) N=$((FPS-5));[ "$N" -ge 20 ] || N=20;save "$N" "$IDR";;
  stream-fps-up1) N=$((FPS+1));[ "$N" -le 40 ] || N=40;save "$N" "$IDR";;
  stream-fps-down1) N=$((FPS-1));[ "$N" -ge 20 ] || N=20;save "$N" "$IDR";;
  stream-idr-up) N=$((IDR+1));[ "$N" -le 15 ] || N=15;save "$FPS" "$N";;
  stream-idr-down) N=$((IDR-1));[ "$N" -ge 5 ] || N=5;save "$FPS" "$N";;
 esac
 echo MU1367_STREAM_TEST_SAVED;show;exit 0;;
esac
# v1.5.2: saved snapshots of earlier installations and rollbacks. Only directories that no
# controller reads again are listed: removed and stale layer sessions, earlier OEM resets, a
# completed OEM reset and archived MU UI settings. Live layers keep their own snapshots and are
# never listed. The selection lives on the RAM disk, so a reboot clears it.
SEL=$M/ramdisk/.cpmap-snapshot-selected
RESET=$APP/carplay-mu1367-oem-reset
# parents() uses D: the snapshot code keeps its own names.
snap_ok(){ parents "$1" && [ -d "$1" ] && [ ! -L "$1" ]; }
snap_suffix(){ case "$1" in ''|*[!0-9]*) return 1;;esac; }
snap_all(){
 for SD in "$APP"/carplay-mu1367*.removed-* "$APP"/carplay-mu1367*.stale-* "$APP"/carplay-mu1367-oem-reset.completed-*;do
  snap_ok "$SD" || continue
  N=${SD##*/}
  case "$N" in
   *.removed-*) snap_suffix "${N##*.removed-}" || continue;;
   *.stale-*) snap_suffix "${N##*.stale-}" || continue;;
   *) snap_suffix "${N##*.completed-}" || continue;;
  esac
  echo "$SD"
 done
 # A completed OEM reset is a rollback record only; an unfinished one is still needed.
 if snap_ok "$RESET" && regular "$RESET/STATE" && [ "$(cat "$RESET/STATE")" = complete ];then echo "$RESET";fi
 for SD in "$M/mnt/icab/persistent"/cpmap-ui.saved-*;do
  snap_ok "$SD" && snap_suffix "${SD##*.saved-}" && echo "$SD"
 done
}
snap_kind(){
 case "$1" in
  "$RESET") echo 'completed OEM reset (pre-reset files + archived layers)';;
  *.completed-*) echo 'earlier OEM reset';;
  *-android-auto.removed-*) echo 'removed Android Auto layer';;
  *-turn-cards.removed-*) echo 'removed turn-card tuning';;
  *.removed-*) echo 'removed layer from an earlier installation';;
  *.stale-*) echo 'stale compressed-artwork record';;
  *cpmap-ui.saved-*) echo 'MU UI settings saved by a settings reset';;
 esac
}
snap_kb(){ ls -alR "$1" 2>/dev/null | awk '/^-/ {s+=$5} END {printf "%d\n",(s+1023)/1024}'; }
snap_print(){
 N=0;T=0
 for SD in $(snap_all);do
  N=$((N+1));K=$(snap_kb "$SD");T=$((T+K))
  MARK=' ';[ "$SD" = "$(cat "$SEL" 2>/dev/null)" ] && MARK='>'
  echo "${MARK}[$N] ${SD##*/} ${K} KB - $(snap_kind "$SD")"
 done
 echo "MU1367_SAVED_SNAPSHOTS=$N TOTAL_KB=$T"
 if command -v df >/dev/null 2>&1;then df -k "$APP" 2>/dev/null || :;fi
}
snap_lock(){
 parents "$LOCK" && absent "$LOCK" || fail INSTALLER_LOCKED_REBOOT_DISCONNECTED
 absent "$RUNNING" || fail INSTALL_RUNNING_WAIT_OR_REBOOT
 mkdir "$LOCK" || fail INSTALLER_LOCKED
 OWN=yes
 mount -uw /mnt/app || fail APP_REMOUNT
}
snap_remove(){
 SD=$1
 snap_ok "$SD" || fail SNAPSHOT_UNSAFE
 if [ "$SD" = "$RESET" ];then
  # Rename first: an interrupted removal must not leave a half-deleted reset under its live name.
  absent "$RESET.completed-$$" || fail SNAPSHOT_ARCHIVE_EXISTS
  mv "$RESET" "$RESET.completed-$$" || fail SNAPSHOT_RENAME_FAILED
  SD=$RESET.completed-$$
 fi
 rm -rf "$SD";sync
 absent "$SD" || fail "SNAPSHOT_REMOVE_INCOMPLETE_RUN_AGAIN=${SD##*/}"
 echo "MU1367_SNAPSHOT_REMOVED=${1##*/}"
}
case "$ACTION" in
 snapshots)
  snap_print
  echo MU1367_SNAPSHOTS_LISTED_NO_FILES_CHANGED
  exit 0;;
 snapshot-next)
  NEXT='';FIRST='';TAKE=no;CUR=$(cat "$SEL" 2>/dev/null)
  for SD in $(snap_all);do
   [ -z "$FIRST" ] && FIRST=$SD
   if [ "$TAKE" = yes ] && [ -z "$NEXT" ];then NEXT=$SD;fi
   [ "$SD" = "$CUR" ] && TAKE=yes
  done
  [ -z "$NEXT" ] && NEXT=$FIRST
  if [ -z "$NEXT" ];then rm -f "$SEL";echo MU1367_SAVED_SNAPSHOTS=0;exit 0;fi
  echo "$NEXT" > "$SEL" || fail SELECTION_WRITE
  snap_print
  echo "MU1367_SNAPSHOT_SELECTED=${NEXT##*/}"
  echo "NEXT: Remove selected snapshot, or Select next snapshot again"
  exit 0;;
 snapshot-remove)
  regular "$SEL" || { snap_print;fail SELECT_A_SNAPSHOT_FIRST; }
  CUR=$(cat "$SEL");FOUND=no
  for SD in $(snap_all);do [ "$SD" = "$CUR" ] && FOUND=yes;done
  [ "$FOUND" = yes ] || { rm -f "$SEL";snap_print;fail SELECTED_SNAPSHOT_GONE_SELECT_AGAIN; }
  snap_lock
  rm -f "$SEL"
  snap_remove "$CUR"
  snap_print
  exit 0;;
 snapshots-remove-all)
  LIST=$(snap_all)
  if [ -z "$LIST" ];then rm -f "$SEL";echo MU1367_SAVED_SNAPSHOTS=0;exit 0;fi
  snap_lock
  rm -f "$SEL"
  for SD in $LIST;do snap_remove "$SD";done
  snap_print
  exit 0;;
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
 # v1.5.1-e main snapshots also own the CarPlay video bridge.
 case "$(cat "$R/VERSION")" in
 @BRIDGE_VERSIONS@) KEYS="$KEYS bridge";;
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
