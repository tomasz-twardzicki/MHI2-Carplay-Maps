# MU1427 route-guidance B1 test

> Historical test procedure. Use [INSTALL.md](./INSTALL.md) for the released package. Obsolete test tools are retained in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

**Historical test instructions.** The first in-car B1 run later lost CarPlay;
rollback and reboot restored normal operation. Do not repeat B1 yet. Use the
recovered C1 findings in [B1-RESULTS.md](./B1-RESULTS.md) and the corrected
next test in [TEST-B2.md](./TEST-B2.md).

**Experimental.** This test asks
the iPhone for guidance and records raw messages. It does not show VW arrows.
Use a parked vehicle with stable power and the existing toolbox recovery route.

## Build on the computer

Requires Python 3, clang with the ARM assembler, and `ksh` for the
installer tests. The scripts require the exact factory/Phase A driver and
config, not a previously patched file. Install host dependencies in a venv:

```sh
python3 -m venv /tmp/mu1427-rg-venv
/tmp/mu1427-rg-venv/bin/pip install pyelftools unicorn
```

With `DRIVER` and `CONFIG` pointing to the private Phase A copies:

```sh
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-driver.py "$DRIVER"
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/build-test-package.py "$DRIVER" "$CONFIG"
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-install.py "$DRIVER" "$CONFIG" MU1427/route-guidance/build/sd-card/Custom/route_guidance_b1
```

On macOS the Unicorn CPU/cache probe may need permission to run outside the
Codex sandbox. The build itself does not require a QNX SDK or Docker.

Output: `build/MU1427-route-guidance-B1-install-r3-toolbox.zip`, a **full** toolbox SD
layout, plus `build/SHA256SUMS.txt`. Use a fresh `--output` directory to rebuild.
`build/sd-card/Custom/route_guidance_b1/manifest.json` records the driver SHA-256,
patch sites, payload hash and source hash. Generated firmware files are ignored
by git; keep the test ZIP and collected logs private.

### Installer r3: follows the working base patch

The first two on-unit attempts stopped before any file changes: the initial
script needed unavailable `tr`, and r2 still required unavailable `cksum`.
Neither attempt installed the driver, and neither needs a restore.

Installer **B1-install-r3** uses `ls -ln` field 5 for firmware, OEM, payload,
staged-file and backup sizes, as the base map patch does. Its external commands
are only `ls`, `cp`, `cat`, `mv`, `mkdir`, `rm`, `sync`, plus `mount` / `on` for
the same MMX/RCC remount paths as the base patch. `cp -p`, already used by the
toolbox's `sshd_install.sh`, preserves the original file permissions.

There is no on-unit hashing, system `cmp`, `awk`, `tr`, `wc`, or `rmdir`
dependency in installation or rollback. All installer tests use a closed PATH
containing only the seven file utilities above. Host Python still verifies
SHA-256 before packaging; on-unit size checks do not detect same-size changes.
The ARM driver and config payloads are unchanged.

Extract the r3 package at the SD root and **update the toolbox again**, so the
installed script is replaced. Merely replacing the SD payload keeps the old
installer. The console must show `MU1427 route guidance installer: B1-install-r3`
when the B1 entry runs. Then continue with the steps below.

## Install and test

1. Verify the ZIP against `SHA256SUMS.txt`, extract it directly to the SD root,
   and update the toolbox from this package. The B1 entries appear under
   **Customization → CarPlay Maps VC**. The normal map installer is separate;
   there is no need to rerun it for this experiment.
2. **Disconnect the iPhone.** Run **EXPERIMENTAL MU1427: install route guidance
   B1**. Continue only after `CPMAP_RGI_INSTALL_OK`. The script checks the
   firmware/OEM/payload sizes and the payload build marker, and saves backups
   to `/mnt/app/route-guidance-b1/`. It replaces the two files by rename and
   leaves the current processes running.
3. Exit the toolbox and do **one full unit reboot** before reconnecting the
   iPhone. This also clears the old `/dev/shmem/iap2.log`.
4. Connect over USB. Confirm CarPlay and the existing cockpit map work. Start
   an Apple Maps route while parked; wait 15–30 seconds. Cancel it, start
   another route, and change a music track to check that metadata still works.
5. Run **Collect navigation research data to SD** before rebooting. Save this
   as run B1a. The private `Log/cpmap-navrecon-*/iap2.log` is the primary result;
   `rgi-b1-status.txt` records installed/backup file sizes and the B1 markers.
6. Unplug/replug, repeat with a route already selected on the phone, and collect
   a second log (B1b). This tests a fresh session and restored-route timing.

Success in each fresh connection means:

- Identification includes component `0x001e`, sent IDs `5200,5203`, and received
  IDs `5201,5202,5204`, and the phone answers `IdentificationAccepted`.
- `CPMAP_RGI_START B1 0x5200 rc=0 (0=queued)` appears after the stock features
  start. This proves the stock transport accepted the extra frame, not that the
  phone processed it.
- `CPMAP_RGI_RX id=0x5201 ...` and `id=0x5202 ...` appear, each followed by a
  full hex dump of its TLVs. `0x5204` depends on lane guidance being available.
- CarPlay, map video and changing music metadata continue to work.

There is one start attempt per successful stock feature initialization. If the
start queues but no updates arrive, preserve that log and test the fresh replug;
retry timing is a later change. No updates by itself does not prove the protocol
layout is wrong. This build has no timer or automatic retries.

## Restore

Disconnect the phone, run **Restore factory iAP2 driver and config (B1)**, wait
for `CPMAP_RGI_RESTORE_OK`, then exit and fully reboot. This entry uses the local
backups and works without the SD payload. Backups remain for repeat testing.
**Restore factory files** is the separate map-video restore; use the B1-specific
entry to undo this driver experiment. Rollback checks the original backup
sizes and stages both originals before replacing either active file. It also
works when the active driver/config is missing, truncated or otherwise damaged;
it does not require their sizes to match, a build marker or an SD manifest.

If CarPlay fails, collect diagnostics first while the unit is still running,
then restore. If the toolbox entry is unavailable but a shell is available:

```sh
# On MMX; from RCC prefix the script path with /net/mmx.
/bin/ksh /mnt/app/route-guidance-b1/rg-b1.sh restore
```

Before first install, also keep copies of the factory driver and config on the
SD. For manual recovery, their destinations are
`/mnt/app/armle/lib/dll/ipod-drvr-iap2.so` and
`/mnt/system/etc/mm/iap2.cfg`. Remount both partitions writable and restore both
files, then reboot. Do not overwrite a mapped SO in place; copy to a temporary
file on the destination partition and rename it. Stock fingerprints:

| File | SHA-256 (computer only) | OEM bytes | B1 bytes |
| --- | --- | ---: | ---: |
| Driver | `0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51` | 739925 | 741796 |
| Config | `ce05524385ccae1167966d45c52ff60ac0c70fe0f46ac98d77a75f109a6bfa6c` | 5905 | 6006 |

A power interruption between the two file renames leaves a partial install;
repeat B1 restore before reconnecting. Installation refuses unsupported current
sizes; rollback only requires valid-sized original backups. The operation lock
is `/ramdisk/.route-guidance-b1-lock`, so a full reboot clears it. If an
interrupted operation in the same boot leaves that directory, verify no
install/restore is running before removing it. Original backups remain in
`/mnt/app/route-guidance-b1/` across reboots. An incomplete backup directory
requires manual inspection rather than overwriting the originals.

## What remains untested

The QNX loader must accept the additional RX `PT_LOAD`, the native logger must
show the markers, and the iPhone must accept the component and deliver updates.
ARM emulation cannot establish these. There is no decoded PPS output, maneuver
mapping, HMI hook, retry timer or explicit `0x5203` teardown in B1. Unplugging
closes the session; restoring/rebooting removes the subscription with it.

Protocol layout attribution: LuKa (@LuKa_dev), GPL-3.0-or-later,
[`mib2q-carplay-rgi`](https://github.com/luka-dev/mib2q-carplay-rgi/tree/dfafccf6637ad45457085f0977f18cd7f64ab3ed/hook/routeguidance).
