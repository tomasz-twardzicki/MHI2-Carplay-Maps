# D2: native output accepted, distance conversion correction needed

The user confirms visible native guidance arrows on **both AID and HUD**,
normal OEM navigation/reconnection, and clearing when disconnecting during
guidance. Two remaining items were reported: maneuver distances appear at
one tenth of the correct size, and route distance/time are blank. D2 omitted
route totals deliberately. Native output is now demonstrated on the unit.

## Exported evidence

Both captures identify `MU1427-RGI-D2-cbdd13d9` and the accepted r2 Java build
`8a25954d4812cdf0`.

| Check | Shadow `4034635` | Live `7831680` |
| --- | --- | --- |
| Recorder duration | 117,365 ms, manual stop | 300,013 ms, normal duration limit |
| Valid / invalid reads | 1,104 / 0 | 2,706 / 104 |
| Snapshots / producer faults | 95 / 0 | 286 / 0 |
| Recorded unique events | 162 | 475 across two publications |
| Unrecorded prefix | None | First window retains 147–162; preceding 146 predate capture coverage |
| Reader invalidations | 0 | One unavailable-source event, reason 1 / errno 2 |
| Stale deadlines | 2 | 3 |

The live unavailable-source interval and new publication are consistent with
the reported unplug/reconnect test. Invalid reads here are recorder polls
while the virtual source was unavailable; they are not Java decode errors.
There is no later unique sequence gap in either recording. The live recorder
reached its five-minute deadline; it was not extended.

The saved shadow verification has `mode=1 context=0 ticks=502 proposals=190
writes=0 failures=0 error=0`. The live status-menu snapshot has `mode=2
context=0 ticks=1730 proposals=168 writes=1896 releases=2 failures=0
records=335 error=0`. These are observations at the status checks, not final
run totals. Output writes count adapter hook fills, not physical cluster ACKs.
Later disabled status resets per-run counters, as expected. The D2 snapshot
export changes preserve the active evidence successfully.

Journal SHA-256:

- Shadow: `d6d4b6848753f42f041446a152bc0709a607e850bbc2db49067d9218fde6513e`.
- Live: `fc7f446b27dc9b8f38e0284e7dd492d438673e5b4238af05bbd49078da7c2dba`.

## Distance cause and route totals

D2's helper copied source metres directly into a BAP distance with unit 0.
The exact factory `DistanceToNextManeuver.computeDistanceAndDistanceUnit`
instead calls `FixFormat.cnvDistance2KilometersExt` (or the corresponding
miles converter). The factory numeric formatter emits the BAP fixed-point
value, rounding and switching units as necessary. For example, 20 source
metres become `(200, unit 0)`, and 30 metres round to `(400, unit 0)`.
Bypassing this conversion caused the reported factor-of-ten display error.
The previous raw-metres assumption was incorrect.

The recordings already contain `remaining_meters` and `remaining_seconds`
updates: 108/109 observed field occurrences in shadow, and 379/382 in live
(including replay after consumer resets). No driver change or additional
phone request is needed. [D3](./TEST-D3.md) uses the stock formatter and adds
the stock destination-distance and time-to-destination BAP stages. Its time
output is **remaining travel duration**, not a clock-time ETA derived from
an unverified phone timestamp epoch/timezone.

D3 Java/Python replay matches all 208 shadow and 573 live observations,
including distances and the new totals; old complete journals remain
bootstrap-only. Raw navigation payloads and photos stay outside the repository.
