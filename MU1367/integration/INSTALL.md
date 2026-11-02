# MU1367 / 791 v1.4.2 — complete installation and update

For **MHI2_ER_VWG13_K4525 MU1367 + AID 791 (12.3 inch)** only. P4521, AID 790,
MU1427 and other firmware are not supported by this package.

Verify `CarPlay_Maps_VC_MU1367_791_v1.4.2.zip` with the adjacent `SHA256SUMS.txt`.
Extract to a clean FAT32 SD root; do not merge older SD contents. Keep this SD
and copy all recovery snapshots off the unit after a successful installation.

Park, maintain stable power and retain working MMX shell access. Disconnect
both the phone and wireless adapter, then fully reboot. Refresh **both Toolbox
menus and scripts** from this SD. The established refresh command on MMX is:

```sh
/bin/ksh /fs/sda0/Toolbox/final/install_scripts.sh /fs/sda0
```

Use `/fs/sdb0` throughout if appropriate. From RCC enter MMX with `on -f mmx`.
Under **MQB Coding > Customization > CarPlay Maps VC**, verify the banner reads
**MU1367 / 791 v1.4.2**. Do not use scripts left from an earlier SD.

## Install / update

Select **Install / update CarPlay integration (reboot)**. This is the single
installation path for video, guidance, native lanes, audio text and artwork,
MU settings, road names, progressing arrows and reconnect recovery. No former
numbered or experimental steps need to be selected separately.

- **Stock OEM, v1.3.0, v1.4.0, supported step-6/step-8 and Integrated Arrows:**
  matching existing layers are checked and retained; missing layers are added.
- **Lane-v2:** the release update is added directly.
- **Active v1.4.1 or v3 / v3r2 / v3r3 / v3r4 (including the right-edge safe-area test):**
  the first invocation checks the saved controller and every original backup,
  removes matching optional card tuning if present, and restores the lane-v2
  baseline through the saved controller. Expect
  `MU1367_RELEASE_MIGRATION_BASE_RESTORED_FULL_REBOOT_THEN_RUN_INSTALL_AGAIN`.
  **Fully reboot disconnected, then run the same install action again.** A
  temporary reboot marker prevents completing both stages in the same boot.
  The old removed snapshot is verified and archived, never overwritten.

The final success message is
**`MU1367_RELEASE_1_4_2_INSTALLED_FULL_REBOOT_REQUIRED`**. Fully reboot with the
phone/adapter absent. Check OEM HMI, cluster and audio before reconnecting.
If a stage fails, retain its complete output and use Recovery. Do not force
version markers, delete recovery directories or continue through an error.
Unknown, modified or interrupted installations are refused; recover their saved
layer first, or use the independent OEM reset below. The oldest first Map Only
experiment requires its documented removal or OEM reset.

The normal **(200,96,400,364)** safe area is restored, with the existing 800×480
canvas. The failed right-edge layout experiment is not applied.

## Defaults, settings and optional tuning

Fresh settings use **30 fps / IDR5**, turn cards OFF and the standard map layout.
Valid existing stream/map/mirror choices are preserved. Adjust them under
**App-Connect > Virtual Cockpit settings**. Reconnect after stream/layout changes.
**Reset saved MU UI settings (reboot)** archives the entire old preference store
as `/mnt/icab/persistent/cpmap-ui.saved-*`; it does not erase the archive.
Reboot disconnected after resetting.

The base runtime has no turn-card controls and ignores old card-ON preferences.
**Tuning > Install optional turn-card support** installs the card-capable runtime
and its corresponding MU UI controls together. Reboot, then explicitly select
Card ON if desired. **Remove turn-card support + settings** restores the base
runtime/menu, retaining preferences and snapshots; fully reboot. An old saved
ON preference can become effective when optional tuning is deliberately added.

**Ottocast Mini Pico may still show a turn card even with the base installed.**
Its scene handling can override the MU request; optional tuning is not required
for that adapter-generated behavior. See [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

## Checks and diagnostics

Guidance status must show **`MU1367-guidance-v1.4.2`**, identifying the rebuilt
JAR with corrected VW U-turn lane bytes (114/146). **Diagnostics > Show integration + guidance + card status**
also reports the release controller version. The release manifest pins all files.

Test cable first, then Mini Pico. Check map alignment, native arrows/countdown,
ETA/current road, recommended lanes, music text/artwork, controls, cancellation,
reroute, OEM navigation priority and switching connection types. Enable the OEM
lane guidance setting. At a suitable junction, check a U-turn lane and its
other exits; the corrected MU1367 rendering still needs vehicle acceptance. Blank unused-lane slots match OEM behavior; this release
does not draw additional outline arrows. Google Maps is the currently exercised
navigation app; Apple Maps/Waze need separate support and acceptance work.

Export **Diagnostics > Export diagnostics to SD** while connected, actively
guiding and displaying the issue. A later disconnect or cable reconnect can
replace session evidence. Retained lane source and factory requests/replies are
available in the same submenu. The runtime uses bounded diagnostic files.

## Recovery and full return to OEM

**Recovery > Remove latest update only** restores the pre-release lane-v2 snapshot;
remove optional turn-card tuning first. Fully reboot. Recovery for a failed or
interrupted latest update is also in this submenu. On MMX, without SD/HMI:

```sh
/bin/ksh /mnt/app/carplay-mu1367-turn-cards/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367-guidance-v3/control.sh uninstall
```

Run the first command only if tuning is installed. Stop on any failure. For an
interrupted latest update, use `recover` instead of `uninstall` on its saved
controller. Restoration verifies every backup before replacing any target.

For a complete fresh start, choose **Recovery > RESTORE OEM + retain all snapshots**.
This independent reset restores exact firmware-matched files, remounts/checks
writes first, and archives all twelve active integration/recovery roots. It
also handles mixed installations and roots marked removed. It does not depend
on older layer uninstallers. Expect
`MU1367_OEM_RESET_COMPLETE_FULL_REBOOT_REQUIRED`; fully reboot disconnected,
then run **Diagnostics > Verify restored OEM files** and check stock operation.
Completed reset sessions are archived before a subsequent reset; interrupted
sessions must be recovered, not discarded. A real remount/write failure is
not bypassed. See [MU1367_OEM_RESET_INSTALL.md](MU1367_OEM_RESET_INSTALL.md).

Without menus, run on MMX:

```sh
/bin/ksh /fs/sda0/RUN_RESTORE.sh
```

After reboot, run `/bin/ksh /fs/sda0/RUN_VERIFY.sh`. Keep the SD and copy
`/mnt/app/carplay-mu1367-oem-reset`, all `.completed-*` and `.removed-*` snapshots
off-unit. The full original HMI boot script is restored, so other boot-script
edits are removed after backup. Coding, FECs, pairing, OEM user data and Toolbox
are retained. Custom MU preferences are retained unless explicitly reset.
