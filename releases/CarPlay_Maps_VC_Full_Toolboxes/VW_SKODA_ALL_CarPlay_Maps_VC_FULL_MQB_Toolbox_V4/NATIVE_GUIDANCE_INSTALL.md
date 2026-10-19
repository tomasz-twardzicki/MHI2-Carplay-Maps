# MU1427 native guidance — full installation

Full MQB Toolbox bundle with automatic MU1427 native guidance, version 1.0.0.

This full MQB Toolbox bundle keeps the original AUTO MU video installers and
adds **Install full native guidance (MU1427 only)**. The add-on supplies native
arrows and maneuver distance on AID/HUD, plus remaining route distance and
travel duration on AID. It starts automatically after boot and needs no manual
recorder, shadow verification or five-minute test. Phone navigation controls
when guidance appears; OEM guidance retains priority.

The menu credits **omonob (QCDWJ)** for the baseline and
**tomasz-twardzicki** for the MU1427 version and native guidance additions.
Research/test entries are removed. The narrow/wide phone turn cards move
16 pixels lower to clear the native distance/time bar; map-only is unchanged.

## Install

1. If a D-series **test HMI adapter** remains installed, remove it with its
   existing menu and fully reboot first. If D3 was already removed/rebooted,
   start there. **Do not restore B4 to factory**: the new installer accepts
   both the tested B4 pair and factory driver/config, preserving OEM backups.
2. Extract the full ZIP to the SD root and refresh/install the toolbox
   scripts and menus as before. Prefer a clean extraction; preserve your
   existing `Log` folders separately if needed. The CarPlay Maps VC menu
   should show the new credits and no phase-test entries.
3. Disconnect the phone. Select **Install 791 AID 12.3 (AUTO MU)**. This also
   installs the lowered default turn card. Existing users should rerun it to
   receive the updated core. The tuning menu still offers narrow/wide/map-only.
4. Select **Install full native guidance (MU1427 only)**. Expect
   `CPMAP_GUIDANCE_INSTALLED_REBOOT_REQUIRED` or `CPMAP_GUIDANCE_ALREADY_INSTALLED`.
   The new option requires an installed `MU1427/791` base profile and refuses
   other firmware. It installs the matched driver/config when necessary,
   the HMI JAR, and the automatic reader. It preserves unrelated HMI JARs.
5. **Fully reboot once after both installs.** Confirm the normal OEM cluster
   map before connecting the phone, then connect and start phone guidance.
   Arrows, maneuver distance and route totals should appear automatically.

The maneuver/route mapping and factory formatting passed D3 unit testing.
This release adds automatic startup and a continuous RAM feed, and lowers the
card. Host and factory QNX/J9 tests pass; **these release-specific changes
still need a first check on the unit**.

## First installation check

Check that the turn card clears the distance/time bar, native AID/HUD arrows
and distances agree with the phone, and route totals appear. Let guidance
continue beyond five minutes to confirm automatic continuous operation.
Stop guidance, unplug/reconnect during another route, and briefly use OEM
guidance: values should clear/recover and OEM guidance should have priority.
Check again after a full reboot; no manual start should be necessary.

**Show native guidance status** reports the installed build and reader/HMI
counters. During eligible phone guidance expect `mode=2 context=0`, increasing
ticks/writes and `failures=0 error=0`. With no connected phone or active OEM
guidance the ownership context differs and phone output stays suppressed.

The reader stores only a bounded latest-state file in RAM, with no route
archive or automatic SD logging. Device reads stay in its supervised worker;
a stuck worker stops the reader rather than accumulating replacement workers.
The HMI clears output on lost freshness. Unexpected reader/decoder failure
requires a reboot after checking status.

## Disable, remove or restore

- **Disable native guidance now (until reboot)** releases native output and
  leaves ordinary CarPlay working. It does not require SD payload files.
  Reboot enables the installed add-on again.
- **Remove native guidance (reboot)** removes its boot entries/JAR and restores
  the OEM iAP2 driver/config from the preserved backups. It keeps the base
  video patch, display choice and unrelated HMI patches. Fully reboot.
- **Restore factory files** first removes native guidance when installed,
  then runs the existing base video restore. Fully reboot afterwards.

The saved MMX recovery controller works without SD:

```sh
/bin/ksh /mnt/app/carplay-route-guidance/control.sh disable
/bin/ksh /mnt/app/carplay-route-guidance/control.sh uninstall
```

Then fully reboot. From RCC prefix each command with `on -f mmx`.
If removal reports a boot-script/rename failure, keep guidance disabled and
retain the reported error and recovery directory. The script keeps the JAR
when it cannot safely remove the boot entry; fix the reported filesystem/layout
condition and retry removal. OEM backups are retained for recovery, and normal
removal preserves later unrelated HMI changes instead of restoring an old
complete boot script.

Street text, lane graphics, bargraph and clock-time arrival ETA are outside
this release. The shown time is remaining travel duration. Firmware support
is limited to `MHI2_ER_VWG11_K3342_MU1427` with the 791 cluster profile.
