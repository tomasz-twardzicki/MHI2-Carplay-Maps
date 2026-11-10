# Keep the tested reboot boundary between retiring a local revision and release installation.
if [ -d "$MAIN" ] && regular "$MAIN/STATE" && [ "$(cat "$MAIN/STATE")" = installed ];then
 . "$P/release-versions.sh" || fail RELEASE_IDENTITY_SCRIPT
 if [ "$RELEASE_CURRENT" = no ];then
  IDENTITY=$MAIN/control.sh
  OLD_TUNING=no
  if [ -d "$CARDS" ];then
   regular "$CARDS/STATE" || fail TUNING_STATE_UNKNOWN
   case "$(cat "$CARDS/STATE")" in
    installed)
     legacy_check "$CARDS" "$CARDS/control.sh" || fail UNKNOWN_OR_DAMAGED_LEGACY_TUNING
     IDENTITY=$CARDS/backup/parent
     regular "$CARDS/parent.sha256" && "$P/verify" "$MAIN/control.sh" "$(cat "$CARDS/parent.sha256")" || fail LEGACY_PARENT_GUARD_CHANGED
     OLD_TUNING=yes;;
    removed) :;;
    *) fail RECOVER_INTERRUPTED_TUNING_FIRST;;
   esac
  fi
  legacy_check "$MAIN" "$IDENTITY" || fail UNKNOWN_OR_DAMAGED_LEGACY_REVISION
  # A later release with the Android Auto layer installed retires it before its main layer.
  if [ -d "$APP/carplay-mu1367-android-auto" ] && [ "$(cat "$APP/carplay-mu1367-android-auto/STATE" 2>/dev/null)" != removed ];then
   /bin/ksh "$APP/carplay-mu1367-android-auto/control.sh" uninstall "$APP/carplay-mu1367-android-auto" || fail LEGACY_ANDROID_AUTO_REMOVAL_FAILED_USE_RECOVERY
  fi
  if [ "$OLD_TUNING" = yes ];then
   /bin/ksh "$CARDS/control.sh" uninstall || fail LEGACY_TUNING_REMOVAL_FAILED_USE_RECOVERY
  fi
  /bin/ksh "$MAIN/control.sh" uninstall || fail LEGACY_REMOVAL_FAILED_USE_SAVED_RECOVER
  : > "$M/ramdisk/.cpmap-release-migration-reboot" || fail MIGRATION_REBOOT_MARKER
  echo "MU1367_STAGE_1_OF_2_COMPLETE: previous revision removed, snapshots kept"
  echo MU1367_RELEASE_MIGRATION_BASE_RESTORED_FULL_REBOOT_THEN_RUN_INSTALL_AGAIN
  echo "NEXT: disconnect phone/adapter, select Reboot unit, then run Install again (stage 2 of 2)"
  exit 0
 fi
fi
