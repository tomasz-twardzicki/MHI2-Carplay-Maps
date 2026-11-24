# Install or recover MU1367 v1.6.7-e

Use the complete ZIP on supported MU1367 K4525/P4521 HW50/HW70 firmware. Default profile is 791; select 790 explicitly for that cluster. GPS stays off. Both profiles use v1.6.5-e-test2 input.

## Install, including recovery from withdrawn v1.6.6-e

1. Unplug USB and turn the phone's Wi-Fi and Bluetooth off. Perform a full MU reboot before installing, especially if v1.6.6-e cannot disconnect. Keep the phone disconnected throughout migration.
2. Extract the whole ZIP to the SD root. Keep `Custom`, `Toolbox`, scripts and manifests together. Open GEM and run the included **release installer** (`RUN_INSTALL.sh` is the corresponding SD entry point).
3. Repeat the same installer after **every requested full MU reboot**, until it reports `MU1367_RELEASE_1_6_5_E_TEST2_INSTALLED` or `MU1367_RELEASE_1_6_5_E_TEST2_ALREADY_INSTALLED`. These messages are intentional: the SD release is v1.6.7-e, while its parent runtime is exactly test2.
4. From v1.6.6-e, the wrapper first restores the saved 790/791 child, requests a reboot, then restores the saved v166 parent and requests another reboot. The original test2 installer subsequently handles recognized earlier wireless/base layers. v1.5.3/v1.5.4 and v1.6.1 paths are retained, including recovery through the last saved layer and another reboot. The number of stages depends on existing receipts. Keep every snapshot; do not copy individual payloads or delete recovery roots.
5. For **791**, keep the default. For **790**, while the phone is still disconnected, open GEM → CarPlay Maps VC → the experimental profile menu → **790: tested map backend; test2 input**, then fully reboot. The 790 child requires the installed test2 parent. Selecting 791 later restores the saved parent first and requires a reboot.
6. Re-enable phone Wi-Fi and Bluetooth and connect normally. AID map, touch, call routing and disconnect behavior should be tested before a drive. Do not enable the old GPS option: no qualified wireless GNSS/UTC client ships in this package.

Recognized controllers are hash checked before restoration. Changed/unknown controllers or targets are refused with snapshots preserved. If the installer refuses, retain the error and export diagnostics; do not bypass its checks.

## Display options

Fresh turn-card preferences are **Off**. Saved explicit On/Off choices survive. The 790 wireless default URL is map-only; GEM provides separate **790 wireless turn card On/Off** actions. Its default safe area is `202,16,606,344` within `1010×376`, with map and navigation safe areas aligned. The 790 geometry menu adjusts or resets that configuration; follow its reboot/reconnect instructions. 791 tuning remains the original test2 controls; begin with 40/8/150 for comparison.

## Diagnostics and car acceptance

The normal GEM **base diagnostics export** also gathers wireless evidence. The separate wireless collector remains available, including 790 input logs, selected profile, geometry and saved-layer state. Export while connected and again during a symptom. Pairing stores and hotspot configuration are excluded; logs and route/media snapshots can contain personal data, so review before sharing.

Test cold start and Wi-Fi reconnect; MU/AID maps and touch; Keep/disconnect; audio, reverse return and calls; track skip/artwork; 790 card Off/On and centring; and return to 791. On 791, repeat the accepted-session BT-off test separately from Wi-Fi-off. Do not assume that the older 790 observer supplies the same custom accepted-session protection. No startup-freeze, pre-acceptance stale-address paging or GPS fix is claimed.

## Restore

Use this SD's **Remove 790 and restore saved test2 parent** to remove only the optional child, then reboot. The parent wireless uninstall restores its saved preceding layer; use the same SD's release installer/recovery actions to continue after the reboot.

For complete managed removal, run this SD's **complete OEM restore** (`RUN_RESTORE.sh`). Keep the phone disconnected and repeat that same action after each requested full reboot until `MU1367_RELEASE_COMPLETE_OEM_RESTORE` or the OEM-reset already-complete message. It restores the child first, then recognized wireless/base layers, and uses the baseline OEM reset for the package's managed OEM files. Its archive list includes the new 790 and withdrawn v166 receipts. Snapshots are retained.

This preserves test2's restoration scope; it is **not** a universal uninstaller for omonob 3.2 or arbitrary modifications to OEM files. Use the originating installer to remove unrelated modifications before installing. Never delete backups to force adoption. Older SD releases do not recognize the new child; retain this SD for recovery.
