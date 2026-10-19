# C4 on-unit result (2026-10-17)

**Follow-up:** [C4-2](./C4-2-RESULTS.md), reviewed 2026-10-18, captures all
240 published events and fresh sustained current-maneuver lists, with normal
outdoor guidance/reconnect confirmed by the user. The observations below
describe the original garage run; its sustained missing-list condition is
not reproduced in C4-2.

**The continuous recorder completed normally, including device loss and
recovery on a new connection. Coverage is nearly complete, but this run does
not establish reliable current-maneuver selection for native arrows.** Keep
the tested B4 driver and C4 package. No native cockpit/PPS/HMI output is enabled.

Private inputs are `Logs/C4/cpmap-rgi-C4-5173328` and the subsequent
`cpmap-navrecon-C3-5509188`. Raw route data stays outside the repository.
The user reports testing in an underground garage and confirms that the
first instruction without an arrow matched Google Maps directional guidance
on the phone. They consider that observation probably unrelated to the patch.
Reconnection required three cable insertions before recognition; the cable
is not original. Recovery occurred, but first-attempt reconnect reliability
is not established. The cause of the recognition delay remains unresolved.

## Recorder operation and coverage

Build marker: `MU1427-RGI-C4-603b9a14`. The 237,587-byte journal passes strict
envelope and semantic replay and ends at **251.577 seconds**, reason
**1: manual stop**, followed by `CPMAP_RGI_C4_EXPORT_OK`. Final status:
2,369 polls, 1,479 valid reads, 890 unavailable reads, last sequence 88.
There is no worker deadline, worker EOF, malformed snapshot, producer fault,
capacity end or output-failure end in the journal. Heartbeats are separated
by 1.000–1.099 seconds. These demonstrate progress, not CPU load or the
latency of every poll.

Both unavailable episodes are source-open `ENOENT` (errno 2): before the
first connection at 0.016 seconds, and at 104.982 seconds after the first
allocation disappears. A new source is observed at 186.139 seconds. The 890
unavailable polls are not 890 corrupt snapshots. Five stale markers occur
before initial publication, after route stops or during source absence;
none interrupts the sustained active intervals. Each clears host state.

The observed source-absence interval lasts 81.157 seconds. The user's report
of three cable insertions provides context for this interval, but the journal
does not timestamp individual insertion attempts or capture USB enumeration.
It cannot distinguish cable/contact problems, phone behavior or a software
delay. Do not attribute the delay to the cable or clear the patch on this
evidence alone; the successful new allocation demonstrates eventual recovery.

Deduplicating by allocation, publication session and event sequence gives:

| Allocation (monotonic sec, nsec) | Snapshots | Final sequence | Unique records retained | Missing sequences |
| --- | ---: | ---: | ---: | --- |
| `(118, 714000000)`, session 1 | 88 | 149 | 149 | None |
| `(291, 312000000)`, session 1 | 35 | 88 | 87 | 1 |

Across both allocations C4 retains **236 of 237 published events**: 184 route
`5201`, 40 maneuver `5202` and 12 lane `5204` records. All retained records
validate, with no unknown field IDs; overlapping copies agree. The first
post-reconnect burst advances from sequence 0 to 17 between reads,
overwriting sequence 1 in the sixteen-slot ring. The companion text log
confirms that the missing record is a component-16 route-state-zero update.
All published maneuver and lane records are retained. This is still a real
coverage gap; 100 ms polling cannot guarantee retention of every burst.

The standard replay summary reports **118 `missing_before_windows`** and
250 applied messages. These are consumer reconstruction counters, not unique
journal loss: staleness resets its sequence cursor, so later windows report
62 and 55 older records outside the retained window, plus the one genuinely
unrecorded event. Fourteen previously captured events are applied again after
resets. Do not interpret this as 118 dropped wire messages.

The journal shows four sustained guiding intervals, with stopped states at
53.978, 101.883, 214.525 and 231.015 seconds. These are observation times,
not timestamps assigned to individual wire events. Reconnect changes the
allocation identity and restarts its sequence. Stop, disconnect, stale and
recorder-end handling clear selected host guidance.

## First instruction and current-maneuver limitation

The first indexed maneuver is **index 0, type 11 (`START_ROUTE`)**. It has no
exit-angle or junction-angle TLV. The pinned reference identifies type 11 in
`rgd_tlv.h`; absent geometry remains unknown rather than becoming a fabricated
direction. None of this run's 40 maneuver records supplies either geometry
field. Later records still include explicit left/right/straight/U-turn
types, so absent angles do not make every maneuver unusable.

The user confirms that the card agreed with the phone's own directional
guidance. This is therefore not evidence of an AID-only rendering defect.
It does **not** establish a GPS/heading failure or prove that being underground
caused the missing arrow. Decoded route states are 0, 3 and 1; there is no
explicit locating (`4`) or proceed-to-route (`6`) state. The visible turn card
is still rendered by the phone, independently of a future native consumer.

A separate selection limitation appears in all four starts:

1. The phone publishes an empty current-maneuver list, indexed records, then
   ordered list `[0, 1]` while guiding and visible-in-app is 1.
2. It immediately publishes state zero, then loading. The reader clears the
   former episode's list and records.
3. It resends maneuver records and resumes guiding with visible-in-app 0,
   but supplies no current-maneuver list for that sustained episode.

The first allocation contains every sequence, so this cannot be explained
by missed initial history. Its transient lists are sequences 20 and 93,
followed by stopped states 21 and 94. The second allocation shows the same
pattern at 20/21 and 72/73. All retained route fields were inspected,
distinguishing explicit-empty and absent lists. Do not retain an old list
across a real stop or choose a cached maneuver without a current index.

The replay's **one resolved-maneuver snapshot** counts state at the end of
each captured window. Other windows contain a transient resolved head and
then a stop in the same batch; those intermediate records are retained.
It is neither a maneuver-reception count nor proof of sustained selection.
The source is Google Maps. Whether this sequence depends on route-start
conditions or app/display transitions remains unresolved.

## Offline follow-up: comparison with successful runs

The same startup stop/loading pattern exists in B2 and B4 logs. It is not
unique to C4. In the successful B4 sessions, later route updates supply new
ordered lists in the sustained guiding episode: the first connection goes
on to select indices 0, 1 and 2; the later connection selects 0, 1 and 2 and
later reuses indices after rerouting. B2 also initially guides without a list,
then supplies `[2, 3]` after a later loading/rerouting cycle. These are fresh
post-reset lists, not selection recovered by carrying a list across a stop.

C4 has no such later list, nor any maneuver-distance field in its sustained
guiding updates. Route activity alone therefore does not establish that the
phone has supplied a current step. Suppressing a stop or selecting the first
prefetched maneuver would hide this distinction. The pinned reference also
clears its current list on a nonzero-to-zero transition, even when it delays
the visible stopped-state notification; copying that debounce does not
restore the missing list.

The companion logs also allow a comparison of outbound NMEA fields without
recording coordinates. All sentences counted below have valid checksums:

| Log | GGA quality `0` | GGA quality `1` | Sustained maneuver list / maneuver distance received |
| --- | ---: | ---: | --- |
| B2 `3764296` | 0 | 164 | Yes / yes |
| B4 `4620416` | 0 | 221 | Yes / yes |
| B4 `5968000` | 31 | 54 | Yes / yes |
| C4 companion C3 `5509188` | 95 | 0 | No / no |

All counted RMC sentences carry status `A`, including all 95 in the C4
companion, despite GGA quality `0`. Do not describe this as unambiguous proof
of a missing position or infer what location the phone actually used. The
C4 companion covers the later connection only; the first connection's NMEA
is absent from these inputs. This contrast supports controlling position
conditions in the next test, not declaring a GNSS cause or a driver defect.

The host replay now reproduces coverage directly in `coverage`: 237 published,
236 recorded and one unrecorded event. `--messages` exposes all four transient
selected-head events, followed by stop/loading and `order_absent` during
sustained guidance. It distinguishes these from the single window ending
with a selected head. `--require-complete` correctly exits 1 for this capture's
one gap, while ordinary replay exits 0 for normal recorder completion.
The changes are host-only; the tested C4 binary/package stays unchanged.

## Companion C3 evidence and fingerprints

C3 completes every copy, reporting `CPMAP_RGI_CAPTURE_OK` and
`CPMAP_NAVRECON_OK`. Its 33,088-byte snapshot is enabled, fault-free, sequence
88 and stopped in the second allocation. Its header equals C4's last header;
all sixteen retained events match the journal.

The 144,419-byte text log contains 88 guidance markers, one accepted
identification and a successfully queued `5200` start. There are no
`Invalid packet`, `Failed to send packet`, `No packets in receive list` or
`IdentificationRejected` errors. Strict replay rejects one interleaved hook
dump, marker line 413 / sequence 14. The preceding stock semantic dump is an
intact 65-byte `5202` frame and independently matches the journal's decoded
event. The other 86 overlapping text records match C4's exact message IDs
and TLV bytes; sequence 1 appears only in text. No permissive hex recovery
was added. OEM error 42 is the unchanged historical B1 archive.

Both collectors retain the exact B4 driver (743,196 bytes, SHA-256
`3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b`)
and patched config (6,006 bytes). C3's OEM backups match the fingerprints in
[B2-RESULTS.md](./B2-RESULTS.md). No rollback was exercised.

Input SHA-256:

- Journal: `96104664ece8630d8cda36e948d0ba516fa09691e3e7f82b8ad5ce437ee03c95`
- Text log: `509f02c49c044b0da4c060244236af0d9f634fc641fc340aeedea61cc811f969`
- C3 snapshot: `8d6380515ea75876c0adaa33379db3017367d6c38b42027522517278854dc24f`

## Next test

Use the **same C4 package**, leaving B4 installed. Export/remove the previous
RAM capture, then repeat outdoors with a usable position and an identifiable
first ordinary turn. The added procedure in [TEST-C4.md](./TEST-C4.md) lets
startup settle, distinguishes the route-start instruction from an ordinary
turn and records whether opening the Maps route screen changes the card.
Export before any reboot. No factory restore or driver reinstall is needed.
If available, use a cable already known to reconnect reliably and note the
number of insertion attempts and approximate recognition delay. Keep cable
recognition separate from guidance behavior in the test notes.

The next decision is whether a route with a usable outdoor position supplies
an authoritative current index after the startup reset, and whether that
index/distance advance through an ordinary turn. Native output remains deferred until
that is understood. The one overwritten stopped-state record also leaves
burst-completeness unproven; faster polling alone would not establish a
lossless handoff.
