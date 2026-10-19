# MU1427 B3 publication test

**Historical B3 test: file reads worked, but publication stayed disabled.**
See [B3-RESULTS.md](./B3-RESULTS.md) for the lifecycle defect and
[TEST-B4.md](./TEST-B4.md) for the corrected test package. Do not repeat B3 to
test publication. The original procedure below is retained for the record.
B3 retains B2's guidance reception
and adds the bounded read-only `/dev/ipod0/rgi-events` handoff described in
[PUBLICATION.md](./PUBLICATION.md). No native cockpit output or background
consumer is enabled. The full toolbox includes the focused C3 collector.

## Install from the working B2 state

1. Extract `MU1427-route-guidance-B3-toolbox.zip` to the SD root and **update
   the toolbox again**. Check that the menu says **install route guidance B3**
   and **Capture route-guidance data to SD (C3)**.
2. Disconnect the iPhone. Run **EXPERIMENTAL MU1427: install route guidance B3**.
   Confirm **`B3-install-r1`** and **`CPMAP_RGI_INSTALL_OK`**.
3. Exit the toolbox and perform one full unit reboot. Connect the phone and
   check normal CarPlay startup.

**No factory restore is required before this upgrade.** The installer accepts
the known active B2 driver/config with its matching B2 marker and valid OEM
backups. It retains the same originals and recovery path. It also accepts the
restored OEM pair. Unknown/B1 active driver sizes or mismatched patched-build
markers are rejected before activation. On-unit checks use the base toolbox's
`ls -ln` sizes; host builders verify exact OEM hashes. Same-size corruption is
not detected by the on-unit size checks.

## Collect while parked

1. Start a Google Maps route, as in the successful B2 test. Wait 20–30 seconds.
2. Run **Capture route-guidance data to SD (C3)** while guidance is active.
   Confirm `CPMAP_RGI_CAPTURE_OK`. Save `Log/cpmap-navrecon-C3-*`.
3. Leave guidance running another 20–30 seconds and capture again. This checks
   that sequence numbers advance and a second snapshot read does not stall
   CarPlay. The rolling window only retains the last sixteen events.
4. Stop guidance, wait 5–10 seconds and collect once more. Check CarPlay still
   responds, then unplug/replug and check it starts again. If practical, start
   another route and collect after reconnect to verify the new session/instance.

C3 first preserves the live iAP2 log, then makes **one** snapshot read with
`dd bs=65536 count=1`. It expects exactly **33,088 bytes** in `rgi-events.bin`.
It does not enumerate mounts, read PPS, recurse through devices or retry an
`EAGAIN` forever. A missing file, failed read or wrong size produces
`CPMAP_RGI_CAPTURE_PARTIAL` while preserving the rest of the diagnostics.

Acceptance on the computer:

- Active driver hash matches B3; original backups still match OEM.
- `CPMAP_RGI_START B3 ... rc=0` and `CPMAP_RGI_RX B3` continue without B1's
  packet rejection/send-failure/empty-pool errors.
- All `rgi-events.bin` files decode; fault is zero and sequence advances
  between the two active captures. A late first snapshot or widely spaced
  captures normally report missing history; that alone is not producer failure.
- Ending guidance yields state-zero updates in the window and full iAP2 log.
  Old maneuver data must not survive a detected gap or stopped route.
- CarPlay remains usable through both captures, stop and reconnect.

A snapshot may have no current maneuver because its metadata arrived before
the retained window. Use the complete iAP2 log to evaluate full-route decoding;
the one-shot collector is not a continuously polling cache. If the snapshot
file is absent, retain the capture: it distinguishes filesystem initialization
failure from guidance reception failure.

```sh
python3 MU1427/route-guidance/rgi_publication.py "$CAPTURE/rgi-events.bin"
python3 MU1427/route-guidance/rgi_decode.py "$CAPTURE"
```

All captures contain private route/device data. Keep them out of git.

## Rollback and recovery

Use **Restore factory iAP2 driver and config (B1/B2/B3)**, then fully reboot.
The saved local helper also works without SD and without valid active files:

```sh
/bin/ksh /mnt/app/route-guidance-b1/rg-b1.sh restore
```

From RCC prefix the path with `/net/mmx`. Wait for `CPMAP_RGI_RESTORE_OK` and
reboot. The originals are not overwritten by a B2→B3 upgrade. If the second
activation rename fails, automatic recovery restores the OEM pair; it does not
attempt to reconstruct B2. If automatic restore fails, originals remain in
place for a retry using the local helper. Reboot clears the `/ramdisk` lock.

To return specifically to B2: restore OEM with the current B3 helper, reboot,
update the toolbox from the preserved B2 ZIP, reinstall B2 and reboot. The old
B2 installer intentionally rejects an active B3-sized driver.

| File | OEM bytes | B2 bytes | B3 bytes |
| --- | ---: | ---: | ---: |
| `ipod-drvr-iap2.so` | 739,925 | 741,944 | 743,148 |
| `iap2.cfg` | 5,905 | 6,006 | 6,006 |

B3 driver SHA-256:
`bfd79ed0c1a86d7ed48837d6ec4c766f2be024366d8376ceb730a1403854741d`.
Config is byte-identical to B2. The published map-video runtime is unchanged.

## Rebuild and validate on the computer

Host dependencies are the same as B2: Python, pyelftools, Unicorn, clang ARM
assembler, and ksh for shell tests. `DRIVER` and `CONFIG` are the exact OEM files.
Choose a fresh output directory:

```sh
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-publication.py "$DRIVER"
python3 MU1427/route-guidance/test-rgi-decode.py
python3 MU1427/route-guidance/test-rgi-publication.py
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/build-publication-package.py "$DRIVER" "$CONFIG" --output MU1427/route-guidance/build-B3
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-install-b3.py "$DRIVER" "$CONFIG" MU1427/route-guidance/build-B3/sd-card/Custom/route_guidance_b1
python3 MU1427/route-guidance/test-capture-b3.py MU1427/route-guidance/build-B3/sd-card/Toolbox/scripts/cpmap_navrecon.sh
```

ARM tests mock OS/iofunc behavior and bypass B2's unchanged ACK scheduling.
They establish neither hardware filesystem registration nor full CarPlay
stability. The parked test above is the next required validation.
