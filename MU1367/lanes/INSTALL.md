# MU1367 / 791 lane test: installation and rollback

Only exact MU1367 K4525 + 791 with the published v1.3.0 native/settings
layers is accepted. This optional update has not yet been tested on the car.

## Installation

1. Verify `CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip` using the adjacent
   `SHA256SUMS.txt`. Extract to a clean SD root. Refresh Toolbox menus **and
   scripts**, especially the full restore wrapper; retain the SD afterwards.
2. Park, maintain stable power and retain a working MMX shell. Save the recovery
   commands below outside the unit. Disconnect CarPlay and fully reboot first.
3. If v1.3.0 is already installed, keep steps 1–3 and their backups. Select
   **4. Add native lanes + default cards OFF (791)** only. Fresh installations
   must complete the original video, native/audio and settings steps first,
   following `MU1367_INSTALL.md` and `MU1367_SETTINGS_INSTALL.md` in the ZIP.
4. Expect `MU1367_LANES_INSTALLED_REBOOT_REQUIRED`. The snapshot, controller
   and verifier are saved in `/mnt/app/carplay-mu1367-lanes` before replacement.
   Unknown/modified originals are refused. Fully reboot with the phone absent;
   check OEM HMI and cluster before reconnecting.
5. In App-Connect **Virtual Cockpit settings**, select Card **OFF** once if an
   explicit ON preference already exists. Fresh preference stores default OFF.
   Keep your preferred **30 fps / IDR5**. Saved preferences are not reset.

Card ON/OFF remains the existing App-Connect selector. ON restores the
current configured card/layout; OFF leaves the map clear. The card is not
moved lower by this update. Compare space around the native lane/ETA bars
before leaving it ON. Reconnect after stream/layout changes; the card toggle
uses the existing live switching mechanism.

## Vehicle acceptance

Enable the OEM lane-guidance display setting. On a familiar route with
phone lane hints, compare the number/order of lanes, recommended versus best
lanes, left/right exits, straight branches and lane-bar disappearance after
the junction. Check Apple Maps, Google Maps and Waze separately; delivery may
depend on the app/route. The adapter does not invent lanes when none arrive.

Check route cancellation, rerouting, reconnect, OEM navigation priority and
no-navigation operation. Confirm native arrows/ETA, audio text, maps/mirror
and controls still work. Test Card OFF then ON/OFF and verify that the lane
bar and ETA remain readable. Finish with a 90-minute run and phone reconnect.
Record the exact ZIP hash, app and preferences with the diagnostics.

Use **Show native lane adapter status** or the MMX commands below. A positive
`lane_count` shows decoded content, not a guarantee of cluster visibility;
the phone show flag, freshness, ownership and OEM display setting also gate it.

## Remove lanes only, without SD

Disconnect the phone. Run on **MMX** (from RCC use `on -f mmx`):

```sh
/bin/ksh /mnt/app/carplay-mu1367-lanes/control.sh status
/bin/ksh /mnt/app/carplay-mu1367-lanes/control.sh uninstall
```

Expect `MU1367_LANES_SNAPSHOT_RESTORED_REBOOT_REQUIRED_PREFERENCES_RETAINED`.
Fully reboot. All three runtime files and both parent controllers are restored
from the pre-lane snapshot, returning to v1.3.0. Preferences and backups remain.
The matching Toolbox item is **Remove native lane layer (reboot)**.

## Interrupted installation or damaged HMI

Run the saved controller; it needs neither SD nor a working HMI:

```sh
/bin/ksh /mnt/app/carplay-mu1367-lanes/control.sh recover
```

All five backups must verify before any target is restored. Staged files are
discarded; the original complete snapshot is restored. Fully reboot. If the
shared lock remains after a power interruption, first confirm no installer
is running, then remove only the empty
`/ramdisk/.carplay-guidance-install-lock` directory and retry recovery.
Do not delete backups or force a lower layer's restoration. An incomplete
automatic rollback prints `MU1367_LANES_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER`.
If snapshot verification fails, retain the files and use the off-unit backup;
do not treat a partial restore as complete.

## Full return to OEM

The **Restore factory video + integration** action from this bundle removes
lanes, settings, native/audio integration, then base video, stopping on error.
Parent controllers refuse removal while the lane layer is installed/prepared.
Always use this bundle's restore scripts, including after refreshing Toolbox.
Manual no-SD removal, on MMX, is:

```sh
/bin/ksh /mnt/app/carplay-mu1367-lanes/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367-settings/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367/control.sh uninstall
/bin/ksh /mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_restore_core.sh
```

Stop on any failure; recover the failed layer before proceeding. Reboot and
verify OEM cluster, HMI, audio and CarPlay. Keep recovery directories until
successful reboot and an off-unit archive. Reinstallation intentionally
refuses to overwrite a removed/interrupted lane recovery directory. Only
after verifying `STATE=removed`, archive and move that directory aside.
