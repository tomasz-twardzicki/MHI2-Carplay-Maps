# B4 on-unit result (2026-10-17)

**B4 passes the captured publication lifecycle test.** All four C3 captures
contain enabled, advancing event publication with no producer fault. The
reader observes guiding and stopped states, and a later connection has a
new allocation with its own sequence. This confirms the activation-order
correction described in [B3-RESULTS.md](./B3-RESULTS.md).

This validates the bounded driver handoff, not a continuous consumer or native
cockpit output. The captures contain one active-navigation snapshot rather
than two consecutive active snapshots. They still demonstrate sequence
progression within one allocation, route-stop clearing and publication in a
later allocation. The user also confirms that the AID route line and turn
card worked normally, including the first navigation session before
reconnecting. Long-duration operation and Qnet reads remain unvalidated.

## Private inputs and publication

Inputs are under `Logs/B4/`; raw logs and snapshots stay outside the repository.
All snapshots are exactly 33,088 bytes, with session 1, enabled 1, fault 0,
writer lock 0 and a valid even snapshot version. Every retained event passes
the binary reader's header, identity, sequence, bounds and TLV validation.

| Capture | Allocation (monotonic sec, nsec) | Sequence | Retained range | Last route state |
| --- | --- | ---: | --- | --- |
| `cpmap-navrecon-C3-3301450` | `(43, 231000000)` | 93 | 78–93 | Stopped (`0`) |
| `cpmap-navrecon-C3-4079683` | Same | 217 | 202–217 | Guiding (`1`) |
| `cpmap-navrecon-C3-4620416` | Same | 230 | 215–230 | Stopped (`0`) |
| `cpmap-navrecon-C3-5968000` | `(345, 694000000)` | 113 | 98–113 | Stopped (`0`) |

All **64 retained records** match the corresponding message IDs and raw TLV
bytes at their exact sequence positions in the complete session logs. The
second snapshot includes events 216–217 received after its text-log copy;
both appear in the third capture's cumulative log. C3 copies the log before
reading the snapshot, so those files are not a simultaneous transaction.

Sequential `Consumer.consume` reports missing history of 77, 108, 0 and 97
events respectively. These are expected rolling-window gaps or a late first
read, not producer faults. The second and third windows overlap by three
records; the reader applies only thirteen new events from the third. Its
state clears immediately on the final state-zero updates. The last capture's
allocation change resets the reader before applying the new session.

The active snapshot contains route deltas but no maneuver records: its
ordered head is index 1, while `current_maneuver` correctly remains unknown.
The complete text-log replay has that maneuver cached. Spaced SD captures
cannot reconstruct records overwritten before the reader starts. A future
continuous reader must detect gaps and preserve this distinction, rather
than choose a guessed maneuver or equate missing metadata with stopped
guidance.

## Reception and text-log limitation

| Capture | iAP2 log bytes | Route markers `5201` | Maneuver markers `5202` | Strictly decoded records |
| --- | ---: | ---: | ---: | ---: |
| `3301450` | 160,119 | 79 | 14 | 93 |
| `4079683` | 331,271 | 187 | 28 | 214 of 215 |
| `4620416` | 358,307 | 202 | 28 | 229 of 230 |
| `5968000` | 173,197 | 101 | 12 | 113 |

The first log is an exact prefix of the second, which is an exact prefix of
the third. The fourth starts a fresh identification/start cycle. Count only
the third and fourth logs: **343 distinct guidance messages**, comprising
303 route and 40 maneuver updates, with no lane `5204` messages. Their counts
agree with the final publication sequences, 230 and 113. Source is Google Maps.

One hook hex dump is interleaved with stock logging: message sequence 110,
marker at line 2043 in the second/third log. The next line is not its intact
145-byte payload, so the strict decoder correctly reports
`incomplete or interleaved hook dump` and exits 1 for those two logs. This is
the same damaged record in cumulative captures, not two malformed wire frames.
The stock semantic dump immediately preceding the marker (line 2042) contains
an intact 151-byte `5201` frame, which independently passes `decode_frame`.
The binary snapshots are unaffected. No permissive log-recovery change is
needed for the publication reader.

Each log contains one `IdentificationAccepted` and one successful
`CPMAP_RGI_START B4 0x5200 rc=0`. All four have zero `Invalid packet`,
`Failed to send packet`, `No packets in receive list` or
`IdentificationRejected` messages. Location/ACK traffic continues after
route stop in the first, third and fourth captures. There is no B1-style
receive-pool stall in this evidence.

The video supervisor remains CarPlay-active throughout the first three
captures. The fourth contains a fallback/restart and a second successful
CarPlay/video setup, consistent with the new iAP2 allocation/connection.
The historical `patch_failed_fingerprint` marker is also present in successful
B2/B3 captures; it does not identify a new B4 failure. The user's visual
check confirms normal AID route-line and turn-card behavior in B4, including
the first session before reconnecting. The B3 symptom did not recur in this
test; its original cause remains undetermined.

## Installation and collection integrity

All four copies match the exact B4 driver (743,196 bytes), patched config
(6,006 bytes) and original OEM backups (739,925/5,905 bytes). Driver SHA-256:
`3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b`.
Config/backups match the fingerprints in [B2-RESULTS.md](./B2-RESULTS.md).
Every collector reports zero read failures and `CPMAP_RGI_CAPTURE_OK`.
OEM error 42 remains the exact historical B1 archive; no new numbered error
was collected. These captures do not exercise an on-unit B4 rollback.

No driver or installation change follows from this result. Preserve the
tested [B4 package](./build-B4/MU1427-route-guidance-B4-toolbox.zip) and its
host-tested rollback path. The next implementation step is an independent,
bounded continuous reader with gap, disconnect and stale-data handling,
initially for diagnostics. Test its polling cadence and burst handling before
enabling any PPS/HMI output. Maneuver mapping and lane interpretation remain
separate work; see [PUBLICATION.md](./PUBLICATION.md). That diagnostic step
is now implemented as [C4](./OBSERVER.md); [TEST-C4.md](./TEST-C4.md) is the
next hardware procedure.

## Input integrity

SHA-256 of each `iap2.log`, in acquisition order:

- `3948be5105a0302aac6c92637e0d43ab67d08aa4d8b2fb4e8bd81104af4f784f`
- `91d13724f9b92a7cdb9dd906e6aaf945ae7d2a87751cbcbf9320e76b1e08314a`
- `7bd5f582288a2e76a90343ec94e6f7ad998185c4d507bafd396c036f6290ceee`
- `c40ae2425245a289c0bc4b4b3bb7d2458cddf7149d4b8ca6b3e027f40a506cff`

Snapshot SHA-256 in the same order:

- `229946abe30537228eb65569d21da21becd75bce78d3878b8710978740708c18`
- `24e681a771a57493f8d2e6d1c50e57715e0194c8f58b8234632e7c802d801bb4`
- `c56f23020cf0b3865dfb4640462ef1d3ccb3515695c83d1c32deee9531f53357`
- `22e390e6dd4e9106777418a80ce51838fe9c8124472d3cd1e8220d6aef0373a8`
