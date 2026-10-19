# C4-2 on-unit result (reviewed 2026-10-18)

**C4-2 passes continuous recording, sustained maneuver selection, distance
progression, route-stop clearing and recovery on a new connection.** The user
confirms an outdoor run through ordinary turns, normal AID turn cards and
route line, and no reconnection issues. All 240 published events in the two
observed allocations are recorded, with no producer fault or worker failure.

The B4 driver and C4 recorder are unchanged. This validates the diagnostic
handoff/reader for this run, not native cockpit output, arbitrary burst
retention or long-duration operation. No PPS/HMI output is enabled.

## Inputs and duplicate exclusion

Private inputs are under `Logs/C4/C4-2/`. The new captures are:

- `cpmap-rgi-C4-4526211`: the continuous journal and final recorder status.
- `cpmap-navrecon-C3-4931652`: the later connection's text log and snapshot.

The directory also contains `cpmap-rgi-C4-5173328` and
`cpmap-navrecon-C3-5509188`. Their journals/logs/snapshots match the original
garage captures byte-for-byte. They are excluded from the new-run totals;
see [C4-RESULTS.md](./C4-RESULTS.md). Raw logs, position, road/destination
data and authentication material remain outside the repository.

## Recorder completion and coverage

Build marker: `MU1427-RGI-C4-603b9a14`. The 249,718-byte journal passes strict
replay, including `--require-complete`, and ends at **194.201 seconds** with
reason **1: manual stop**, followed by `CPMAP_RGI_C4_EXPORT_OK`. Final status
reports 1,814 polls, 1,465 valid reads, 349 unavailable reads and sequence 63.
There are 112 changed snapshots, 101 active snapshots and 83 ending with a
resolved current maneuver. No malformed publication, producer fault, worker
deadline, worker EOF, capacity end or output-failure end is recorded.

| Allocation (monotonic sec, nsec) | Session | Changed snapshots | Final sequence | Unique records retained |
| --- | ---: | ---: | ---: | ---: |
| `(129, 742000000)` | 1 | 77 | 177 | 177 |
| `(255, 848000000)` | 1 | 35 | 63 | 63 |

Coverage is **240 recorded / 240 published / 0 unrecorded**, comprising 194
route `5201` and 46 maneuver `5202` records. No lane `5204` records arrive.
Overlapping slot/TLV bytes agree. All sequences from 1 to each allocation's
last sequence are present, with no unknown field IDs.

Two source-open `ENOENT` episodes occur: before initial connection at 0.016
seconds, and on disconnect at 105.233 seconds. The new allocation is read at
134.548 seconds, an observed source-absence interval of 29.315 seconds.
This does not time USB enumeration or individual cable operations. The user
reports normal recognition, unlike the first test's repeated insertions.

Six stale markers occur before guidance, after route stops or during source
absence; none interrupts a sustained active interval. Heartbeats are
separated by 1.000–1.095 seconds. These show recorder progress, not a CPU-load
measurement or a worst-case bound on every device request.

`missing_before_windows` is 64 because the consumer resets after staleness
and later reconstructs a window beginning at sequence 65. This is not capture
loss: all those older events are already in the journal. Eight retained
events are processed again, giving 248 consumer events versus 240 unique
records. Independent `coverage` correctly reports zero gaps.

## Current maneuvers and distances

As in earlier tests, startup briefly supplies a current list, then reports
stopped/loading and resumes without one. **Fresh lists now arrive later in
each sustained guiding episode**, so the reader selects a current maneuver
without carrying stale selection across the reset:

| Episode | Resumed guiding observed | Fresh selected head observed | Sustained head progression | Stop observed |
| --- | ---: | ---: | --- | ---: |
| First allocation, first route | 27.897 s | 35.120 s | 0 → 1 → 2 | 55.197 s |
| First allocation, second route | 68.786 s | 76.061 s | 3 → 4 → 5 → 6 | 100.866 s |
| New connection | 145.314 s | 145.844 s | 2 | 173.635 s |

Times are captured-window observation times, not per-message wire timestamps.
For the first sustained route, fresh list sequence 37 selects index 0
(`START_ROUTE`), 41 selects index 1 (right turn), and 44 selects index 2
(left turn). Later lists select indices 3–6. On the new connection, sequence
27 selects index 2 (right turn). Transient missing heads while records arrive
remain unknown; no substitute prefetched entry is selected.

The source is Google Maps. Route messages contain 130 current-list fields
and 109 maneuver-distance fields across the two allocations. Distances
change and decrease within selected heads in both allocations. Some upward
corrections also occur; do not assume every distance sequence is monotonic.
Stop updates clear route-specific data and both caches. The final observed
state is stopped, and recorder termination also invalidates its state.

The 46 maneuver records include nine explicit exit angles (seven zero,
two −90 degrees) and four between-maneuver distances. Junction types include
intersection and roundabout records; no junction-angle arrays are supplied.
Zero angles remain present values, distinct from absent angles. This adds
useful mapping evidence but does not validate a VW icon mapping or lane
renderer.

## Companion C3 and installation integrity

C3 reports `CPMAP_RGI_CAPTURE_OK` and `CPMAP_NAVRECON_OK`, with every scheduled
copy completed. Its 118,636-byte text log contains 63 guidance messages:
53 route and ten maneuver updates. **All 63 message IDs and raw TLV payloads
match their exact sequences in C4's second allocation.** Strict text replay
has no malformed/interleaved records or rejected updates. Identification is
accepted once and the `5200` start queues successfully. There are no
`Invalid packet`, `Failed to send packet`, `No packets in receive list` or
`IdentificationRejected` errors.

The final 33,088-byte C3 snapshot is enabled, fault-free, sequence 63 and
stopped. Its header equals C4's last header; all sixteen retained events
match the journal. Its 73 GGA sentences have quality `1`, and all 73 RMC
sentences have status `A`; every counted sentence has a valid checksum.
This is later-connection evidence only. It contrasts with the garage
companion's GGA quality `0`, but does not prove why the first run lacked a
current list or establish what position the phone actually used.

Both new captures retain the exact B4 driver (743,196 bytes, SHA-256
`3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b`)
and patched config (6,006 bytes). C3's OEM backups match the factory
fingerprints in [B2-RESULTS.md](./B2-RESULTS.md). OEM error 42 is the unchanged
historical B1 archive; the directory lists no archive numbered above 42.
No reinstall or rollback was exercised.

Input SHA-256:

- Journal: `719e37549580ea20a888769a68a1e1d65e93d4ff31c1d432c39907fc7dd3dc2d`
- Text log: `b4b3986805ae6fcb1dc1c7c61fb33eabf793621770ff1bc524e84f1e00faf4f4`
- C3 snapshot: `e61d630d2699c900df280904a0e2fc94355dfddba722cfc286757c9bde70f904`

## Acceptance and next implementation

The garage run's sustained missing-list behavior is not reproduced here.
The existing conservative cache receives fresh post-reset lists, follows
their ordered head, observes distance progression and clears on route stop.
The user's visual/reconnect confirmation completes acceptance for C4-2.
The first run's one overwritten event still demonstrates that the sixteen-slot
handoff is not guaranteed lossless for every possible burst.

No driver or recorder change is justified by this result. Keep B4 installed.
The subsequent [native mapping/bridge model](./NATIVE-BRIDGE.md) now implements
offline VW maneuver projection, ownership, replacement and clear/handback
semantics against the exact factory interfaces. The subsequent
[D1 consumer/Java adapter](./LIVE-BRIDGE.md) is prepared for its own
[shadow/live unit test](./TEST-D1.md), outside the iAP2 receive hook.

An optional private C4-2 regression in `test-observer.py` checks complete
coverage, fresh post-reset selection, indices 0 → 1 → 2, decreasing distance,
selection after reconnect and final clearing. All 18 journal tests pass with
the private B4, original C4 and C4-2 replays enabled. No private payload is
embedded in the tests or printed.
