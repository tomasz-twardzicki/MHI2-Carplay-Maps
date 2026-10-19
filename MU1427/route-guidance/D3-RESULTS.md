# D3: native distances and route totals working

The user reports no observed issues. The supplied photos show native arrows
and maneuver distance on both AID and HUD, remaining route distance and
travel duration on AID, and agreement between the native and phone-rendered
maneuver distance in the photographed example. The earlier factor-of-ten
error is not visible. The time field displays a duration, as intended.

The user additionally confirms that **all three display checks passed**:
the maneuver distance scale is corrected, and remaining route distance and
travel time are visible and roughly consistent with the phone. This accepts
the D3 distance/totals changes for the tested run. Exhaustive checks of every
unit boundary, maneuver and ownership transition remain separate. Absolute
clock-time ETA remains outside D3.

## Removing before export

**The supplied captures are usable.** Both exported successfully and contain
valid, complete manual-stop end records. The installed version in both is
`MU1427-RGI-D3-ea264694`, adapter build `6fa06a5387d3757b`.

The packaged `uninstall` action disables the enable request and stops the
recorder, then removes the JAR and its bootclasspath entry. It does not delete
the RAM capture, saved status snapshots or RAM version marker. Export does
not require the adapter still to be installed. Therefore uninstall followed
by export, **before reboot or clear**, preserves the recording up to stop.
Reboot or clear would discard RAM captures; that has not happened to these
exported files.

The live export lacks `adapter-status-before-disable.txt`, consistent with
removing the enable request before export. The independently saved
`adapter-status-observed.txt` retains the healthy active live status. The
latest `adapter-status.txt` is already disabled/reset; its zero counters are
not active-run totals. Export before removal remains the preferred order.

## Recorder and adapter evidence

| Check | Shadow `3993667` | Live `6951040` |
| --- | --- | --- |
| Duration / termination | 98,403 ms / manual stop | 284,798 ms / manual stop |
| Valid / invalid reads | 923 / 0 | 2,670 / 0 |
| Snapshots / producer faults | 78 / 0 | 233 / 0 |
| Source-unavailable invalidations | 0 | 0 |
| Stale deadlines | 1 | 3 |
| Unique recorded events | 158 | 423 |
| Recorded route / maneuver / lane messages | 124 / 34 / 0 | 367 / 56 / 0 |
| Journal bytes | 176,746 | 545,802 |

The verified shadow status is `mode=1 context=0 ticks=550 proposals=216
writes=0 failures=0 records=121 error=0`. The live observed status is
`mode=2 context=0 ticks=1882 proposals=217 writes=4040 releases=5 failures=0
records=483 error=0`. These are status-check observations, not final totals.
Writes count output-hook fills rather than physical cluster acknowledgments.
The five releases need not correspond one-for-one to particular user actions.

Shadow retains every published event. Live starts with the old shadow ring
at sequence 158, retaining 143–158: the missing prefix 1–142 predates live
recording. There is also **one genuinely unrecorded event**, sequence 364,
between the last sequence 363 and a window starting at 365 at elapsed
117,000 ms. This precedes the final manual stop and is separate from removal.
The bounded sixteen-slot ring does not guarantee arbitrary burst retention.
The decoder invalidates history at a gap and uses the subsequently validated
window; no adapter error or user-visible issue was reported. Thus the live
journal is structurally complete, but its source-event coverage is not lossless.
Consumer reset/replay counts are not additional unique missing events.

## Replay validation

The exact packaged Java JAR matches the Python model at **all 172 shadow and
504 live observations**, including maneuver distance, remaining distance and
remaining seconds. Attaching to either complete old journal proposes no live
output. With simulated eligible ownership:

| Observation count | Shadow | Live |
| --- | --- | --- |
| Publish / clear-release / pass-through | 134 / 4 / 34 | 419 / 6 / 79 |
| Valid maneuver distance | 114 | 354 |
| Valid route distance | 133 | 418 |
| Valid remaining duration | 134 | 419 |

These include heartbeats and are host-model observations, not on-unit output
write totals. The complete replay and metric comparisons keep private values
in memory; only structural aggregates are retained in the verification record.

Journal SHA-256:

- Shadow: `c764cf09a2fab25ce0eaa5466263ed55d50f41b3c56367f875c1d2a774e8a390`.
- Live: `7247534bcbbf05f35077fe06f9febc5eb272a08e1b66ef80fd0f7bfc5fe5e400`.

The raw captures/photos stay outside the repository. The tested ZIP, Java
JAR, B4 driver and C4 reader are unchanged by this result review. This remains
a manual five-minute test package; acceptance does not enable persistent
output or change the install/reboot/rollback procedure in [TEST-D3.md](./TEST-D3.md).
