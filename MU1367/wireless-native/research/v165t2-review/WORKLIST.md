# Test2 follow-up — 2026-11-24

Work is isolated in v166-next; no new package exists. Keep the accepted-session BT guard, media and steady-state video behavior that passed the car tests.

Status: the eight-export audit is in [REVIEW.md](REVIEW.md). The profile-release opt-in, road prefetch fix/output trace and clock-repair attribution are implemented as prototypes and bench tested. Reconnect fallback/stop-reason integration, full ACL release, raw GPS/UTC and startup freeze remain open. Do not package the copied test2 metadata in v166-next.

1. Confirm and retain BT guard attachment, BT-only survival and Wi-Fi teardown across the connection test and both drives. Verify Apple's official session 717 separately from implementation support.
2. Add opt-in phone-requested profile release only after stable accepted ownership and an installed/live guard. Defer during any active/ringing/dialling call or unknown call state. Bound retries, retain BT after repeated short failures, preserve manual stop/wired/ignition semantics. Verify actual HFP/A2DP event and confirmation before claiming released. Full ACL release needs a separately verified device-specific native API; do not power down the whole shared stack speculatively.
3. Audit Wi-Fi-first reconnect intent and expiry. Existing discovery is not proof of bounded same-phone retry or reason-aware stop. Prefer OEM-held ACL, then the last successful accepted wireless phone; respect OEM trust/removal, do not delete pairing stores or use native crash-skip latches as temporary pause controls.
4. Fix/replay prefetched-road invalidation and add worker-flushed f19/f20 accepted-text and blank-reason diagnostics. Keep epoch/source/session protection, reused-index clearing and UTF-8 limits. Empty param 3 must stay distinct from omitted.
5. Attribute PTS rebases to original capture-clock repairs, arrival gaps, presentation/PCR lead and session changes. The mixed BT-on/off intervals do not prove causation. Keep current smoothing and resets until a replay shows a concrete defect.
6. GPS raw GNSS/UTC and main-screen startup freeze remain open. Repeat complete installation, recovery and export gates only when the next candidate is ready; no public upload.

Primary guidance: https://developer.apple.com/videos/play/wwdc2017/717/ (setup disableBluetooth and 2.4 GHz coexistence, reason-aware reconnect, last-device preference, CarPlay Control before Bluetooth fallback).
