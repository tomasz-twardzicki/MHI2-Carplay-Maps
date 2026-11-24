# v1.6.5-e-test2 review — 24 November 2026

All eight archives match the sealed test2 receiver launcher, tap, tuning tool,
bridge, supervisor and BT guard. The exports overlap: four describe the
connection/reconnect boot, two drive 1, and two the separate GPS-probe drive.
[EVIDENCE.json](EVIDENCE.json) retains archive hashes and per-boot summaries;
[analyse.py](analyse.py) reproduces them without publishing device addresses,
coordinates, road names or track text.

## Confirmed baseline

The guard attaches on attempt one with `stage=ready`, `open=ours`, `write=ours`.
The snapshots retain BT-only preservation and accepted-session paging/resend
suppression; none of the retained native BT logs contains the old forced
`WC bye` message. This agrees with the user's BT-off survival and Wi-Fi-off
teardown tests. The independent default/libc symbol lookup fix is retained.

Drive 1 has eight unique summary rows, with a maximum PTS interval of about
150 ms. The connection/reconnect boot reaches about 796 ms; drive 2 reaches
about 921 ms. These are PTS intervals, not direct measurements of screen
presentation or network throughput. Do not infer radio improvement solely
from bitrate during zoom spam, or sum overlapping cumulative counters.

## Ordered changes

1. **Phone-requested BT profile release.** The native command is already
   received, but the legacy HMI path defaults to keeping profiles. Its old
   `wcp_bt_released` marker is written before asynchronous disconnect dispatch,
   so that marker is not proof of success. The prototype adds an opt-in choice
   `keep / profiles / status`, a session-qualified command mailbox, five seconds
   of stable accepted ownership, a fresh installed guard, current OEM trust,
   known idle call/profile state, bounded retries and a short-failure circuit
   breaker. Requested and confirmed states are separate. Only the existing
   factory phone-disconnect event is used; no reconnect request is generated.
   Full ACL release and a global stack toggle are not implemented by this step.
2. **Reconnect order and Wi-Fi-first arbitration remain next.** The pinned
   selector at `0x252bc` already scans all its native candidates for an OEM-held
   ACL at `0x254fc..0x25570`, using lookup `0x25068` and state `3`, before native
   paging fallback. A later "OEM-held" log does not establish that the ACL was
   visible at the first attempt. The logs do confirm stale fallback candidates
   and exponential backoff; drive 1 has three failed ACL attempts before reuse.
   Improve the fallback only after tracing its cursor, failures and current
   OEM trust. The native test-address override bypasses the normal scan and is
   not an appropriate last-phone preference. The crash-skip latch and user's
   persistent reconnect-off preference must not become transient policy flags.
   Native periodic CarPlay Control discovery also does not establish a bounded
   same-device Wi-Fi-first window or distinguish unreachable from explicit
   disconnect, wired takeover and ignition off. Those stop reasons must be
   carried into the fallback policy before enabling automatic retries.
3. **Road prefetch and observable output.** Drive 1 reports 367 current-road
   fields, 307 nonempty; drive 2 reports 383/255. Explicit empty param 3 remains
   distinct from omission. There is a reproducible model defect: a fresh
   manoeuvre cached before entering the short route order could be erased by
   the head-change rule. The prototype preserves unused prefetched roads,
   retires consumed heads and still clears reused indices and source/session
   epochs. It logs actual f19/f20 text with submission acceptance and blank
   reasons, including absent/empty fields, reused heads, stale route status,
   rerouting and missing current ownership. This fixes a proven model case;
   it does not prove that case was the only cause of the vehicle's blank dial.
   Latest mailboxes and the stopped-route adapter snapshot cannot reconstruct
   the earlier complete cache. One drive-1 ownership gap is about 2.6 seconds;
   it is not evidence by itself of root switching or cache erasure.
4. **PTS attribution.** The current `reason` in continuity logs describes
   timing correlation, not the repair cause. A repair occurs for an adjusted
   duplicate/backward capture or a forward gap over 250 ms. A separate PCR-lead
   rebase shifts presentation to remain ahead of the running transport clock.
   The prototype logs these causes independently with original capture,
   arrival, previous output, adjustment, period, session and PCR context.
   Smoothing, deadlines, repair thresholds and reset rules are unchanged.
   The retained evidence does not prove BT-off causes the rebase spikes.
5. **GPS remains unresolved.** The probe has 273 positions, zero live/boot
   clocks, no proven raw GNSS, and 24 map-matched rows in the last 32 retained
   positions. PosPosition must not be relabelled as raw GPS or paired with an
   invented UTC clock. A real raw GNSS/UTC producer is still required.
6. **MU startup freeze remains unresolved.** Keep the existing launch and HMI
   ownership traces. The clean drive does not demonstrate that startup or
   reconnect behavior is fixed.

## Validation boundary

The prototype is isolated in `v166-next`. It is not an installable package and
still carries test2 recovery/build placeholders. Old sealed source directories
and release ZIPs remain unchanged. Before packaging, allocate a distinct root,
pin test2 migration, retain preference archival and complete all installation,
rollback, OEM restore, firmware import and assembled GEM/export checks.

Factory ARM/J9 tests cover the independent road functions and accepted/rejected
trace, profile policy, media and reverse-return regressions. Native QNX tests
cover the actual receiver command tail, ownership binding, the preference tool,
SD remount preflight and diagnostics collection. Phone actions/radio, call
transitions and physical cluster rendering still need vehicle validation.

Apple's [WWDC17 session 717](https://developer.apple.com/videos/play/wwdc2017/717/)
supports honoring the phone's disableBluetooth request, avoiding Bluetooth
interference on 2.4 GHz, last-device preference and CarPlay Control reconnect
before Bluetooth fallback. Releasing HFP/A2DP is only a first experiment; it
does not demonstrate that every Bluetooth connection or the stack is off.
