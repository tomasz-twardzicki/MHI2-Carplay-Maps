# MU1367-P4521 v1.4.1 experimental / 791

Fixes the known dormant upstream-menu installation case behind
`MU1367_SETTINGS_FAIL=UNEXPECTED_BASE_menu` in the P4521 USB test report.
The tester's existing JAR hash was not included in that export, so its exact
identity still requires confirmation. Unknown hashes are refused and printed.

[Download ZIP](./CarPlay_Maps_VC_MU1367_P4521_791_v1.4.1_Experimental.zip?raw=true),
[checksums](./SHA256SUMS.txt), [verification](./VERIFICATION.json),
[installation/retry instructions](../../../MU1367-P4521/INSTALL.md),
[vehicle report and diagnosis](../../../MU1367-P4521/P4521-2026-10-29.md).

The corrected step 3 recognizes exact dormant upstream v2.0.0/v2.0.1
MU1367/791 menu JARs, snapshots them and restores them byte for byte on
rollback. It still rejects active competing boot entries, unknown files and
symlinks. Step 4 pins the exact new settings controller/build. Diagnostics
now include relevant JAR hashes and layer states. Runtime binaries and JARs
are unchanged from v1.4.0; 386 other baseline Custom files are unchanged.

Passed 1,898 package/install checks, 21 settings/migration/fault tests and
19 lane recovery tests. These include reproduction of the old failure,
known-menu rollback, unknown/active-menu refusal and full four-layer return
to OEM without SD. Runtime/ARM-J9 evidence is inherited, not newly rerun.

For the exact rejected step-3 case, keep installed steps 1/2 and their
backups. Use a clean SD, refresh Toolbox menus/scripts, disconnect CarPlay,
fully reboot and retry **step 3 only**. Reboot after success, then run step 4
from this same bundle. Do not delete the old JAR to bypass a refusal.
This is not an in-place upgrade for already completed v1.4.0 settings/lanes.

**Known unresolved issue:** the USB export also proves native reader
termination (`END / WORKER_FAILED`). This release fixes the installer case,
not native reader recovery, every video stutter, or cluster view changes.
Retain diagnostics during a blackout and fully reboot to restart the reader.
No P4521 vehicle validation of v1.4.1 is claimed. 791 / 12.3-inch only.

Original MU1367 v1.4.0 and P4521 v1.4.0 release assets are unchanged.
ZIP SHA-256: `6995e85764345f6d8dabe1f4c9af71f3b7d427a96d881eca9c0f10bf15267c79`.
