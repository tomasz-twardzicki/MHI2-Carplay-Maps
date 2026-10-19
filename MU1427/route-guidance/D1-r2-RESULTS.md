# D1-r2: startup and shadow accepted

The user reports normal OEM and CarPlay navigation during this test, after
completion, and after reconnecting the phone. The user also confirms that
**verify shadow health returned `CPMAP_RGI_D1_SHADOW_VERIFIED`** during the
active run. The original D1 class-format startup failure is not reproduced.

## Build and on-unit evidence

The export reports `MU1427-RGI-D1-r2-cbdd13d9`. Its adapter build ID is
`8a25954d4812cdf0`, matching the corrected, all-major-46 Java JAR:
`cbdd13d9cddd63d1e93973ccd7aa21e9bd8017ec73d3fa95d7db156bb7b090a3`.
The photo shows the adapter active at `mode=1 context=0 ticks=889` with run
ID 3457152. The right side of that status line is clipped; counters beyond
it are not inferred from the photo.

The successful verifier establishes a matching build/run, shadow mode,
eligible factory ownership, nonzero proposals/ticks, zero writes, zero
failures and zero decoder errors at verification time. Exact proposal counts
were not retained in the export. This is acceptance of startup, actual
factory context and shadow processing, **not native BAP display output**.

The exported status is after disable:

```text
mode=0 context=0 ticks=1072 proposals=0 writes=0 releases=0 failures=0 records=0 error=0
```

This is expected stopped state. Disabling changes the request/run ID, and
the Java worker resets per-run proposal/write/record counters. Those zeroes
cannot be used as the active-run counter totals. D2 preserves the exact
verified shadow status, the status observed from the menu, and pre-disable
status/request snapshots to remove this reporting limitation. The tested
Java JAR is unchanged.

## Recorder and semantic replay

| Check | Result |
| --- | --- |
| Duration / termination | 109,829 ms; manual stop, reason 1 |
| Reads | 1,033 valid; zero invalid |
| Snapshots | 109; zero producer faults; zero read invalidations |
| Active / current head resolved | 105 / 93 snapshots |
| Unique recorded messages | 193: 157 route, 36 maneuver, zero lane |
| First window | Sequence 185, retaining 170–185 |
| Coverage | Every sequence 170–362 retained; 169 earlier events predate capture coverage |
| Stale deadlines | One; no decoder error |
| Java/Python parity | All 214 journal observations match, including distances |
| Old complete journal | Bootstrap-only replay proposes no live output |

The ring was already populated when recording started. Its single unique
gap is the missing prefix 1–169, not a loss later in the recorded test.
Consumer reset/replay counts must not be added to that unique gap.

With **simulated eligible ownership**, the host bridge produces 200 publish
observations, three clear/release transitions and eleven pass-throughs.
Those 200 observations contain 152 right-turn descriptors, eleven roundabout
descriptors and 37 blank symbols; 178 observations have a valid distance.
These include heartbeat observations and are not unique wire-event counts
or on-unit native writes. Missing heads/geometry are cleared conservatively.
The recording contains reroute/loading resets and subsequent fresh selection.

Journal: 244,268 bytes, SHA-256
`24b48a125ad276ec5fbbf86417eefebb518320b9fb021ef5959570d611ceac1b`.
Private route payloads and the photo remain outside the repository/package.

## Next test

[D2](./TEST-D2.md) enables a manual, bounded native arrow/distance test only
after a fresh successful shadow verification in the same boot. It reuses
this exact Java JAR, the tested B4 driver and C4 native reader. Its changes
are toolbox controls, status evidence preservation and the live-start menu.
Native glyphs, distance rendering, physical stop/disconnect clearing and OEM
ownership handback remain untested on the cluster.
