# MU1367 / 791 v1.5.2-e — complete installation and update

For **MHI2_ER_VWG13_K4525 or MHI2_ER_VWG13_P4521 MU1367 + AID 791
(12.3 inch)**. **P4521 installation remains experimental**, following a successful
vehicle test of the earlier P4521 experimental build. AID 790, MU1427 and other
firmware are outside this package. Both supported trains receive the same complete
feature set, including the v1.4.2 U-turn fix. Exact firmware hashes remain required.
The installer reports `MU1367_FIRMWARE_TYPE=P4521_EXPERIMENTAL` or `K4525` when
RCC train information is available. Without it, the shared exact firmware hash
is reported as `K4525_OR_P4521_HASH_MATCH`; it cannot distinguish these trains.

**Experimental update — to be tested.** Based on stable v1.4.6, with every CarPlay
feature of it: driving-side U-turn lanes, Apple Maps in any phone language, the 27 fps /
IDR 5 default and compressed album artwork by default. It adds **Android Auto**: the
Google Maps picture on the AID and native VW turn arrows from an Android phone. The
normal install action installs CarPlay and Android Auto together. It saves the
originals for rollback, including the factory Android Auto receiver. See [RELEASE-NOTES.md](RELEASE-NOTES.md).

If the previous standalone reader test is installed, restore it first using
its saved controller and fully reboot. Audio R1/R2 test layers and the artwork
refresh test from v1.4.5 (**Tuning > Remove artwork test**) must be removed before a
base upgrade, because the release retains the original audio runtime.

Verify `CarPlay_Maps_VC_MU1367_791_v1.5.2-e.zip` with the adjacent `SHA256SUMS.txt`.
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
**MU1367 / 791 v1.5.2-e - EXPERIMENTAL (CarPlay + Android Auto)**. Do not use scripts left from an earlier SD.

## Install / update

**From the separate P4521 v1.4.0/v1.4.1 experimental package:** its settings/lane
transactions differ from the integrated baseline. First select **Recovery >
Restore complete OEM state**, fully reboot disconnected, then select the normal
install action below. OEM reset verifies the shared firmware originals, archives
all old layers and retains settings/snapshots. It also removes dormant upstream
menu JARs. Do this before installing over an older upstream Toolbox map package
with a dormant `VCMenu.jar`. Do not delete or edit version markers. An installed
P4521 v1.4.1 settings layer is recognized and directs you to this recovery path
before any installation writes.

Select **Install / update CarPlay integration (reboot)**. The installer first
prints `MU1367_INSTALL_STEPS=N`, then one numbered line per completed layer,
for example `[3/9] MU1367_WIRELESS_INSTALLED`. **Do not reboot while it runs.**
Only the final message asks for a reboot. This is the single installation path for video, guidance, native lanes, audio text and artwork,
MU settings, road names, progressing arrows, reconnect recovery and Android Auto. No former
numbered or experimental steps need to be selected separately.

- **Stock OEM, v1.3.0, v1.4.0, supported step-6/step-8 and Integrated Arrows:**
  matching existing layers are checked and retained; missing layers are added.
- **Lane-v2:** the release update is added directly.
- **Active integrated v1.4.1/v1.4.2/v1.4.3/v1.4.3-e/v1.4.4/v1.4.5/v1.4.6-e/v1.4.6/v1.5.0-e/v1.5.1-e (both builds), or v3 / v3r2 / v3r3 / v3r4 (including the right-edge safe-area test):**
  this is the one case that needs two reboots. The first invocation (stage 1 of 2) checks the saved controller and every original backup,
  removes an installed Android Auto layer (the factory `gal` returns from its snapshot) and matching optional card tuning if present, and restores the lane-v2
  baseline through the saved controller. Expect
  `MU1367_RELEASE_MIGRATION_BASE_RESTORED_FULL_REBOOT_THEN_RUN_INSTALL_AGAIN`.
  **Fully reboot disconnected, then run the same install action again.** A
  temporary reboot marker prevents completing both stages in the same boot.
  The old removed snapshot is verified and archived, never overwritten.

The final success message is
**`MU1367_RELEASE_1_5_2_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED`**, preceded by
`MU1367_INSTALL_COMPLETE=N/N`. Disconnect the phone/adapter, then select
**Reboot unit (after install completes)** in the same menu. That entry refuses to
reboot while an installation is still running and otherwise uses the Toolbox's
own reboot helper. Toolbox **Coding > Reboot unit** is equivalent. Check OEM HMI, cluster and audio before reconnecting.
If a stage fails, retain its complete output and use Recovery. Do not force
version markers, delete recovery directories or continue through an error.
Unknown, modified or interrupted installations are refused; recover their saved
layer first, or use the independent OEM reset below. The oldest first Map Only
experiment requires its documented removal or OEM reset.

The map-only view declares the **(160,20,480,440)** safe area of v1.2.2 (v1.5.2-e test;
v1.4.x–v1.5.1-e used 200,96,400,364), with the existing 800×480 canvas. The turn-card
option keeps its own layouts. The failed right-edge layout experiment is not applied.

## Android Auto

The last install step is `MU1367_ANDROID_AUTO_INSTALLED`. It checks the factory
Android Auto receiver `/mnt/app/eso/bin/apps/gal` by hash, saves it under
`/mnt/app/carplay-mu1367-android-auto/backup`, and puts a small wrapper in its place.
The hook runtime goes to `/mnt/app/carplaymaps/aa`. Nothing in `/mnt/system` changes.
Updating from v1.5.0-e or v1.5.1-e removes the old Android Auto layer in stage 1
of the two-stage update above (its snapshot is kept); stage 2 installs the new one. An
older Android Auto layer left on top of this release's main layer is replaced in place
(`MU1367_ANDROID_AUTO_PREVIOUS_BUILD_REMOVED_UPGRADING`).

## CarPlay video bridge (since v1.5.1-e)

The main layer also replaces `/mnt/app/carplaymaps/altscreen-most-bridge` with this
release's build, which takes the MOST output back from the factory encoder during boot
instead of exiting. The upstream bridge is kept in the main layer's snapshot and comes
back on uninstall or recovery. In an exported `altscreen-most-bridge.log`,
`bridge: most-reclaim attempt=1 … dmdt=0/0` followed by `reopen=ok` means a reclaim
happened and worked.

After the reboot, connect an Android phone by cable and start a route in Google Maps.
The picture appears on the AID about 5 s after connecting. **Android Auto cluster map:
off** makes Android Auto run exactly as from the factory from the next connection;
**on** brings the map back. The MU menu's cluster map switch applies as well: with the
map off, the AID keeps its VW content for Android Auto too.

Status: **Diagnostics > Show integration + guidance + card status** ends with
`ANDROID_AUTO_STATE`, the wrapper's last decision (`hook=yes/no`), the feeder summary
(`/ramdisk/pmcp-aa-feeder.txt`) and the Android Auto guidance status. The route
guidance status shows `phone=3 root=/ramdisk/pmcp-aa-rg` while it reads Android Auto.

## Defaults, settings and optional tuning

Fresh settings use **27 fps / IDR 5**, turn cards OFF and the standard map layout.
Valid existing stream/map/mirror choices are preserved. Adjust them under
**App-Connect > Virtual Cockpit settings**. Reconnect after stream/layout changes.
**Map stream** offers 20, 25, 27, 30 and 40 fps, all with IDR 5. A saved
30 fps / IDR 20 or 40 fps / IDR 20 choice from an older release now runs at the same
frame rate with IDR 5. Before rolling back, select **30 fps / IDR 5** or
**40 fps / IDR 5**: v1.4.5 and older menus do not recognize 20 or 27 fps, and v1.4.4
and older also not 25 fps.
**Reset saved MU UI settings (reboot)** archives the entire old preference store
as `/mnt/icab/persistent/cpmap-ui.saved-*`; it does not erase the archive.
Reboot disconnected after resetting.

The base runtime has no turn-card controls and ignores old card-ON preferences.
**Tuning > Install optional turn-card support** installs the card-capable runtime
and its corresponding MU UI controls together. Reboot, then explicitly select
Card ON if desired. **Remove turn-card support + settings** restores the base
runtime/menu, retaining preferences and snapshots; fully reboot. An old saved
ON preference can become effective when optional tuning is deliberately added.

**Compressed album artwork is installed by default** (step `MU1367_ARTWORK_PNG_INSTALLED`).
It replaces the artwork helper with one that writes the same lossless 256 × 256 cover
PNG compressed with the factory zlib: usually 1–100 KB instead of 197 KB, with identical
pixels, and saves the original helper. **Tuning > Disable compressed album artwork
(reboot)** restores the original; a later install keeps it disabled
(`MU1367_COMPRESSED_ARTWORK_KEPT_DISABLED`). **Remove latest update only** and
**RESTORE OEM** from the menu switch it off first. Only if you run the OEM reset without
the menu does its folder `/mnt/app/carplay-mu1367-artwork-png` stay behind; the next
install archives it. To switch it off without the SD, run on MMX:

```sh
/bin/ksh /mnt/app/carplay-mu1367-artwork-png/control.sh uninstall
```

**Ottocast Mini Pico may still show a turn card even with the base installed.**
Its scene handling can override the MU request; optional tuning is not required
for that adapter-generated behavior. See [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

## Checks and diagnostics

Guidance status must show **`MU1367-guidance-v1.5.0-e`** (unchanged in v1.5.1-e); the reader is unchanged from v1.4.4 and its status shows
`MU1367-reader-v1.4.4-e` with `total_restarts` and `budget_resets`. The U-turn
lane bytes (114/146) are unchanged. **Diagnostics > Show integration + guidance + card status**
also reports the release controller version. The release manifest pins all files.

Test cable first, then Mini Pico. Check map alignment, native arrows/countdown,
ETA/current road, recommended lanes, music text/artwork, controls, cancellation,
reroute, OEM navigation priority and switching connection types. Enable the OEM
lane guidance setting. At a suitable junction, check a U-turn lane and its
other exits; the corrected MU1367 rendering still needs vehicle acceptance. Blank unused-lane slots match OEM behavior; this release
does not draw additional outline arrows. Google Maps is the exercised navigation
app; this build targets Apple Maps and Waze delivery and needs their acceptance.
Test Apple Maps with stops longer than 5 s (for example at lights) and Waze with
an active route. `guidance-evidence.txt` names the phone app in each export.

For this build: with an Android phone, check the Google Maps picture on the AID, VW
arrows with distance and the bar during a route, switching between a CarPlay iPhone and
the Android phone without a reboot, the two **Android Auto cluster map** entries, and
that CarPlay behaves as with v1.4.6. Export diagnostics while the issue is visible.

From v1.4.6: in left-hand traffic, check that a U-turn lane shows the right U-turn
arrow. With Apple Maps and a non-English phone language, check that arrows and lanes
update from the first turn; `guidance-evidence.txt` then shows `route_clears source=0`
and a `source_flips` line. Compare stutter and smoothness at the 27 fps default against
your previous setting.

Export **Diagnostics > Export diagnostics to SD** while connected, actively
guiding and displaying the issue. A later disconnect or cable reconnect can
replace session evidence. Retained lane source and factory requests/replies are
available in the same submenu. The runtime uses bounded diagnostic files.

## Recovery and full return to OEM

**Recovery > Remove latest update only** first removes Android Auto (the factory
`gal` comes back from its verified snapshot), switches compressed artwork off, then
restores the pre-release lane-v2 snapshot;
remove optional turn-card tuning first. The saved reader is restored in the
same transaction. Fully reboot. Recovery for a failed or
interrupted latest update is also in this submenu. On MMX, without SD/HMI:

```sh
/bin/ksh /mnt/app/carplay-mu1367-android-auto/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367-turn-cards/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367-guidance-v3/control.sh uninstall
```

Run the second command only if tuning is installed. Stop on any failure. For an
interrupted latest update, use `recover` instead of `uninstall` on its saved
controller. Restoration verifies every backup before replacing any target.

For a complete fresh start, choose **Recovery > RESTORE OEM + retain all snapshots**.
From the menu it removes Android Auto and compressed artwork first. If you run the
independent reset without the menu (`RUN_RESTORE.sh`), it still archives the Android
Auto runtime and Android Auto keeps working as from the factory, but the wrapper stays
in place of `gal`; run the Android Auto `uninstall` command above afterwards.
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
