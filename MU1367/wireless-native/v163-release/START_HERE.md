# v1.6.3-e experimental — installation and OEM restore

For K4525/P4521 MU1367 with AID 791 (12.3 inch) only.

Extract the complete ZIP directly to a clean SD root. Refresh both Toolbox
menus and scripts using Toolbox's normal refresh/install action. The CarPlay
Maps banner must show **v1.6.3-e experimental**. Disconnect phones/adapters and
fully reboot before starting.

## Fresh installation and update

Select **CarPlay Maps → Install**. The same SD contains the complete wired
base and wireless installation; installing v1.5.4 or v1.6.1 separately is not
required. Wait for the final result before rebooting. Fully reboot whenever
requested, then repeat Install from this SD until it reports v1.6.3-e installed.
Fresh installation installs the base first, followed after a full reboot by
the wireless layer. Known previous local releases first unwind their saved
layers and request an additional reboot. Keep all recovery folders.

If omonob's upstream package is installed, use the complete OEM restore below
and fully reboot first, then install from this same SD.

The test2 wireless runtime and its recovery identity are retained. Existing
v1.6.3-e-test2 installations are verified and adopted without replacing their
runtime or snapshots.

Turn cards default to **Off** on a fresh preference store. A saved user choice
is retained. Change it through the existing App-Connect navigation-card menu.

## Complete OEM restore, including omonob releases

Select **Recovery → Restore complete OEM state**, or use RUN_RESTORE.sh on MMX.
Repeat the action after every requested full reboot. Local saved wireless
layers are restored first. The next stage restores verified factory files,
removes the known addon hooks/JARs/wireless flags and archives recovery and
management directories, including omonob's public plaintext wired releases
and wireless v3.0, v3.1 and v3.2. Their original SD is not needed.

OEM reset preserves pre-reset files and old recovery journals under
`/mnt/app/carplay-mu1367-oem-reset`. Inert per-unit wireless pairing data is
retained. Do not delete backups or edit receipts. Encrypted/private releases
and other firmware/cluster combinations are outside this release's scope.

After OEM reset, fully reboot disconnected before checking factory operation
or installing again. **Remove wireless** restores its saved wired base;
complete OEM restore is a separate action.

## Validation limits

Bench tests cover installation/recovery scripts and package integrity. Radio,
calls, MFi, MOST, long-duration operation and vehicle behavior need physical
testing. Standard diagnostics include wireless logs and media evidence.
