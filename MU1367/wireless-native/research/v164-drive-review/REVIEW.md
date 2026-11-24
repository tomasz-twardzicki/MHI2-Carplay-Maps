# v1.6.4-e-test1 drive review — 2026-11-23

Reviewed all four ZIPs from `Logs/wireless/v1.6.4` and the supplied feedback. The two standard/standalone pairs belong to two drives, not four independent tests. Both drives' runtime fingerprints match the sealed v1.6.4-e-test1 launcher, tap, tuning tool, bridge and supervisor. This review changes no sealed runtime or package.

[Reproducible analysis](analyse.py), [capture evidence](EVIDENCE.json), [factory API contracts](FACTORY-API.json).

## Results to retain

| Observation | GPS off | GPS option/probe on |
|---|---:|---:|
| Last retained minute-summary timing matches | 40,650 | 38,829 |
| Timing misses / bridge drops | 0 / 1 | 0 / 1 |
| PTS clamps / rebases / slow writes | 0 / 0 / 0 | 0 / 0 / 0 |
| IDR cadence, frames per keyframe | 7.99 | 7.99 |
| First full minute maximum PTS step | 225 ms | 250 ms |
| Subsequent maximum minute PTS step | 225 ms | 150 ms |
| Sampled smoothing demand, median | 160.5 ms | 165.5 ms |
| Bridge latency resets | 0 | 1, already present in first minute |
| Standard-export artwork fetches / errors | 5 / 0 | 7 / 0 |
| Standard-export artwork responses / HMI errors | 0 / 0 | 0 / 0 |
| BT guard installed | 0 | 0 |
| GPS source / advertised / requested / sent | absent / inactive | 0 / 0 / 0 / 0 |

These PTS intervals are not direct measurements of screen presentation or a wall-clock freeze. `delay_ms` is sampled smoothing demand, not end-to-end video latency. Main/alternate retained receiver FPS medians are approximately 22.2/22.8 and 21.4/23.1. The timestamped audio records retained in the rotated logs cover roughly the last 5–8 minutes, with output equal to MPL5 writes and no inactive/error count; they do not independently cover the entire drive. User observation supplies the longer continuous-audio report.

The on-drive GPS experiment sent nothing, so the smoother feel cannot be attributed to car GPS forwarding. Keep 40/8/150 and the working timing/audio/IDR path while addressing the following items.

## 1. BT guard attachment — first implementation priority

Confirmed: the module executes once at 8.711 s / 9.297 s uptime, logs `not-installed-contract-or-library-mismatch`, writes `installed=0` and stops its watch worker. Its owner-preservation, reconnect pause and resend guard therefore never become active. BT-off survival is not fixed on these cars.

The supplied lazy-binding explanation is consistent with the exact pinned third-party ELF:

- No `DT_BIND_NOW`, `DF_BIND_NOW` or `DF_1_NOW` flag.
- `open` at 0x47878 and `write` at 0x47860 are R_ARM_JUMP_SLOT relocations (22).
- Both file slots initially contain 0x272f0, the add-on's PLT resolver entry; their runtime unresolved value is base+0x272f0.
- The four instruction contract words match the production guard's expectations.
- Production currently accepts only resolved libc values and has a single attach attempt.

The exported log does not identify which check failed and contains no live GOT values. Lazy binding is a strong explanation, not a proven live failure stage. The patch mentioned in the feedback is not present as a separate file in these four archives or the pasted attachment; the binary contracts are sufficient to implement and test an independent correction.

Work items:

- [ ] Give every failure stage a bounded reason: hash, load/symbol lookup, contract word, open/write slot, competing hook, attachment race. Include relative slot category/value and attempt number; avoid pairing data.
- [ ] Permit only the exact native resolver stub, exact libc target or our own existing hook. Reject other hooks and altered code.
- [ ] Retry attachment for a bounded startup window (suggested 60 s), retain/reuse the loaded handle, and keep hashing/dlopen/logging off a high-frequency retry loop.
- [ ] Use guarded atomic slot updates and revalidate installed hooks. Repair only a known native lazy-resolution overwrite; do not overwrite a competing hook. An unsafe/conflicting state must revoke our live guard.
- [ ] Test unresolved/resolved/mixed slots, delayed availability, in-flight resolver overwrite, conflict refusal, expiry, wired takeover and real user BT preferences on QNX. The earlier fixture disabled the add-on constructor and loaded it with RTLD_NOW, so it did not exercise this startup condition.
- [ ] Car test: BT off preserves a healthy accepted Wi-Fi/control session; Wi-Fi off tears down through the native control/timeout path; a later ignition/reconnect works.

## 2. GPS source — architecture change, not another reboot

Confirmed: both wireless process snapshots lack `dio_manager.real`. The GPS-on capture has both option files, 1,424 HMI position events, no DIO attempt marker, no WGPS source file and receiver `source=0 advertised=0 requested=0 sent=0`. The DIO wrapper cannot claim or start its capture when DIO is absent. The missing attempt file does not distinguish an early failed claim from a wrapper never launched by itself; the process and launcher observations establish the latter explanation here.

The DIO-based passive implementation cannot supply vehicle GPS in these wireless-only sessions. Do not start the USB DIO/audio service simply to obtain location. Retain the receiver protocol/framing and stale/source/session protections, but replace the wireless producer dependency.

The HMI source needs qualification before generating NMEA. The factory `DSINavigation` class defines `RELIABILITY_BIT_MATCHED_TO_DIGITAL_MAP=1024`. In the last 32 GPS-on probe records, 10 have reliability 44544 (0xae00, map-matched bit set), and 22 have 43520 (0xaa00, bit clear). All retained records have state=2 (factory 3D-fix constant) and DSI validity=1. A cleared map-matched bit does not prove raw GNSS; some observed coordinates explicitly are map-matched.

Clock discovery also needs care. The passive ClockGPSSyncData probe received zero events. `SoPosTimeInformation` looked like a possible alternative, but the actual `PosTimeInfo` class contains timezone offset and DST transition fields, **not current UTC**. It cannot timestamp RMC/GGA fixes. The native position provider exposes `carsensordata2` GPS base/time/quality/velocity types, worth investigating as a read-only raw source; their presence alone is not a working service client.

Work items:

- [ ] Extend read-only diagnostics to identify raw/fused/map-matched position source, units, validity, demo state and an independently valid UTC/date source.
- [ ] Prefer a read-only OEM GNSS/NMEA service available without USB, or a verified HMI-side raw provider binding. If only fused/map-matched data is available, define its proper protocol semantics rather than claiming autonomous GNSS.
- [ ] Add explicit read-only notification subscriptions if needed to obtain initial clock/position values; preserve OEM listeners and settings. Do not use clock setters or the MMX Jan-01 clock to manufacture GPS UTC.
- [ ] Do not make a cached stationary coordinate appear freshly observed merely by updating its timestamp. A 1 Hz stationary output needs independently fresh fix/receiver status and UTC; stop on loss, stale source, demo or replacement.
- [ ] Make GEM status show option state **and** actual producer/PID, fix age, validity/source type, UTC readiness, advertised/requested/sent counters and last failure reason. Preserve read-only status and explicit enable/disable behavior.
- [ ] If retaining the DIO diagnostic path, log whether its wrapper was invoked and distinguish option-off, hash failure and attempt-exists. Missing wrapper output must not be reported as a particular claim failure.
- [ ] Keep GPS off by default until source/UTC contracts and stale/parked/reconnect behavior are proven; re-run the native receiver and full managed recovery tests for the replacement producer.

## 3. Requested dial road label — supported by captured payloads

Each retained mailbox contains six 0x5202 manoeuvres, all with non-empty parameter 4. The route source in both mailboxes identifies Google Maps. This establishes availability in these captured snapshots, not every message over the entire drive or behavior of Apple Maps/Waze.

The current implementation deliberately renders `RoadName.current()` into `turnToInfo`; cached `raw[4]` is used only when a manoeuvre has passed. The requested behavior requires a route-model/rendering change, not a wireless transport change. The same new guidance JAR can serve wired and wireless.

Work items:

- [ ] Expose the upcoming-road text from the active current manoeuvre, tied to route epoch, exact manoeuvre index and fresh route state.
- [ ] Clear on reroute/route/source/session reset or an unknown/mismatched head. Correctly handle look-ahead records already received for the same route and index; do not require an unnecessary resend that an app may never send.
- [ ] Add GEM next road / current road / off choices with the existing strict UTF-8 and 75-byte limit. A missing upcoming field may be blank; never show a previous manoeuvre's road as the next road.
- [ ] Test index advance/reuse, reordered and prefetched records, route deltas, stale route, missing/empty field, reroute and both connection roots. Compare roundabout/exit/junction labels on Google Maps, Apple Maps and Waze in the car.

## 4. Artwork — two remaining paths, earlier exception issue improved

The standard captures report 5 and 7 fetches with `errors=0`, `hmi_errors=0`, `error_seq=0`. No `error` or `decode-rejected` event appears in their retained traces. The old worker-Throwable symptom is not reproduced.

Many gate transitions have no usable UID/cover or no matching metadata. Current native parsing clears identity on a title change without UID and advances generation for artist/album changes. This is conservative against wrong-track artwork, but the current logs lack the complete metadata-field and file-transfer timeline needed to distinguish legitimate track changes from partial/late updates. `text_match=0` with `metadata=0` does not independently prove an actual text mismatch; the metadata object is absent.

There is also an unresolved publish path: `responses=0` even though some decodes succeed. Current counters cannot distinguish a missing CurrentStationHandle stage, source eligibility, failed handle acceptance or missing picture-server attachment. Successful PNG decoding is not evidence that the AID/MU displayed it.

The later GPS-off standalone export contains a sixth successful decode at 1,911.178 s, after its earlier standard export's five-fetch status. Do not combine those two moments into one final status.

Work items:

- [ ] Add bounded identity/generation/field-presence and cover-transfer start/completion/reject reasons, without raw titles or track IDs in summaries.
- [ ] Reproduce partial metadata, delayed UID, same-UID text edits, delayed/reused cover IDs and skip timing. Reconcile deltas with explicit identity evidence; do not retain/rebind a previous song's cover just to increase fetch counts.
- [ ] Expose stage/server attachment, source eligibility, wanted/filled/accepted/pushed handles, request/response counts and publishing exception phase. Verify actual CurrentStationHandle processing and picture-service selection on this firmware.
- [ ] Test MU and AID independently, including source switches, skip, reconnect and wired regressions.

## 5. Startup — distinguish radio arbitration, ownership and video timing

Both boots send CarPlayStart three times; cp_watch reports established after 5,196 ms and 9,261 ms respectively, relative to that watch's start. The slower drive logs an absent-phone ACL failure and 10 s retry before reusing the phone's OEM-held ACL. Pausing RC only **after acceptance** cannot fix that pre-acceptance selection order. Do not claim the accepted-session BT guard alone fixes the slow startup or all start resends.

The MU controller logs session-up around 35.197 / 70.158 s boot uptime. The GPS-on run hides the canvas around 40.316 s and shows it again around 127.875 s. The other run has repeated borrow/take/visible transitions. The user has now confirmed that the startup freeze affects the main infotainment screen only. Duration, touch/audio behavior during that specific freeze and the initiating action are not established. The ownership events may include user/popup actions. One first-minute AID bridge latency reset is real, but it does not establish the cause of this main-only symptom. The primary video logs show advancing input/decoded counts with no reported decoder errors or drops in their startup samples; these counters do not prove that fresh images were presented. Primary-stream delivery, decoder/output-layer presentation and HMI foreground ownership therefore need separate correlation. Do not align the video process-relative timestamps directly with the HMI timestamps without establishing their clock offset.

Work items:

- [ ] Investigate an existing matching OEM ACL and the previously successful phone before paging unrelated absent phones; preserve pairing and multi-phone/call policy.
- [ ] Suppress redundant start resends only after verified control/session progress. An AP interface merely being up is insufficient evidence that the phone owns a live CarPlay session.
- [ ] Keep bounded first-connection timestamps for native control, primary/alternate stream, decoder/bridge, IDR/config readiness and MU foreground ownership.
- [ ] Trace the main-only freeze through primary stream receive, decode completion, actual output-layer presentation and HMI canvas ownership. Record timebase/offset explicitly. Leave the healthy AID smoothing path unchanged unless new evidence implicates it. Exercise reverse/popup return and genuine manual exits; avoid forcing CarPlay foreground against user intent.

## Implementation sequence before another package

1. BT attach/lazy-binding lifecycle and precise status; verify native/QNX conflict and expiry cases.
2. GPS read-only source/UTC qualification and meaningful GEM health status. Do not bundle synthetic autonomous-GNSS claims from the current map-matched probe.
3. Next/current/off road-label model and GEM option with wired/wireless replay tests.
4. Artwork identity/transfer and HMI publishing instrumentation plus evidence-based fixes.
5. Main-display startup receive/presentation/ownership work, preserving the stable alternate/AID path.
6. Only then assemble the candidate: preserve K4525/P4521 HW50/HW70 gates, exact legacy roots, previous-layer/reboot paths, all newly managed targets/preferences, complete OEM restore and normal diagnostic export. Repeat final package integrity and recovery checks.

No new test ZIP or runtime patch is claimed by this analysis pass. Wi-Fi-first pre-acceptance arbitration, track-skip delay and deeper SDK jitter/link tracing remain tracked work, rather than being inferred fixed from the stable video drive.
