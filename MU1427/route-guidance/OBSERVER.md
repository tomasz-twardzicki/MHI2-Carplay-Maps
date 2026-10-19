# C4 continuous diagnostic reader

C4 reads the tested B4 virtual file from a separate process. It adds manual
toolbox controls and an offline replay tool; it does not change the driver,
config, OEM backups, video bridge, HMI or boot startup. Use
[TEST-C4.md](./TEST-C4.md) for the procedure and follow-up. The first
[on-unit recording](./C4-RESULTS.md) completed 2,369 polls over 251.577 seconds,
survived source removal/reappearance and retained 236 of 237 published events,
with no producer fault or worker deadline. One startup burst exceeded the
sixteen-slot window. The [C4-2 follow-up](./C4-2-RESULTS.md) retains all 240
published events and observes sustained maneuver/distance progression,
route-stop clearing and reconnect recovery. The user confirms normal
outdoor guidance and reconnection. This validates the diagnostic reader in
these runs, not native output, arbitrary bursts or long-duration operation.

## Runtime boundaries

`observer/observer.c` runs on MMX. A supervisor starts one worker and the worker
reopens `/dev/ipod0/rgi-events` every 100 ms, makes one 33,088-byte read, closes
it and sends the result through a private pipe. All device open/read/close
operations are confined to the worker. If no complete result arrives for
1,500 ms, the supervisor invalidates guidance, kills the worker and ends the
recording. It never waits indefinitely for the worker to exit. A dead
supervisor closes the pipe, causing the worker to exit on its next write.
Pipe writes are at most 512 bytes and the supervisor drains nonblocking data
before waiting for readiness. Its device deadline starts after output setup,
so creating the journal cannot consume the first request's time budget.

The supervisor validates the whole publication envelope, slot identities,
lengths and top-level TLV boundaries before recording a compact snapshot.
The host decoder additionally checks semantic field widths, text, nested
lane TLVs and guidance state. There is no native maneuver renderer or state
publisher in this diagnostic version.

Unchanged snapshots are deduplicated. Five seconds without a changed
publication header produces a stale marker; repeated successful reads of
the same bytes do not refresh guidance. After a read failure, recovery of the
same old header cannot revive guidance either: a changed publication is
required. The host reader clears cached state on staleness, read failure,
session/allocation changes, history gaps, producer faults and recorder end.
Five seconds is a conservative diagnostic deadline, not a protocol promise
that a stationary phone must send new guidance that often.

The recorder runs for at most **300 seconds** from the toolbox (the CLI caps
any run at 600 seconds). Its journal is capped at **8 MiB**, reserving space
for an end record. Status is replaced atomically once per second and at
shutdown. Files are private (umask 077) in `/ramdisk/cpmap-rgi-C4`; the binary
is `/ramdisk/cpmap-rgi-observer-C4`. No recording is written to SD while
polling. Export first confirms shutdown, then copies bounded regular files
with the same firmware-verified `dd` options used by C3. RAM data is retained
until explicit removal or reboot.

Control scripts use the existing toolbox commands and `ls -ln` sizes. `chmod`
is also verified in the exact MMX stage2 firmware (`bin/chmod`, 14,030 bytes).
The executable handles background startup and stop deadlines itself; no
shell `nohup`, fractional `sleep`, `timeout`, process-name killing or hash
utility is introduced. Start checks the B4 driver/config sizes and matching
saved build marker. Stop/removal do not require SD or a valid active driver.
Size checks have the same same-size-corruption limitation as the B4 installer.

## Journal and replay

`events.rgj` starts with four little-endian words: ASCII `RGJ1`, version 1,
expanded snapshot size 33,088 and poll interval 100 ms. Each record has eight
little-endian words: kind, elapsed monotonic milliseconds, payload size,
detail and four zero reserved words.

| Kind | Payload / detail |
| ---: | --- |
| 1: snapshot | Original 64-byte publication header, then retained slots in sequence order, each truncated to its 16-byte slot header plus declared TLV bytes; detail 0 |
| 2: unavailable | Detail: 1 open, 2 read/close, 3 short read, 4 invalid envelope, 5 worker deadline, 6 worker EOF; optional u32 source errno |
| 3: stale | No payload; detail 5,000 ms |
| 4: heartbeat | No payload; detail last observed sequence; emitted about once per second |
| 5: end | No payload; detail 0 duration, 1 stop requested, 2 capacity, 3 worker failure, 4 output failure |

Reconstruction restores slots to their ring positions with zero padding, then
uses the existing `rgi_publication.Consumer`. Snapshot data is validated
before applying any of its events. Monotonic times, total size, record bounds,
reserved fields and a final end record are checked. A missing end record is
an incomplete capture, not success. Capacity/deadline/output termination,
no publishing snapshots, or any producer fault makes the CLI exit nonzero.
Temporary source absence during phone reconnect is recorded and can recover.

```sh
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj"
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --events > /tmp/c4-events.jsonl
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --messages > /tmp/c4-messages.jsonl
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --require-complete
```

Default output omits private route text, distances, times and opaque lane
bytes. `--include-private` is opt-in. The binary journal still contains private
route data; keep all captures outside git. `last_observed` is historical;
`final` is invalidated when the recorder ends and must not drive a live HMI.

The host summary now includes `coverage`, measured independently of consumer
resets by allocation/session/sequence. `published_events` sums the highest
observed sequence in each publication; `recorded_events` counts unique
retained events; `unrecorded_events` is their difference. This measures only
publications and sequence ranges actually observed, not traffic after
recording ends or a connection missed entirely. `recorded_by_id` counts unique
records and `gap_windows` counts newly observed sequence gaps. Overlapping
records must have identical slot-header/TLV bytes, and a sequence regression
is rejected even after a stale reset. Only the latest sixteen records per
publication are retained for overlap checking. `--require-complete` adds a
nonzero exit for any unrecorded sequence; ordinary replay still distinguishes
a completed but partial capture from a recorder failure.

`missing_before_windows` retains its original meaning: consumer missing
history after resets as well as actual coverage gaps. Applied-message counts
can include records replayed after a stale reset. For the first C4 capture,
coverage is 236 recorded / 237 published / 1 unrecorded even though the
consumer counter is 118. See [C4-RESULTS.md](./C4-RESULTS.md).

`--messages` emits state after every newly processed consumer event, retaining
transient head selection followed by a stop inside one captured window.
Each record has the publication instance/session/sequence, message ID, field
names and state; raw fields remain private by default. `elapsed_ms` is the
window's observation time, shared by all its events, not wire receive time.
Events processed again after a reset are emitted again; this stream is a
consumer trace, not unique coverage. `message_selection_states` counts those
intermediate states. The original `--events` and resolved-snapshot counts
still describe state at the end of each window.

`current_maneuver_status` distinguishes `inactive`, `order_absent`,
`order_empty`, `head_not_cached` and `head_cached`. A cached head is decoded
protocol data, not proof that its type/geometry can generate a native arrow.
These additions run on the host and require no SD update or new unit binary.

## Build and verification

The build uses Apple clang's ARM code generator and the original QNX 6.5
linker/CRT/sysroot from
[luka-dev/qnx65-armv7-toolchain](https://github.com/luka-dev/qnx65-armv7-toolchain),
pinned to commit `baa45224f18ae6b13c2e9c77c6663bb8181eb6a1`. Only its minimal
`qnx-sdp` container stage is needed; no new GCC, Go or Rust build is necessary.
Toolchain sources stay outside this repository. An isolated Colima profile
`cpmap-rgi` holds these build images; the ordinary Docker context is unchanged.

The ARM object uses the actual QNX headers, base softfp calling convention,
int-sized enums and strict alignment. Builtins are disabled so clang retains
the stock libc memory calls instead of introducing compiler-runtime imports.
The original QNX linker selects `armnto`, emits its QNX note and links the
stock CRT. The result depends only on `/usr/lib/ldqnx.so.2` / `libc.so.3`.

`build-observer.py` extracts the real MMX stage1 libc directly from the
provided firmware (deflate wrapper followed by imagefs), checks SHA-256
`775139dc7381b8aa7001330dafe93b5cb8b0f779eb8e97d5ee32ca93bb85d2f1`,
and verifies every required dynamic import against that library's exports.
It rejects hard-float output, extra library dependencies, runtime search paths
and text relocations. Containers mount only the dedicated output directory
and run without networking during linking/testing.

```sh
git clone https://github.com/luka-dev/qnx65-armv7-toolchain /tmp/mu1427-qnx65-toolchain
git -C /tmp/mu1427-qnx65-toolchain checkout baa45224f18ae6b13c2e9c77c6663bb8181eb6a1
colima start --profile cpmap-rgi --cpu 2 --memory 2 --disk 12 --activate=false
docker --context colima-cpmap-rgi build --target qnx-sdp -t cpmap-qnx65-sdp /tmp/mu1427-qnx65-toolchain
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/build-observer.py /tmp/mu1427-qnx65-toolchain "$FIRMWARE" --output MU1427/route-guidance/build-C4-native
python3 MU1427/route-guidance/test-observer.py
python3 MU1427/route-guidance/test-observer-control.py
docker --context colima-cpmap-rgi build -f MU1427/route-guidance/observer/Dockerfile.qemu -t cpmap-qemu-arm MU1427/route-guidance/observer
/tmp/mu1427-rg-venv/bin/python MU1427/route-guidance/test-observer-qnx.py /tmp/mu1427-qnx65-toolchain "$FIRMWARE"
python3 MU1427/route-guidance/build-observer-package.py MU1427/route-guidance/build-C4-native --qnx-result MU1427/route-guidance/build-C4-qnx-check/result.json
```

Use fresh output directories. The package builder verifies the exact tested
B4 ZIP before extending its menu. It compares every preserved B4 file against
the seed, including the driver, config, installer and rollback helper. Source,
GPL license, compiler identity, toolchain commit, native fingerprints and
verified imports accompany C4.

**Native package preparation passed:** 20 standard journal/process tests, both optional private B4
replays (22 total), eight control/export tests and execution of the exact ARM
binary on QNX under native ARM64 QEMU. The QNX run uses the factory MMX libc
and pipe service, obtains 30 valid snapshots with no invalid frames, and
checks foreground recording, daemon startup and explicit stop. The package
builder requires a passing QNX result bound to the exact reader hash.

The QEMU boot image uses the pinned BSP/kernel plus an ephemeral RAM disk;
its cache-noop and `sync=none` settings are test setup only. QNX documents
the latter for devices without persistent synchronization support in
[fs-qnx6.so](https://qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_utilities/f/fs-qnx6.so.html).
The runtime emulator is ARM64-native to avoid nested x86 emulation distorting
the deadline test. Device reads in this smoke test use a synthetic regular
file; [C4-RESULTS.md](./C4-RESULTS.md) separately records the first live B4
virtual-file polling run and its coverage limits. Long-duration operation
remains untested. The checked-in B4 driver/read hooks are unchanged.

Host tests cover journal reconstruction, stop/gap/stale/disconnect invalidation,
privacy and strict rejection, plus real processes for deduplication, missing
source, short reads, corrupt headers, background start/stop, duplicate start,
read recovery without progress, capacity and a deliberately blocked worker.
Control tests use only the verified utilities in PATH and exercise refusal,
complete export, failed export/retry, removal and recovery without SD/payload.
Set `CPMAP_PRIVATE_B4_DIR` for two optional private replays: all four B4
snapshots through journal replay and through the real C worker/packer, with
consumer states compared to direct snapshot decoding. No raw data is printed
or committed.

Set `CPMAP_PRIVATE_C4_DIR` for the optional first-C4 journal regression. It
checks true sequence coverage and the transient selected head / stop /
missing-order startup trace without embedding private capture data in tests.

Host verification before the C4-2 regression passed **47 decoder + 13 publication + 28 observer
tests**, including both private B4 replays and the private C4 journal replay.
The new tests cover reset-independent coverage, immutable overlap checks,
regression across staleness, intermediate selection, privacy and CLI exit
semantics. The native recorder source and tested unit payload are unchanged.

Set `CPMAP_PRIVATE_C4_2_DIR` for the later journal regression. It selects only
the new recording (the supplied directory also contains old duplicates),
checks complete coverage and fresh selection after reset, maneuver/distance
progression, recovery on reconnect and final clearing. All 18 journal tests
pass with the private B4, C4 and C4-2 journal replays enabled. The production
reader and unit package are unchanged.
