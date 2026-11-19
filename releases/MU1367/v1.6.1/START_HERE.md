# MU1367 / AID 791 v1.6.1 — install, update and restore

For K4525/P4521 MU1367 and AID 791 only. Extract the complete ZIP to a clean
FAT32 SD root. Keep the SD and all saved recovery snapshots. Disconnect USB and
wireless CarPlay before installation; keep the phone disconnected through every
reboot stage. Refresh both Toolbox menus and scripts from this SD using its
normal Toolbox refresh/install action. The banner must show v1.6.1.

## Install or upgrade

Select the normal **CarPlay Maps VC → Install/update** action, or run
`RUN_INSTALL.sh` from the SD. Follow the displayed result:

1. If an older wireless layer is active, the installer checks and runs its saved
   controller to restore its exact previous layer. Fully reboot, then select
   Install/update again from this same SD. The old SD is not needed.
2. If the base needs upgrading, the existing verified migration first restores
   the last known layer and retains its snapshots. Fully reboot and run Install
   again. Once the v1.5.4 base has been installed, fully reboot and repeat Install
   once more to add wireless support.
3. Completion is `MU1367_RELEASE_1_6_1_INSTALLED_FULL_REBOOT_REQUIRED`. Fully
   reboot before reconnecting the phone. A verified existing test2 installation
   instead reports `MU1367_RELEASE_1_6_1_ALREADY_INSTALLED`; it keeps its tested
   runtime and original snapshots.

From v1.5.4, only the wireless install/reboot is normally needed. From v1.5.3,
allow the base rollback/reboot, updated base install/reboot, then wireless
install/reboot. Older supported base revisions use the same checked migration.
Never remove a reboot marker or edit `STATE` to skip a stage. Unknown versions,
changed files, missing snapshots or damaged backups are preserved and reported.

Bluetooth starts the wireless Wi-Fi handoff. Keep Bluetooth and Wi-Fi enabled;
manual hotspot joining is a diagnostic step. USB retains priority. On a first
boot with no saved OEM driving-side coding, let the HMI finish starting and
reconnect once if the initial layout was negotiated too early. Subsequent cold
boots use the saved OEM coding, with live coding taking priority.

## Recovery and complete OEM restore

**Recovery → Restore complete OEM state**, or `RUN_RESTORE.sh`, first restores
the wireless snapshot and asks for a full reboot. Repeat the same action from
this SD after reboot to run the factory OEM restore. This restores the factory
CarPlay driver, boot/config/DIO files, Bluetooth/connection-manager changes and
Android Auto receiver, removes added active runtime/JARs, and archives the
wireless and base recovery directories. Completed earlier OEM-reset snapshots
are retained under unique names before another reset is prepared.

For an interrupted transaction, choose **Recover interrupted install**. The
saved controller validates before/after receipts; it never overwrites an
unknown third-party edit. Reboot when instructed and resume the intended action.
**Remove wireless** restores the v1.5.4 base first; it is not a direct downgrade
to v1.5.3. Complete OEM restore is a separate second stage after reboot.
Pairing data, user preferences and retained recovery snapshots are kept.

## Diagnostics and tuning

Use the normal **CarPlay diagnostics → Collect diagnostics to SD** while the
failure is present. Its `Log/cpmap-diag-*/wireless` folder includes receiver,
video, autostart and input logs; process fingerprints; PID/owner/grant/feed
state; guidance/lanes and bounded route mailbox; IDR cadence receipt; live and
cached driving-side coding; stream preferences and timing metadata. Standard
logs and sloginfo are in the same export. Pairing stores, hotspot passwords and
the large encoded-video ring are excluded. Review route/vehicle identifiers
before sharing. The separate wireless export remains available as well.

Default wireless request is 40 FPS, IDR8 and 150 ms smoothing. Wireless-page
choices are FPS 20/25/30/40, IDR 5/7/8/10/15, smoothing Off/100/150/200 ms.
Reconnect after changing a value. Wired stream-test controls and OEM
remaining-time/arrival-time selection are retained from v1.5.4.

Wireless media text/artwork forwarding is not included. Android Auto retains
its previous validation limits. Stable promotion follows the maintainer's
successful test2 vehicle report; exhaustive endurance and tuning combinations
are not claimed. Exact component and installation evidence is in VERIFICATION.json.
