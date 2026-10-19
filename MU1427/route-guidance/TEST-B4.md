# MU1427 B4 publication activation test

**Experimental; publication validated in four on-unit captures.** See
[B4-RESULTS.md](./B4-RESULTS.md) for progression, stop clearing, a later
connection and the text-log interleaving limitation. The procedure below
remains available for installation, retesting and rollback.

B3 proved that the virtual file
and C3 reads work, but identification ran before its pool existed, leaving
publication disabled. B4 enables the pool after native filesystem initialization
and before the unchanged `5200` send. See [B3-RESULTS.md](./B3-RESULTS.md).
The receive path, wire format, video runtime and C3 collector are unchanged.
No native cockpit/PPS/HMI consumer is enabled.

## Install

1. Extract `MU1427-route-guidance-B4-toolbox.zip` to the SD root and **update
   the toolbox again**. Check **install route guidance B4** and **Capture
   route-guidance data to SD (C3)**. The collector stays C3 deliberately.
2. Disconnect the iPhone and run **EXPERIMENTAL MU1427: install route guidance
   B4**. Confirm `B4-install-r1` and `CPMAP_RGI_INSTALL_OK`.
3. Exit the toolbox, fully reboot the unit, then connect the iPhone.

**No factory restore is needed before upgrading from the known B3 or B2 pair.**
Their matching build markers and valid OEM backups are required. A restored
OEM pair is also accepted. Original backups are retained and the local restore
helper is refreshed. Unknown sizes or mismatched patched-build markers are
rejected. Runtime checks use the established `ls -ln` sizes; they cannot detect
same-size corruption. The builder checks the exact factory hashes on the host.

## Test while parked

1. Start a Google Maps route. After 20–30 seconds, run **Capture route-guidance
   data to SD (C3)** and save `Log/cpmap-navrecon-C3-*`.
2. Leave guidance active for another 20–30 seconds and capture again.
3. Stop guidance, wait about 5 seconds and capture a third time. Check normal
   CarPlay operation, then reconnect the phone. An additional active-route
   capture after reconnect is useful if practical.

The essential change in acceptance is that an **active-navigation snapshot
must have `enabled=1`, session greater than zero, and sequence greater than
zero**, with `fault=0`. A 33,088-byte file containing all-zero counters is a
failed publication test even if the collector reports success.

The two active snapshots should show increasing sequence numbers for the same
allocation/session. A rolling-history gap is expected when more than sixteen
events arrive between captures. After stopping the route the publication
channel normally remains enabled; it should contain state-zero route updates.
Publication enablement is separate from whether navigation is active.

On the computer:

```sh
python3 MU1427/route-guidance/rgi_publication.py "$CAPTURE/rgi-events.bin" --expect-publishing
python3 MU1427/route-guidance/rgi_decode.py "$CAPTURE"
```

Also check `CPMAP_RGI_START B4 ... rc=0`, continuing `CPMAP_RGI_RX B4`, and no
B1-style packet rejection/send-failure/empty-pool errors. C3 still reads the
live iAP2 log first and makes one bounded snapshot request, without a retry
loop, mount listing or PPS scan. Keep all raw captures private.

If the first-attempt visual issue recurs, keep that capture and note whether
the route line/card appeared before or after reconnect. The B3 evidence does
not yet assign that symptom to the iAP2 patch; no speculative video change is
included in B4.

## Restore

Use **Restore factory iAP2 driver and config (B1/B2/B3/B4)**, then fully reboot.
The local recovery command works without SD or valid active files:

```sh
/bin/ksh /mnt/app/route-guidance-b1/rg-b1.sh restore
```

From RCC prefix the path with `/net/mmx`. Wait for `CPMAP_RGI_RESTORE_OK`.
A failed second activation rename restores the OEM pair. If automatic rollback
fails, keep the original backups and retry the saved local helper; reboot
clears the `/ramdisk` lock. To reinstall an older patch, restore OEM with the
current helper first, reboot, then use that older toolbox/install procedure.

| File | OEM bytes | B3 bytes | B4 bytes |
| --- | ---: | ---: | ---: |
| Driver | 739,925 | 743,148 | 743,196 |
| Config | 5,905 | 6,006 | 6,006 |

B4 driver SHA-256:
`3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b`.

## Host rebuild/checks

Passed: 25 ARM tests (including both private integration replays), 28
installation/rollback tests, 11 unchanged C3 collector tests, 46 decoder/state
tests and 11 publication-reader tests. The installer tests include direct B3
and B2 upgrades, mismatched markers, failure recovery and local rollback.

Use exact OEM `DRIVER` and `CONFIG`, and a fresh output directory:

```sh
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-activation.py "$DRIVER"
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/build-publication-package.py "$DRIVER" "$CONFIG" --revision B4 --output MU1427/route-guidance/build-B4
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-install-b4.py "$DRIVER" "$CONFIG" MU1427/route-guidance/build-B4/sd-card/Custom/route_guidance_b1
python3 MU1427/route-guidance/test-capture-b3.py MU1427/route-guidance/build-B4/sd-card/Toolbox/scripts/cpmap_navrecon.sh
python3 MU1427/route-guidance/test-rgi-decode.py
python3 MU1427/route-guidance/test-rgi-publication.py
```

The ARM suite includes native-order B3 failure reproduction and B4 correction.
Set `CPMAP_PRIVATE_B2_LOG` and `CPMAP_PRIVATE_B3_LOG` to the respective cumulative
private logs for the optional 167- and 277-message integration replays. OS and
ACK scheduling boundaries remain mocked. B4's captured hardware results are
recorded separately in [B4-RESULTS.md](./B4-RESULTS.md); they do not establish
continuous-reader behavior or on-unit B4 rollback.
