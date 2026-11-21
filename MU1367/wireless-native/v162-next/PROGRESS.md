# v1.6.3-e-test2 development — checkpoint 2026-11-20

This directory is an isolated development tree. It retains v162 media/RHD/label
support and adds the first fixes from the [drive review](../research/v162-drive-review/REVIEW.md).
The candidate is v1.6.3-e-test2, with a separate recovery root and explicit v162 migration recognition. Its final installer and recovery gates passed. The installable archive and final package evidence are recorded separately in VERIFICATION.json and dist/v1.6.3-e-test2; the development checkpoint below remains a bench-only record. Stable v1.6.1 and sealed v162 test1 sources and ZIPs remain unchanged.

The [four-export v162 review](../research/v162-test1-review/REVIEW.md) distinguishes the new single-session capture from the earlier v1.6.1 drives. Despite its directory name, it contains v1.6.2-e-test1. Media notification routing and reverse screen return are new fixes from this capture; the native timing, PF, audio and lifecycle changes below were already implemented against the earlier feedback.

[Verification checkpoint](VERIFICATION-DEVELOPMENT.json): 23 evidence reports,
current source/component hashes checked, `ready_to_package=false`.

## Implemented and bench checked

| Area | Change | Evidence |
| --- | --- | --- |
| Media delivery | Send through the registered service's ASL/DSI proxy notification event route, rather than a constructor-selected dispatcher with unrelated listeners. Separate queued/delivered counters. | Separate-dispatcher regression, actual factory event creation/method lookup/listener invocation, wired regressions and native artwork worker pass under factory ARM J9 with and without verification. The ASL event-loop boundary is controlled by the fixture. Captured82,266-byte JPEG also decodes to256×256 under ASan/UBSan. |
| Return after reverse | Preserve pre-borrow CarPlay ownership; submit existing HMI event2910012 after unborrow. | Patched service tests cover duplicate borrows, OEM ownership, explicit take/manual-leave cancellation, stale receipts and missing registration. Factory J9 verifies the class; a back-edge check proves the hook runs every worker iteration. |
| Reconnect timing/IDR | Classify the native sender by its own port and header flag, instead of reading the parent's alt flag through the wrong object base. | Actual pinned sender `0xe6fcc` reproduces the old failure; fixed sender preserves timing/IDR8 on restart, a new accepted session, 61 KB AUs and partial sends. Other ports/unaccepted sessions are excluded. |
| Receiver process replacement | Publish initialized timing rings by atomic rename and reopen the bridge mmap when accepted PID changes. | Factory-QNX test switches accepted ownership to another live PID and a new inode; old mapping stays readable and new timing matches. |
| Timestamp continuity | Calibrate arrival fallback to the last capture anchor. Keep presentation time monotonic with a bounded recovery adjustment; wall-clock smoothing uses the real capture estimate, not that adjustment. | Old production mux produces steps 191,250 then 1 at a correlation miss/recovery; fixed mux produces 2,250 then 2,250 (25 ms each). Host ASan/UBSan run covers 50,000 frames with misses/bursts/session changes. |
| Long-drive diagnostics | Export actual `wcp.log.1`, per-minute bridge summaries and PF readiness. Include timestamp miss reasons/sizes and PTS repair/clamp counters. Suppress unchanged avcC log announcements. | Production collector on factory QNX; two simulated 90-minute processes retain 184 summary records across detailed-log truncation and restart; repeated codec configurations only log changes. |
| Main/AID FPS | Apply wireless FPS to the exact native alt-display type 111 and UUID. Main display keeps its native maximum of 30. | Real display provider returns main30 and alternate20/25/30/40. Unknown type, identity and array count remain unchanged. |
| Video lifecycle | Recognize the exact native tap and bootstrap paths as owners of the video PID receipt. | Actual firmware pidin/ksh/grep/sleep/tail tests cover start/status/stop, preflight, reused PIDs and an unrelated same-basename executable. |
| PF startup | Serialize both callers using a kernel-held lock in the existing managed `wireless-tune` binary. Generate private files, retain active OEM NAT selection, validate before applying, and launch receiver discovery only after success. Autostart retries readiness with a bound. | Factory-QNX tests cover concurrent callers, AP/NAT delay, syntax/apply failure, four uplinks, owner exit and OEM-off restoration. Templates and required utilities audited for K4525/P4521, HW50/70. Kernel/network operations are explicit stand-ins; see limitation below. |
| Audio output scheduling | Apply floor14 to the pinned platform MainHigh/type102 output worker, preserving higher priorities and excluding auxiliary audio. Prefix native output stats with monotonic time. | Real native audio worker (hardware callbacks absent) reads back 10→14 and 20→20, executes its ten-second stats callsite and exits. SDK receive entries already request priority61 and retain their native handling. |
| Wired recovery | Preserve the unfinished AU tail when discarding queued work; permit a current IDR to resume recovery; require one healthy writer block. | ASan/UBSan test reconstructs complete PES payloads at all 1,130 tested packet split/wrap positions: old=1,122 truncated cases, fixed=0. Incoming IDR preserved, one healthy block recovers, no-reset TS output byte-identical. |

The clock's 250 ms outlier threshold is a presentation-continuity safeguard,
separate from the selected smoothing delay. Its epoch adjustment does not become
an added hold. Smoothing choices, delay rise/decay, alt40 and IDR8 are retained.
Vehicle testing must assess visible latency and responsiveness.

## Important limits and remaining work

1. **BT/Wi-Fi connection owner and coexistence:** PF readiness is fixed in this
   development tree, but Wi-Fi-first handoff deduplication, profile teardown,
   inquiry/page suppression, call routing and their restoration need the
   pinned `libbtwcp`/factory-HMI audit and timestamped connection tracing. Do
   not equate PF success with proof that these separate problems are solved.
2. **Audio jitter and skip latency:** output priority and timestamped native
   stats are implemented. Live SDK Late/Missing/Gaps/Rebuffers forwarding and
   the type102 flush/command timeline remain open. The old drive tails do not
   establish a buffer-flush cause. The existing CP service adapter sends
   `postButtonEvent` through its `WC btn` loopback control route on port7104;
   a real wheel-versus-touch trace is still needed to establish each UI path
   and where the 3–5 s delay occurs.
3. **Navigation-card menu/default:** resolve the frozen vendor/current source
   default difference and prove ordinary On/Off access without the tuning
   add-on, preserving existing preferences. Both supplied captures saved Off.
4. **Vehicle GPS:** the [exact-binary audit](../research/GPS-SOURCE-AUDIT.md)
   still applies. Wireless has no implemented car-GNSS producer or location
   subscription. This needs a separate validated OEM-data path.
5. **PF kernel check:** the real firmware parser dry-run cannot complete in
   this VM: `getifaddrs: Address family not supported by protocol family`.
   The VM has neither the vehicle AP nor `/dev/pf`. Generation, locking and
   readiness tests pass against exact OEM templates with explicit query/apply
   stand-ins. Actual parser/application and OEM connectionmanager reloads
   remain vehicle checks. The inserted pass-rule syntax is retained from the
   existing runtime overlay; OEM files are not edited.
6. **Packaging/restore:** assembler integration and v162 recovery recognition are complete. All seven host release groups pass, covering four base variants, v1.5.3/Android Auto, older wireless generations, stable v1.6.1, v162, recovery preservation and diagnostics. Factory-QNX transactions check full install/removal of41 targets and five selected rollback/resume sites. Final evidence and ZIP hashes are in VERIFICATION.json and the dist package directory. These fixture results do not establish a physical vehicle installation.
7. **Vehicle regressions:** the latest single-session v162 capture establishes input priority14 and exposes the notification gap fixed here. The next candidate must establish visible media text/artwork, reverse screen return and audio behavior, VW label, RHD, reconnect smoothing, calls and wired behavior. Bench results are not vehicle results.

No radio, MFi, MOST driver or real audio hardware success is claimed by these
bench tests. Known closed-binary entrypoints remain guarded by the existing
exact receiver hash. No new OEM firmware or SDK binaries are distributed.

## Reproduction

Use `build-components.py` with the exact stable v1.6.1 ZIP and existing pinned
local toolchain, as in v162 development. The current component checkpoint is
`../build-v163t2-components-r5/COMPONENTS.json`.

New notification/screen probes: `media-host.py`, `media-qnx.py`, `screen-host.py` and `TestBorrowedScreen.java`. The exact captured JPEG decode is recorded in the verification checkpoint.

Tests added in the earlier batch:

- `receiver-reconnect.py`: old-bug reproduction or fixed native sender.
- `timestamp-qnx.py`: old/fixed production mux, plus accepted-PID replacement.
- `capture-clock.c`: standalone sanitizer model checks.
- `bridge-diagnostics.py`: repeated configuration and long-summary retention.
- `collector-qnx.py`: combined/standalone export with rotated logs.
- `pf-qnx.py`: actual shell/native lock with explicit kernel query stand-ins.
- `pf-firmware-audit.py`: four exact firmware/template/utility profiles.
- `bridge-recovery.py`: full PES reconstruction across every reset position.

The retained `receiver-tap.py`, `launch-lifecycle.py` and `unit-tools.py` have
also been extended/run for the changed behavior. Verification evidence binds
the tested sources and component hashes; old unsuccessful harness runs remain
in ignored build directories for traceability.
