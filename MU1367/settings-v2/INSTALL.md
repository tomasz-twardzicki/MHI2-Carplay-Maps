# MU1367 / 791 settings: install, acceptance and rollback

This test package has [initial user test results](UNIT-RESULTS.md): 30 fps /
IDR5 was preferred, with some stutter reported for both 40 fps profiles.
Extended endurance and the individual acceptance checks below remain
unrecorded. Use only the exact MU1367
firmware (`lsd.jxe` SHA256
`09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a`)
and the **791** cluster. Installation requires our exact preceding integration
build; unknown cores, other v2 HMI patches and altered payloads are refused.

## Preparation and installation

1. Verify the new ZIP against its adjacent `SHA256SUMS.txt`. Extract to a clean
   SD root and refresh the Toolbox menus **and scripts**, including restore
   scripts. Preserve diagnostic exports and recovery backups separately.
2. Work while parked with stable power and a working MMX shell. Save the
   commands below outside the MU. Disconnect the phone and fully reboot
   before installing, so no CarPlay session is active. No script auto-reboots.
3. For a fresh MU1367 installation, follow the bundled `MU1367_INSTALL.md`
   (the prior integration instructions): run **1. Install MU1367 / 791 video**,
   then **2. Install MU1367 / 791 guidance + audio text**. Reboot and check the
   base features first. If those exact steps are already installed, retain
   them and proceed directly to step 3 below. Do not reinstall over backups.
4. Select **3. Add MU UI settings + map/mirror runtime (791)**. Expect
   `MU1367_SETTINGS_INSTALLED_REBOOT_REQUIRED`. A complete verified snapshot,
   saved controller and verifier are written under
   `/mnt/app/carplay-mu1367-settings` before files are replaced. The HMI
   prepend and parent uninstall guard are committed after the runtime files.
5. Fully reboot with the phone absent. Check the OEM HMI/cluster first, then
   App-Connect setup's **Virtual Cockpit settings** entry. Initial stream/layout
   defaults are 30/20 and narrow unless saved preferences already exist.

Use the MU selectors for stream/layout while this layer is installed. The
new Toolbox scripts block old GEM core tuning, parent removal and direct
base restore until the layer is removed. Do not use an older SD's tuning or
restore scripts. Firmware upgrades and installing another version require
removal/recovery in reverse order first; never use another MU's backups.

## Vehicle acceptance and remaining checks

The latest user-selected setting is **30 fps / IDR5**. The supplied artifact's
first-install default remains 30/20; select 30/5 in the native MU settings and
reconnect CarPlay to reproduce the user's preferred configuration. The ZIP
is preserved byte-for-byte from the tested build.

Start with 30/20, narrow, map enabled and mirror disabled. Test OEM cluster,
HUD, audio, MirrorLink entry and phone navigation independently. Compare native
arrows, distances and remaining time against the phone, including after
guidance stops and OEM navigation resumes. Check music text, source switching,
steering/rotary keys and all six MU settings rows; the last row must remain
visible and operable. Check that returning/re-entering setup restores widgets.

Change one variable at a time. Select 40/5, unplug/reconnect CarPlay, then
compare smoothness, CPU/load, disconnects and stability over an extended run
and after full reboot. Compare 30/5 or 40/20 to isolate cadence from FPS.
Test compact-below-bar first, then upstream compact if desired; verify the
native distance/time bar remains readable. Card ON/OFF should update live.
Map/mirror selection should respect map priority and leave OEM navigation
usable. Test phone reconnect and rapid card switches without stale output.

Check Apple Maps, Google Maps and Waze individually. Existing Waze freezing
has no established fix here. Wireless is a test selector only. N3 capture
remains optional and is not part of first acceptance. Collect Toolbox
diagnostics plus `/tmp/cpmap-menu-offline.log` and persistent preference files
before reboot; compare the actual phone/cluster display, not only logs.

## Remove just this layer (no SD needed)

Disconnect the phone. Run on **MMX**; from RCC use `on -f mmx`:

```sh
/bin/ksh /mnt/app/carplay-mu1367-settings/control.sh status
/bin/ksh /mnt/app/carplay-mu1367-settings/control.sh uninstall
```

Expect `MU1367_SETTINGS_REMOVED_REBOOT_REQUIRED_PREFERENCES_RETAINED`.
Fully reboot. This restores the prior video runtime, steering controls,
wrapper/launcher and parent controller, and removes `VCMenu.jar`. Native
guidance/audio/NAI remain installed. Ordinary removal deletes only its own
boot token and preserves later unrelated boot entries. All backups and
`/mnt/icab/persistent/cpmap-ui` preferences remain.

The matching Toolbox action is **Remove MU UI settings layer (reboot)**.

## Interrupted installation or damaged HMI

Use the saved snapshot recovery rather than normal uninstall:

```sh
/bin/ksh /mnt/app/carplay-mu1367-settings/control.sh recover
```

It validates every backup before restoring targets, removes staged files,
restores the entire pre-layer snapshot (including boot), and retains backups.
It can discard later boot edits; review those before recovery. Fully reboot.
An incomplete rollback prints `MU1367_SETTINGS_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER`.
If a lock remains after an interrupted operation, confirm no installer is
running before removing the empty `/ramdisk/.carplay-guidance-install-lock`
directory and retrying recovery. Never delete backup contents to bypass a gate.

If the HMI itself cannot start but MMX shell works, run the saved recovery
directly; it does not need the HMI. As an emergency menu-only bypass:

```sh
mv /mnt/app/eso/hmi/lsd/jars/VCMenu.jar /mnt/app/eso/hmi/lsd/jars/VCMenu.jar.disabled
```

Fully reboot. The missing prepend entry falls back to stock factory HMI;
the video/runtime layer still exists. Run `recover`, then reboot again;
ordinary uninstall correctly refuses a manually removed JAR. The separate
native/audio emergency procedures are in `MU1367_INSTALL.md` / `../port/INSTALL.md`.

## Full return to OEM

The **Restore factory video + integration** action in this new bundle runs:
settings uninstall, native/audio uninstall, then base video restore. It stops
on any failure. For manual no-SD removal, after removing/recovering settings:

```sh
/bin/ksh /mnt/app/carplay-mu1367/control.sh uninstall
/bin/ksh /mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_restore_core.sh
```

Fully reboot and verify OEM driver/configuration, cluster map, HMI, audio and
CarPlay. If either transaction is incomplete, recover that transaction first;
do not force the next layer's restore. Recovery folders remain for inspection.
Before a fresh settings installation, archive the removed settings recovery
directory off-unit and move it aside only after checking `STATE=removed` and
confirming successful reboot. The installer deliberately refuses to overwrite
an old recovery directory. Keep the archived snapshot until vehicle checks pass.

Rollback procedures reduce recoverable software-failure consequences; offline
testing cannot guarantee recovery from power/storage failure or untested
hardware behavior.
