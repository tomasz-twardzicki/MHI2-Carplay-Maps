# Two-drive review and work order

Status: analysis complete; implementation is now tracked in
[v162-next/PROGRESS.md](../../v162-next/PROGRESS.md). No new SD package has been built.
The stable v1.6.1 and sealed v1.6.2-e-test1 packages remain unchanged.

Inputs: the feedback attachment and four exports in
`/Users/tomasz/Documents/github/personal/Logs/wireless/v1.6.2e-test1`.
Drive 1 pairs `cpmap-diag-44699776` with `wireless-diag-45396096`;
drive 2 pairs `cpmap-diag-50896995` with `wireless-diag-51548255`.
The three supplied feedback attachments have identical content.

## Establish the installed build first

**Both exports identify the stable v1.6.1/test2 native runtime, not
v1.6.2-e-test1.** This is a runtime fingerprint finding, independent of the
directory name and feedback label. The user confirmed on 2026-11-19 that both
drives were recorded before installing v1.6.2. These are v1.6.1 baseline
captures; there is no installation-failure finding from these exports.

Both wireless summaries say:

```
carplay-mu1367-wireless-native-v161t2
MU1367-wireless-native-v161t2-f6dfb5e724b1
installed
```

The launcher and tap hashes match the contents of the stable v1.6.1 ZIP exactly.
They differ from the sealed v1.6.2-e-test1 ZIP:

| Component | Both drives / stable v1.6.1 | v1.6.2-e-test1 |
| --- | --- | --- |
| wireless-receiver-exec | `8a7ef2c9e6e7…` | `2b8cadae1d55…` |
| libcpmap-wcp-tap.so | `5b3ee9effff1…` | `8a7720cbf931…` |

The HMI status independently reports `MU1367-artwork-55008dbaf18e`, rather than
the new wireless-media build. Source counters use `WCP161`, with no v162 media
counters. Therefore these drives cannot validate the v162 priority floor,
wireless NowPlaying forwarding, or Volkswagen label. The old tracks=0/covers=0
result is consistent with the old runtime; it is not evidence that the new
forwarder failed.

Before another vehicle comparison, record the SD ZIP checksum, the completed
installed generation, post-reboot native hashes and HMI build. Installation
requires repeating Install after each requested reboot until it reports the
new generation installed. The already implemented v162 priority, NowPlaying
and label changes still need their own post-installation vehicle capture.

## What the logs establish

| Observation | Drive 1 | Drive 2 |
| --- | --- | --- |
| Accepted session at export | Yes; session 4 | Yes; session 2 |
| Receiver IDR receipt | Absent | Present; matches receiver/session |
| Cumulative AID frames / IDRs | 69,872 / 13,645 (~5.12 frames/IDR) | 90,634 / 11,433 (~7.93 frames/IDR) |
| Timing/smoothing lines in retained bridge log | None | Present; last matches=89,521, misses=1,048, delay=246 ms |
| Retained bridge clock span | ~135.7 s | ~182.9 s |
| Retained metrics samples | 131 | 181 |
| Samples with maximum PTS step >=200 ms | 33 (25.2%) | 5 (2.8%) |
| Maximum queue_hi in retained windows | 662 | 214 |
| Historical queue_hi_total reported by those windows | 662 | 1,187 |
| Main-screen decode errors / drops / late drops | 0 / 0 / 0 | 0 / 0 / 0 |
| PF startup | Empty NAT detection and undefined macros; later succeeds | First watcher apply succeeds |
| Channel | Settled on 11; no movement recorded | Settled on 11; no movement recorded |
| Guidance feed/fatal failures | 0 | 0 |

Drive 1's input accepted multiple feed connections and its supervisor stopped
the bridge around 164 s, then restarted around 271 s. The exported active
session has no receiver cadence receipt and uses approximately the old IDR5
fallback. Drive 2 has an active receiver cadence and timing matches. These
observations support prioritizing reconnect recovery.

The table's timing percentages describe the retained metrics samples. PTS steps
are frame timestamp intervals, not direct measurements of visible freezes or
whole-drive latency. The 662-versus-214 comparison is valid only for retained
windows: drive 2's historical queue maximum was actually higher. The drives
are useful comparative evidence, but different route/load/session histories
and truncated logs prevent a controlled whole-drive A/B conclusion.

The main-screen decoder being clean narrows investigation toward delivery,
scheduling and presentation, but does not alone prove which caused visible lag.
Likewise, successful MPL5 writes do not establish uninterrupted audio playback.

## Work order, with evidence and exit checks

### 0. Build identification and diagnostics (feedback 8; prerequisite for all comparisons)

The receiver log reports 17 and 16 rotations. The current collector does not
collect the actual `wcp.log.1` rotation; the v162 collector generator adds
`wcp.log.old`, which does not fix this. Capturing `.1` buys one previous segment,
not an entire hour of detailed logs.

Add `.1` to standard/GEM exports, explicit installed generation/native/HMI
fingerprints, bounded timestamped minute summaries and a bounded connection
timeline. Summaries should retain timing miss reasons and sizes, maximum gaps,
queue/PTS/recovery counters, session changes and priority readback. Repeated
unchanged avcC announcements currently consume useful bridge-log space; log
configuration changes and aggregate repeated events. Keep raw video and
credentials out of this routine export.

Exit checks: a simulated long run retains whole-session summaries and recent
detail across rotations; both diagnostic entry points include them; missing
optional files do not fail export. Counters must distinguish cumulative values
from window maxima and identify their receiver PID/session.

### 1. Restore timing and receiver IDR cadence after reconnect (feedback 1, highest functional priority)

**A concrete object-base error exists in both v161 and v162 `wcp_tap_send()`.**
For the pinned receiver SHA256
`f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1`:

- Native `0xe6564` reads the alt flag at parent+132.
- `0xe6568` sets the sender argument to parent+136; `0xe65cc` passes it to
  the thread whose entry is `0xe6fcc`.
- The sender keeps that argument in r5. Its port is argument+64 (parent+200);
  header stripping is argument+112 (parent+248).
- The tap checks `context[132/4]` using r5 as context. That reads parent+268,
  not the alt flag. It is an unrelated field for this test.

Consequently a valid accepted alt sender can bypass both timestamp publication
and receiver IDR requests. This is a strong candidate for the reconnect symptom;
the captured logs do not reveal that field's value, so causation is not yet
proved. The existing synthetic sender test sets context+132 to 1 and therefore
misses the real-layout failure. That test needs correction before relying on it.

First reproduce with the actual sender subobject layout, then classify the
audited sender using its own port/header fields. Test two alt restarts in the
same process, a new receiver PID, accepted-session changes, partial sends,
rejected/main-screen senders and larger access units. Timing events must resume
and IDR8 receipts must identify the current accepted session. Preserve the
working input IDR fallback until a fresh receiver cadence is confirmed; startup,
resume and corruption IDR requests must remain effective.

### 2. Keep timestamp recovery continuous (feedback 3)

The bridge substitutes mapped phone presentation time on a timing match but
returns the input ring's arrival timestamp immediately on a miss. It does not
maintain a continuity mapping across that transition. The native phone time is
already mapped to local monotonic time; the problem is switching capture and
arrival semantics, not simply comparing raw phone NTP with the car's clock.

Drive 2's retained tail contains a maximum PTS step of 193,986 ticks (~2.155 s).
The feedback's large-frame/miss correlation deserves reproduction; the current
logs do not identify the reason for each miss. A 61 KB frame is below the tap's
256 KB size guard, so that guard alone does not explain it.

Track a bounded capture/arrival mapping within the accepted session, use a
continuous fallback, and reset it on real session/clock changes. Add miss reasons
including missing producer, invalid session, no fingerprint match, timing-ring
overrun and timestamp age rejection. Log AU size and recovery state. Exercise
isolated and consecutive misses, delayed arrival, 20–100 KB zoom bursts, ring
wrap and match recovery. Verify monotonic, sensibly bounded PTS without a
seconds-long jump followed by repeated one-tick clamps. Preserve H.264 dependency
chains when skipping to a queued IDR; a newer P frame is not an independent
recovery point.

### 3. Make startup and reconnect have one owner (feedback 2 and connection/call-routing addendum)

The PF failure is not just an interface-up check. `wcp_autostart.sh` and
`wcp_pfwatch.sh` can invoke PF setup concurrently; `wcp_pf.sh` truncates and
appends to a shared RAM rules file and shares its NAT detection scratch file.
There is no serialization. Interleaving is a code-confirmed race; reproducing
the exact undefined-macro failure remains necessary. An empty OEM NAT table
also causes a deliberate startup refusal.

Serialize generation/application, use private staging files, preserve the
currently active OEM uplink/NAT selection, validate the complete candidate and
publish readiness only after successful application. Gate discovery/connection
on that readiness, with bounded retry and useful failure status. Test both
concurrent callers, delayed OEM rules, each supported OEM uplink, a later
connectionmanager reload, stop and reboot. Persistent OEM PF changes would
need their own exact-file and restore audit; they are not a prerequisite for
fixing the RAM race.

Introduce explicit ready/discovering/connecting/accepted/tearing-down states.
Already accepted or in-progress sessions must reject a second handoff. A known
phone already associated over Wi-Fi should get a bounded 10–15 s control
discovery window before considering Bluetooth fallback. Association alone does
not authenticate the phone or establish an accepted CarPlay session; it cannot
authorize another device to take ownership.

Apple's [WWDC17 session 717](https://developer.apple.com/videos/play/wwdc2017/717/)
requires operational networking before connection, avoiding interruption of an
active session, and disabling Bluetooth during active 2.4 GHz CarPlay. Its
reconnect guidance also tries CarPlay control recovery before Bluetooth after
an unexpected loss. This supports the requested policy. These exports do not
prove that duplicated handoffs caused the observed disconnects, or quantify
Bluetooth's contribution to timing stalls.

Audit the actual `btwcp`/OEM BT control path before implementing the policy:
phone profiles, iAP2, inquiry/page activity, call routing and restoration on
session loss/disable. Never kill the OEM BT daemon blindly. Distinguish explicit
user disconnect from transport loss. Test Wi-Fi-first, BT-first, simultaneous
arrival, wired already active, another paired phone, manual disconnect,
unexpected loss, repeated reconnect and incoming/outgoing calls. Record
monotonic times for association, BT ACL/iAP2, 0x5703/0x4301, Bonjour,
accepted/ended and teardown reason. Channel pinning is not supported by these
captures as the first remedy.

### 4. Fix two independent control errors (feedback 6 and 9)

**Display FPS:** the `/info` hook writes the selected maxFPS into both mutable
display dictionaries when their count is two. Restrict the wireless setting to
the verified alt-display dictionary (type 111); keep the main display at 30.
Keep alt 40 and IDR8. Verify native dictionary identity and output, unknown
layouts/counts, tuning choices and reconnect. Do not infer delivered FPS from
the requested maximum. Add a separate main-screen setting only if needed later.

**Video lifecycle:** `alive(..., wcp_video)` requires a name ending `/wcp_video`,
but the launched executable is `/mnt/app/carplaymaps/wcp_video_tap`.
This produces the false launch failure and prevents stop/status from recognizing
the tracked process. Match the exact supported video executable and bootstrap
paths while retaining PID ownership checks. Test launch/status/stop during
preflight and after exec, stale/reused PID and an unrelated process. The previous
receiver launch test disabled video, so it did not cover this case.

### 5. Audit audio scheduling and skip latency (feedback 4 and 5)

The v162 priority wrapper covers the receiver alt sender and dedicated 9997
input adapter. **It does not promote MainHigh/type102 audio or MPL5 output.**
These captures run the older wrapper, so first verify the intended alt/input
floor is actually installed before drawing a performance conclusion about it.

Identify the audio receive, jitter/playout and MPL5 threads and their existing
policies/priorities. Add available native timestamped counters for late/missing
packets, gaps/rebuffers and output blocking. If the closed SDK does not expose
those counters, state that limitation and measure the accessible boundaries;
do not invent values from successful write totals. Promote only demonstrated
low-priority receive/output work, preserve higher native priorities and measure
under reverse/zoom load.

For skip latency, trace the HMI/wheel command route, corresponding phone media
command, audio flush/sequence transition and first new audio output. Compare
touchscreen with wheel skip. A NowPlaying title change is not a reliable audio
flush command. Do not add an arbitrary type102 buffer clear until its ownership,
flush semantics and timing are understood. Verify pause/resume, seek, Siri,
calls, track skip and session teardown without stale buffered audio.

### 6. Reassess smoothing after the preceding fixes (feedback 7)

The current algorithm starts at the selected delay, rises by up to 10 ms for
late frames, caps at 250 ms and only decays after a quiet interval. Drive 2's
retained tail is near the cap. Keep the existing off/100/150/200 choices while
testing actual priority deployment, reconnect and timestamp continuity. Then
measure delay occupancy, deadline misses and interaction response before
changing rise/decay. Preserving steadiness and lowering control latency need
separate measurements.

### 7. Confirm navigation-card defaults and normal menu access (feedback 10)

Both captures have a valid saved `navigation-card.state` with position=3,
which means Off. That saved preference cannot tell us a fresh install's default.
The frozen settings-v2 vendor source defaults to Right (enabled token on 791),
whereas the current integration source defaults Off. The next build must choose
and verify its actual packaged source rather than relying on workspace defaults.

The settings-v2 base menu source already exposes field 5, Navigation card,
with On/Off for 791. The separate turn-card *layout* tuning preference is not
the On/Off switch. Verify the packaged VCMenu/core pair with no optional tuning
menu, a clean preference directory, saved On/Off, upgrade and reconnect. Ensure
the ordinary menu can disable it and that guidance/HUD data continue when the
visual card is Off. Do not overwrite existing saved user choices to repair a
default.

### 8. Vehicle location forwarding (feedback 11; separate feature)

The earlier exact-binary [GPS audit](../GPS-SOURCE-AUDIT.md) found OEM wired
location support, but no location component advertised by the wireless
receiver's identification. Wireless currently has no established car-GNSS
forwarding path. A source of live OEM NMEA, freshness/validity gating and the
receiver's identification/start/stop/message plumbing all need implementation
and testing. Advertising a component alone does not deliver location.

Reuse the OEM data read-only, verify the exact MU1367 interface and subscription
semantics, and test valid fix, stale/no fix, tunnel/loss, reconnect and wired
coexistence. Do not send guessed coordinates. Treat this as a distinct feature
after connection/timing stabilization rather than hiding it inside an FPS fix.

### Separate wired recovery track (issue #14)

[Issue #14](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/issues/14)
documents a host-reproduced queue flush that can cut an AU after its first TS
packets have been written. The current bridge still discards the queue wholesale
and requires eight fast writes before requesting recovery IDR. The issue gives
evidence for AU-safe flushing; it does not establish that every blocky recovery
shares that cause.

Test AU-safe reset at every discard caller, the requested eight-to-one recovery
change and IDR preservation as distinct changes. Include a slow/blocking writer,
reset mid-AU, generation change, resume with an IDR, ring overflow and ordinary
stream parity. Evaluate queued-IDR recovery only after defining AU ownership
across the writer/queue boundary. Wireless and wired share this bridge, so both
paths require regression coverage.

## First implementation step and package gate

The first functional step is the real-layout reconnect reproduction in item 1,
followed by the sender-context fix and session/cadence checks. Diagnostic work
in item 0 supports that step. No new SD package is justified by this analysis
alone; each implementation step needs recorded evidence and an honest list of
remaining vehicle checks.

Before packaging, retain K4525/P4521 exact gates and verify new unit commands
against matching firmware, as required by `MU1367/AGENTS.md`. Repeat installation
from 1.5.3/1.5.4/1.6.1 and the experimental generation, interrupted-stage recovery,
wireless removal and complete managed OEM restore. Previously modified OEM
files still require valid original snapshots; this is not a generic remover
for arbitrary third-party installations.

## Reproduce this review's numeric evidence

Run `python3 MU1367/wireless-native/research/v162-drive-review/analyse.py`.
It reads the captures and both sealed ZIPs and writes [EVIDENCE.json](EVIDENCE.json)
with complete component hashes, input hashes, retained-window measurements and
the relevant status records. The analysis does not run receiver/hardware code
and does not claim to reproduce the functional faults.
