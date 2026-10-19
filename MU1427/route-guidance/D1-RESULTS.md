# D1: failed HMI startup, rollback successful

**D1 is withdrawn. Do not reinstall its original package.** The corrected
class-format build is [D1-r2](./TEST-D1-r2.md), limited to startup/shadow testing.

## Unit result

After D1 installation and reboot, the cluster remained at loading navigation.
OEM navigation worked on the main unit. Connecting the phone and starting
CarPlay guidance did not recover the cluster. Shadow status reported that
the adapter had not started. The user confirms that **removing D1 and fully
rebooting restored normal cluster navigation**. B4 remains installed.

The D1 export identifies `MU1427-RGI-D1-b8f0d359`, matching the failed JAR:
`b8f0d3599f43419c8cbf3cf748cba4ce16ac4038263d082802359e8fdf47b774`.
The original archive SHA-256 is
`feb0dcea4edfe50853ea574af82b0d0c7b214210abb05567286bdbf7cf5a4000`.

The private `Logs/D1` data contains a 345,755-byte journal, recorder status,
basic diagnostics and a C3 capture. There is **no adapter-status file** in
the D1 export. The collected system log has no Java exception establishing
the cause; the controlled firmware-runtime reproduction below establishes it.
No private payload, route text or coordinates are copied into this report.

## Driver/recorder observations

- Recorder: 1,420 valid reads, zero invalid reads, manual end after 150,472 ms.
- Replay: 154 snapshots, zero producer faults, zero source-read invalidations;
  147 active snapshots and 125 with a resolved current maneuver.
- Sequence coverage: 302 published, 246 recorded. The first snapshot already
  has sequence 72 and retains 57–72, so the 56 missing events precede recorder
  coverage. This is not evidence of a later receive failure.
- One source-progress stale deadline occurs. Reset/replayed-window gap totals
  must not be counted as additional unique wire loss.
- Captured driver: 743,196 bytes, SHA-256
  `3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b`.
- Captured configuration: 6,006 bytes, SHA-256
  `67b867db8eb05e0dd20645727d3216ff18b86be75d21c9fb89a92dffbcafc9f7`.

Both fingerprints match tested B4. Journal SHA-256:
`6762e51da750b389cc8eef8c2488cc38bf4f6b79b3cc495f1ff6728f2ea478b5`.

## Confirmed build error

D1 downgraded only its helper classes to class major 46. It left the four
replacement stock BAP function classes at **major 49**, emitted by the pinned
current jxe2jar converter. The installed, working NavActiveIgnore replacements
actually use major **46**; the earlier documentation's comparison was wrong.
Desktop Java 8 accepts 49, so the earlier desktop tests missed this error.

The exact factory ARM J9 and factory JXE were executed under QNX/QEMU:

| Input | Stock function classes | Helper |
| --- | --- | --- |
| Factory ROM, no D1 override | All four load/instantiate | Absent, expected |
| Exact failed D1 JAR | All four rejected with `ClassNotFoundException` | Loads |
| Same D1 JAR, only four major headers changed 49 → 48 | All four load/instantiate | Loads |
| Same D1 JAR, only four major headers changed 49 → 46 | All four load/instantiate | Loads |

This isolates the failure to the replacement class format, before registration
or route processing. Rejection prevents stock NavSD function initialization
and D1's registration hooks; it explains both the cluster startup failure and
absent adapter while the main unit's navigation engine remains available.

The reproducible regression [test-live-qnx.py](./test-live-qnx.py) now uses
the factory ARM J9, matching native libraries/libc and factory JXE, with the
old failed JAR as a required negative control. It checks the actual corrected
release JAR, including stage construction, all four inactive output helpers,
and registration/detachment one stage at a time. Those registration probes
intentionally avoid starting a timer or publishing BAP.

## Correction and next test

All replacement classes **and** helpers now emit major 46. The build rejects
any installed class with a different major, compiles helpers against the
factory CDC boot classes, and fingerprints the patcher as part of build ID.
Packaging requires a passing actual-firmware-J9 result for the exact JAR.

The corrected release passes nine native-runtime checks with OEM `-noverify`
and again with `-verify`. The original JAR still fails the negative control.
The existing 37 desktop integration assertions, 19,360 mapping vectors,
private C4 replays and installation/removal tests also pass.

**D1-r2 has no live-start menu and its controller rejects live start even with
a healthy shadow proof.** First verify cluster startup with no phone, then
CarPlay continuity, then adapter shadow status/export. Full HMI startup and
real event-thread/bus behavior still require that unit test; the emulator
does not simulate the complete car or cluster. See [TEST-D1-r2.md](./TEST-D1-r2.md).
