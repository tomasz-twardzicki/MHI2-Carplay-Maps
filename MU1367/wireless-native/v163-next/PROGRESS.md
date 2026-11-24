# v1.6.3-e-test3 preparation — 2026-11-20

Baseline: sealed test2. The new [BT-only feedback](../research/v163-test2-review/REVIEW.md) confirms a real bootstrap-BT teardown defect separately from Wi-Fi loss. [Implementation contract](../research/v163-test2-review/BT-POLICY.md).

## Implemented

- A hash-pinned BT-only module extends the exact wireless add-on's private GOT probes. A fresh accepted receiver/session lease preserves AirPlay on BT/iAP2 close, pauses outbound reconnect checks and guards redundant accepted-session resend probes. No global open/write override or OEM BT patch. Real profile-release and reconnect preferences retain their original meanings.
- Accepted ownership needs an advancing heartbeat and expires after1500ms without advancement. Session changes warm up again; owner receipt loss, inactive session, disable and wired takeover release the pause. AirPlay/control close/keepalive remains the teardown authority. No crash latch or persistent pause flag is created.
- Checked wrapper activation and OEM-BT fallback on changed inputs. Timestamped status/lifecycle history is included in standard diagnostics. Profile release remains opt-in/off by default.
- Artwork phase/class/message/error sequence and bounded gate traces, plus the absent-USB PPS fallback fix. Skip/reconnect decode and injected exception tests pass on factory ARM J9. Missing-current UID/cover remains a separate diagnosis; stale images remain excluded.
- Test2 timing/IDR/reverse/audio/PF/RHD fixes retained. Receiver-alt already runs at60 and is removed from the open tuning worklist.

## Verification/package state

Components: build-v163t3-components-r5. Native BT decision paths pass with hardware boundaries explicitly stubbed. Launcher hash/pre-exec checks and wrapper activation/fallback pass with only final OEM exec captured. Current/native libraries resolve against all K4525/P4521 HW50/70 firmware profiles. Artwork uses byte-identical JAR/decoder evidence from its passing batch.

The candidate is staged in build-v163t3-stage-r1 with42 managed targets and a separate v163t3 recovery root. It recognizes exact sealed test2 and v162 controllers. All seven host release test groups passed, including upgrade from test2/older versions and OEM restore across four base variants. QNX full42-target install/removal, four rollback/resume sites, release orchestration and combined diagnostics also passed. Final package evidence is recorded in VERIFICATION.json and dist/v1.6.3-e-test3. Earlier test ZIPs/source evidence remain unchanged.

One repeated tools fixture failed the unchanged input-adapter self-test before reaching wrapper checks (tools-qnx-r2). The same gate source/tap/input bytes passed r1 and r3; the cause of that isolated failure is not established. The failed fixture is retained. Current r3 also passes wrapper activation and hash-drift fallback.

## Vehicle acceptance and remaining work

Use START_HERE.md: cold reconnect, phone BT-off with healthy Wi-Fi, Wi-Fi-off/native timeout, both reconnect orders, audio/Siri/calls, another paired phone, wired takeover and reverse. In-flight Bluetooth attempts and actual radio/control timeout behavior are not emulated. Pre-acceptance Wi-Fi-first arbitration remains separate from accepted-session suppression.

Artwork identity/FT sequencing, audited Wi-Fi link counters, SDK jitter/track-skip timing, navigation-card defaults and car GNSS forwarding remain open. No hardware result is inferred from the bench checks. Both firmware gates and complete managed snapshot/OEM recovery are retained as package requirements.
