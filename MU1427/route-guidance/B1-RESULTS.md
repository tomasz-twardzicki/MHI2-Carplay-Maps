# B1 on-unit result and recovery capture C1

MU1427 / 791, 2026-10-16. Installation with **B1-install-r3** completed.
After reboot, the iPhone connected, CarPlay started and a navigation route was
started and finished. Research diagnostics then hung twice. CarPlay stopped
working, including reconnects, with a black CarPlay screen. Basic diagnostics
completed. The user restored B1 and rebooted: **CarPlay works again**.

**Do not rerun B1 or the old research collector.** C1 has now recovered the
failure archive: guidance reception is confirmed and the receive-buffer leak
is identified below. B2 fixes that path; see [TEST-B2.md](./TEST-B2.md) for the
test procedure. B2 subsequently passed its initial on-unit receive test; see
[B2-RESULTS.md](./B2-RESULTS.md).

## Original B1 captures (before C1 recovery)

Private input: `Logs/B1/cpmap-navrecon-3334220/`,
`cpmap-navrecon-4567169/` and `cpmap-diag-5283959/`.

- Both research directories contain only `summary.txt` (9,776 bytes), plus
  empty output directories. Both summaries stop at the same partial `/net/`
  line in **the plain `mount` listing**. The collector never reached its process,
  iAP2-log, PPS or driver-copy stages. The hang is not evidence of a PPS read.
- `date` is unavailable in this unit's script environment. The PID fallback
  names worked, but the missing command is another reason to remove it.
- Basic diagnostics show working video until about 224 seconds of runtime,
  followed by stream teardown and the supervisor restoring OEM MOST output.
- At system uptime **00:03:48**, slog records `run fault` for
  `dio_manager.real`, pid **2220145**. At **00:03:49**, the OEM process dumper
  records **`appState=TIMEOUT_SHUTDOWN`** for that process and writes
  **`/mnt/ota/system/logs/smartphone_integrator_error_42`**. Its description
  explicitly includes **`catTail(/dev/shmem/iap2.log)`** and a process dump.
- These captures do not include an iAP2 log or `mm-ipod` thread state. They
  cannot establish a driver crash, whether `0x5200` was sent, whether any
  `0x5201` / `0x5202` arrived, or why the CarPlay shutdown timed out. The fault
  record is not enough to distinguish a spontaneous fault from dump handling.
- A temporal association with the collector is observed; causation between
  the `mount` hang, the driver experiment and the CarPlay failure remains open.

Do not commit raw captures: they can contain GPS, certificates, phone/device
identifiers and other private data. This document contains only the relevant
process/event facts.

## C1 recovered archive and the B1 defect

Private capture: `Logs/B1/C1/cpmap-navrecon-C1-3211332/`. C1 completed and saved
the 251,070-byte `smartphone_integrator_error_42.tar.gz`. It contains the iAP2
log (43,506 bytes), process/thread snapshot, PPS snapshot, CarPlay process core,
slog, and the shutdown-timeout reason.

The active driver and backup both match factory SHA-256 `0ac13f43…`; the active
config and its backup both match factory `ce055243…`. This verifies actual
rollback bytes, beyond the installer's size checks.

The recovered iAP2 log establishes one sent `0x5200` with return code zero,
followed later by **six received `0x5201` updates**. Source name is **Google
Maps**. Every received guidance frame is followed immediately by `Invalid
packet`; none reaches the old `CPMAP_RGI_RX` marker. The next outbound location
frame is repeated **30 times without an ACK**, followed by send failures and
`packet_recvlist_pop: No packets in receive list` messages. No `0x5202` or
`0x5204` is present in this saved log; their absence does not establish that
the app cannot send them because reception then stalls.

The exact stock driver explains this sequence:

1. `link_handle_iap2pkt` calls `link_handle_reply` at **`0x133a0`**, before the
   old B1 hook at `0x13470`.
2. The unknown-ID gate at **`0x11af0`** logs `Invalid packet` and returns
   **positive `EINVAL` (22)** at `0x11b04`.
3. `link_handle_iap2pkt` propagates that nonzero value through `0x1401c`.
4. `transport_recv_pkt` tests the result at **`0x2146c`** and skips
   `packet_recvlist_push` when it is **greater than zero**. Positive values
   normally mean that a reply packet was retained by a waiter. Thus each
   unregistered guidance message loses a receive buffer.

ARM emulation reproduces this using the actual stock lookup and transport
return/recycle branch: a six-buffer harness loses all six after six updates
and cannot receive the next frame. B2 intercepts valid advertised guidance IDs
before the gate and returns zero; the same harness handles 1,000 frames at each
of two load addresses without losing buffers. USB/ACK scheduling is mocked.

The OEM thread snapshot shows `mm-ipod` still alive (pid 2252918), with `mount`
(pid 3416192) blocked in SEND to it. CarPlay's `dio_manager` later times out on
shutdown. This supports a stalled iAP2/resource-manager path rather than proving
a spontaneous process crash. The exact receive-buffer defect is established;
the B2 on-unit test must still verify recovery of the full USB/CarPlay lifecycle.

## Historical C1 recovery procedure (completed)

**C1 is a diagnostics-only toolbox package.** It contains no experimental iAP2
driver or B1 install entry. It retains the B1 status/restore entries and replaces
the old research collector with `capture-rgi.sh`.

1. Extract `MU1427-route-guidance-C1-diagnostics-toolbox.zip` at the SD root and
   update the toolbox. Leave B1 rolled back; no phone connection, route or
   repeat failure is needed.
2. Run **Customization → CarPlay Maps VC → Capture B1 failure data to SD
   (C1, no driver changes)**.
3. Confirm **`CPMAP_RGI_CAPTURE_OK`**. The output is in
   **`Log/cpmap-navrecon-C1-*`**. Copy that directory privately to `Logs/B1/` on
   the computer for analysis. If `OEM_ERROR42_NOT_FOUND` appears, the directory
   listing still shows whether the OEM dump was archived or removed.
4. If the capture stops, preserve its partial output. `progress.txt` and the
   console identify the last attempted file. Do not rerun the old collector.

C1 copies the current iAP2 log first, then the persisted OEM error 42 files and
archives, then the current driver/config and originals for host verification.
It never enumerates global mounts, reads live PPS objects, runs `pidin mem`, or
recursively searches the filesystem. It records each step as it runs.

Only regular files are read. Each `dd` call has a fixed count derived from its
starting size, so a growing log cannot keep the copy reading indefinitely.
Logs have an 8 MiB cap; each OEM dump file has a 64 MiB cap. Oversized files are
skipped and reported, rather than presenting a truncated archive as complete.
These bounds are on bytes, not an OS-level timeout for a blocked storage read.

`/bin/dd` was extracted from the actual MU1427 MMX `mifs-stage2` package:
17,186 bytes, SHA-256
`5e50ebba9a37d93ef9272c1afc88155bd578057e86b0df93784d7a9dc25d6a50`.
Its embedded usage confirms `if=`, `of=`, `bs=` and `count=` support. No
`timeout`, `date`, `cksum` or system `cmp` is introduced.

Host build/test commands:

```sh
python3 MU1427/route-guidance/test-capture.py
python3 MU1427/route-guidance/build-capture-package.py
```

The original C1 archive remains under `build-capture-C1/`. The current collector
and capture-only builder produce C2, which selects the newest numbered OEM
error rather than fixing the selection at 42. The next driver test is B2,
documented in [TEST-B2.md](./TEST-B2.md).
