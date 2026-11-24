# Native guidance loss: vol2 capture

Reviewed on 2026-11-03:
`Logs/HMIcrashing/vol2/cpmap-diag-8654921`.
Input/source hashes and host fault checks are in the
[audit record](HMI-WORKER-FAILURE-2026-11-03.json).

The captured terminal failure is **native reader worker failure**, distinct
from the earlier MU1427 **RAM-output failure**. This export does not support
reusing RAM-disk exhaustion as the diagnosis. The exact worker failure subtype
and its underlying cause were not retained. No whole-HMI crash is established.

## What is installed

The summary identifies `PROFILE=MU1367/791`, MU1367 integration/settings and
guidance-v3 `mu1367-guidance-v3-9545741e95aa`. Follow-up comparison with the
retained release ZIP identifies this controller ID as **v1.4.1 variant 6**;
the component layer names alone are not evidence of an experimental install.
The running Java guidance build is `MU1367-guidance-31dfc8d5a6f2`. The Toolbox
base VERSION still contains `MU1427`; that label alone does not establish OEM
firmware identity. Installed binary hashes and an OEM software-train
identification are absent, so the version match is not a complete installed
payload audit.

## Evidence compared with the earlier incident

| Evidence | Earlier MU1427 capture | This capture |
| --- | --- | --- |
| Native reader status | `ended ... reason=4` | `ended polls=12818 valid=12655 invalid=163 sequence=1890 bytes=32 reason=3` |
| Terminal mailbox | END / OUTPUT_FAILED=4 | Valid 32-byte RGM1; serial 2789, END=5, detail WORKER_FAILED=3, reader nonce 2889 |
| Explicit filesystem-full error | Later errno 28 / ENOSPC | None found in supplied files; no `df` measurement available |
| Exported video log | 2,510,848 bytes | 254,115 bytes |
| Exported current bridge log | 1,389,056 bytes | 115,753 bytes |
| HMI guidance error | Saved status incomplete as later writes failed | `failures=0 error=0 feed_errors=0 feed_recoveries=0 feed_fatal=0` |

The current video/bridge files are below their 256/128 KiB limits. The video
log starts at uptime 25:47.965 and continues through 26:55.039: earlier video
history is no longer retained, consistent with bounded logging. The 16,779,024
byte video ring remains present in the unit listing. Smaller logs and successful
END/status writes support a different failure path, but do not measure free
filesystem space, total system RAM or device buffer availability.

The earlier finding was specifically exhaustion of RAM-backed **file storage**
by growing logs, with a later explicit ENOSPC. It did not establish a leak in
an HMI heap or MOST buffer pool. Bounded logging mitigates that storage growth;
it does not establish endurance of every other pipeline.

## Recorded sequence

Times below are boot-relative, using the adapter's recorded millisecond values
and the unit's Jan 01 system-log clock; the latter is not a real calendar date.

| Uptime | Observation |
| --- | --- |
| 00:55.715 | Initial video bridge exits. Archived `last-bridge.log` ends with `MOST write failed: Not enough memory`. |
| 01:00.864 | Supervisor starts replacement bridge PID 1884285 and records readiness. |
| 23:45.348 | Last guidance frame-change time implied by the later release's `frame_age=2733`. |
| 23:45.764 | Last accepted mailbox time implied by `journal_age=2317`. |
| 23:46.138 | System log records AirPlay screen `kConnectionErr`, followed by screen shutdown. Rear-camera activation is logged in the same second; causation is not established. |
| 23:46.817 | Adapter records its last owned guidance tick. |
| 23:48.081 | First unexpected ownership release: reason 6, eligible context 0, live mode 2, mailbox age 2317 ms, frame age 2733 ms. |
| 23:48.143 | AirPlay session teardown is logged. |
| 25:23 | Further AirPlay teardown / screen connection errors. |
| 26:55–26:57 | Video/system logging still advances; saved guidance state is ended/inactive. |

Ownership reason **6** means the adapter's mailbox freshness deadline expired
(1500 ms). It is not the native reader's WORKER_EOF enum, which also happens
to use 6. The first unexpected release retains an otherwise eligible context,
not an OEM-navigation takeover. Later status has `mode=0`, `mailbox_kind=5`
and all feed error counters zero, consistent with accepting the reader's valid
END record and stopping native output normally.

The terminal mailbox stores the reader's start nonce, **not its end time**.
Therefore the first release can be timed, but the exact native worker exit
cannot. The connection error and freshness loss are closely associated;
their causal direction is not established. The capture ends around 27 minutes
of uptime and does not itself demonstrate a 30/40-minute threshold or a
successful guidance recovery after reconnect.

## Why it stays stopped

The [shared reader](../../../MU1427/route-guidance/release/reader.c) polls
`/dev/ipod0/rgi-events` in a separate worker. The MU1367 native build uses this
same source; its hash matches the retained native-build manifest.

The parent exits with WORKER_FAILED=3 if no complete worker response arrives
within 1500 ms, if the pipe reaches EOF/errors, if select fails, or if its
clock checks fail. A timeout is plausible here, but END overwrites the earlier
INVALIDATE record, so the saved mailbox cannot distinguish timeout from EOF or
the other paths. The export has no child exit status, syscall phase or timing
history to settle that question.

A returned device open/read/close error, including ENOMEM, normally publishes
INVALIDATE and keeps polling. It does not by itself select terminal reason 3.
The 163 invalid polls therefore cannot be read as 163 terminal worker failures.

After a terminal failure, the parent kills its worker and publishes END. The
boot hook starts the reader once. The video supervisor restarts the video
bridge, not this guidance reader. Java feed recovery can accept a new producer
instance, but does not launch one. Reconnecting the phone alone is consequently
not a guaranteed recovery for this saved ended-reader state. The reported
reconnect recovery may describe another session/lifecycle action; it is not
shown in this export.

The archived MOST ENOMEM is real and should remain a separate resource issue
to investigate. Its failed instance was replaced near one minute, over twenty
minutes before the recorded guidance ownership loss. The later bridge remains
active, with its own counters advancing. This early event neither proves
late RAM-disk exhaustion nor excludes wider resource pressure affecting the
later worker. Repeated `suggestUI` 422/kNotHandledErr responses likewise do not
identify the native worker's failure cause.

## Checks and next engineering step

Two isolated host checks passed against the unchanged production reader:

1. The existing blocked-read regression reproduced a prompt END with detail 3
   and no automatic restart loop.
2. Injecting three returned SOURCE_READ/ENOMEM errors produced INVALIDATE,
   then recovered to valid snapshots with the same reader still alive. Manual
   stop subsequently produced END detail 1.

These establish the distinction between a stalled worker and a returned
device error. They are not a reproduction of the unit's exact trigger, QNX
resource-manager scheduling or an endurance run. The first host attempt hit
an installed SDK/linker mismatch; both checks passed using the existing
MacOSX14.4 SDK used by the repository's native host tests.

The next change should preserve bounded first-failure evidence in the native
reader: terminal subtype, errno, last complete response time, partial-pipe
byte count and child exit status. Any subsequent recovery design must keep
stale guidance cleared, require a validated new baseline and fresh input,
and avoid accumulating workers blocked in device operations. Java decoder
relaxation or a larger log allowance does not address this terminal path.

For the next vehicle failure, preserve an export before reconnect/reboot,
including RAM-disk usage, reader status and process/thread state, then capture
again after the reported reconnect recovery. Establish whether the reader
actually restarts and changes nonce. Record cable/adapter identity and OEM
software train. No new target commands, installed payloads or release ZIPs
were introduced by the initial log review.

## Prepared recovery test

A separate [reader recovery test](../READER-RECOVERY.md) is now packaged.
It preserves bounded first-worker-failure evidence and allows at most three
replacements, only after confirmed reaping. Each replacement forces a new
validated baseline and fresh guidance before output resumes. Host and factory
QNX process/transaction checks pass; vehicle endurance remains unverified.
The current candidate is based on v1.4.3 and also supports P4521. See
[release verification](../VERIFICATION.json) for the current exact artifacts;
the earlier standalone test archive and its verification remain historical.
