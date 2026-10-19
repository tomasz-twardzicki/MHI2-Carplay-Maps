# MU1427 route-guidance B2 test

> Historical test procedure. Use [INSTALL.md](./INSTALL.md) for the released package. Obsolete test tools are retained in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

**Experimental; passed the initial on-unit test on 2026-10-17.** Both C2
captures completed, with 135 route updates and 32 maneuver updates in the
cumulative log, no B1 receive errors, and a clean route-stop transition. The
user reports CarPlay still works after reconnecting. See
[B2-RESULTS.md](./B2-RESULTS.md) for evidence and remaining coverage gaps.
B2 still only logs guidance; there is no native cockpit-arrow or PPS/HMI
implementation. The procedure below also applies to further coverage tests.

## What C1 established

- The currently installed driver/config and both local backups match the OEM
  SHA-256 fingerprints. Rollback restored the originals exactly.
- B1 sent one `0x5200`, and the phone returned six `0x5201` updates, naming
  **Google Maps** as the source. No `0x5202` / `0x5204` occurs in that saved log.
- Each update immediately triggered `Invalid packet`. The stock reply-table
  lookup rejects unregistered IDs with positive `EINVAL` (`22`). The transport
  interprets a positive return as a retained reply and does not recycle its
  receive buffer. Six such losses are followed by empty-pool waits and 30
  unacknowledged sends of the same outgoing LocationInformation sequence.
- The B1 receive hook at `0x13470` was after this rejection, so it never ran.
  The saved process snapshot shows `mm-ipod` alive, `mount` blocked sending to
  it, and a CarPlay shutdown timeout. This was not evidence of an immediate
  driver process crash.

B2 replaces the call to `link_handle_reply` at **`0x133a0`**, before that gate.
It handles only valid semantic `0x5201`, `0x5202`, `0x5204` frames, logs their
TLVs and returns zero. Stock ACK/sequence handling and the normal receive-buffer
return path remain in use. Every other ID, including malformed frames, is
delegated to the original function; unrelated stock unknown-ID behavior is not
changed. The identification component and start-request bytes are unchanged.

## Build and offline checks

Use the original driver/config from the factory package or C1's `files/`
directory (`stock-driver.so` and `stock-iap2.cfg`). The builder verifies their
SHA-256 on the computer. Host requirements: Python 3, pyelftools, unicorn, clang
with the ARM assembler, and ksh for installer tests.

```sh
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-driver.py "$DRIVER"
python3 MU1427/route-guidance/test-capture.py
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/build-test-package.py "$DRIVER" "$CONFIG" --output MU1427/route-guidance/build-B2
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-install.py "$DRIVER" "$CONFIG" MU1427/route-guidance/build-B2/sd-card/Custom/route_guidance_b1
```

ARM tests reproduce the old leak using the real stock lookup and transport
return branch, then pass 1,000 B2 guidance frames at each of two load addresses
without losing a buffer. They check original now-playing dispatch, fallback
handling, TLV encoding and register/stack preservation. USB/ACK scheduling and
OS calls are mocked; this does not establish on-unit stability.

The installer tests use only the base toolbox's file utilities in PATH and
cover original backup adoption, repeat install, missing/damaged active files,
copy/rename failures and rollback through the saved local script without SD.
C2 collector tests include bounded log growth, skipped FIFOs/symlinks and
selection of a newer OEM error archive.

## Install and test while parked

1. Extract **`MU1427-route-guidance-B2-toolbox.zip`** to the SD root and
   **update the toolbox again**. The menu must say **install route guidance B2**.
   B2 includes the focused **C2** collector; do not use an older toolbox copy.
2. Disconnect the phone. Run **EXPERIMENTAL MU1427: install route guidance B2**.
   Confirm **`B2-install-r1`**, then **`CPMAP_RGI_INSTALL_OK`**. The existing
   map-video installation stays installed. C1 already verified the OEM state,
   so there is no need to restore factory files again before this install.
3. Exit and do one **full unit reboot**, then connect the iPhone. Start a route
   in the same app used for B1 (the log identifies Google Maps). Wait 30–60 s.
4. **While the route is still active**, run **Capture route-guidance data to SD
   (C2)**. Confirm `CPMAP_RGI_CAPTURE_OK`. Save `Log/cpmap-navrecon-C2-*`.
5. End the route, wait 15 s and collect again. Check music metadata and CarPlay
   still work. Unplug/replug once and repeat to check a fresh session. If stable,
   an additional Apple Maps route may supply maneuver/lane frames not seen in B1.

Acceptance: `CPMAP_RGI_START B2 ... rc=0`, then `CPMAP_RGI_RX B2 id=0x5201`
and its TLVs; no `Invalid packet` immediately after valid guidance messages;
normal location ACKs and other traffic continue after more than six updates;
CarPlay remains usable through route end and reconnect. `0x5202` / `0x5204`
depend on what the navigation app sends. The stock printer may still label the
group `--?--`; that label alone is not rejection.

C2 copies the live iAP2 log first, skips mount enumeration and live PPS, and
selects the newest numbered OEM smartphone error (42 or later). It uses the
same firmware-verified `dd` bounds as the successful C1 capture. Captures contain
private route/device data: keep them out of git.

If CarPlay fails, capture before rebooting if possible, then restore using
**Restore factory iAP2 driver and config (B1/B2)** and reboot. Do not repeat B1.

## Rollback

The original backup location and local recovery filename are retained for
compatibility: `/mnt/app/route-guidance-b1/`. B2 adopts valid originals from the
rolled-back B1 installation and refreshes its recovery script; it does not
overwrite the OEM backup files. Its rollback works without SD, a build marker,
or valid current driver/config files. From an MMX shell:

```sh
/bin/ksh /mnt/app/route-guidance-b1/rg-b1.sh restore
```

From RCC prefix that script path with `/net/mmx`. Wait for
`CPMAP_RGI_RESTORE_OK` and fully reboot. The lock is in `/ramdisk`, so reboot
clears an interrupted operation's lock. Runtime checks use OEM/payload sizes;
they do not detect same-size corruption. Host SHA-256 checks remain available.

| File | OEM bytes | B2 bytes |
| --- | ---: | ---: |
| `ipod-drvr-iap2.so` | 739925 | 741944 |
| `iap2.cfg` | 5905 | 6006 |

B2 driver SHA-256:
`0763b7aa448837651ca59ce8d3e219c0b157df05204c9a2037f895001b1655b6`.
The config is byte-identical to B1's config, including its historical comment.
