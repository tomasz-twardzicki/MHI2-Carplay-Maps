# v1.6.3-e-test2 changes

- Correct native timed sender classification, including reconnect/session replacement. Preserve IDR8, correlation and smoothing; atomically replace timing rings and reopen the bridge mapping for a new accepted receiver PID.
- Route wireless NowPlaying through the factory ASL/DSI proxy notification event path used by the registered service. Remove the unrelated dispatcher-constructor hook. Report queued versus delivered counters.
- Restore CarPlay through the existing HMI event after unborrow only when it owned the screen before borrow. Duplicate borrows preserve ownership; manual leave, explicit take and expired sessions cancel restoration.
- Apply priority floor14 to the pinned MainHigh/type102 audio-output worker while preserving higher priorities. Retain receiver-alt and input priority handling. Timestamp native audio-output statistics.
- Restrict FPS tuning to alternate type111 and UUID; main display retains native30. Preserve capture-clock continuity through timestamp misses.
- Serialize PF readiness before discovery, retain OEM uplink/NAT selection and bound autostart retries. Recognize exact video bootstrap/native process paths for lifecycle checks.
- Retain bounded per-minute wireless summaries and rotated receiver logs in standard diagnostics. Preserve full video AUs across wired queue recovery.
- Keep exact firmware gates for K4525/P4521 HW50/70, staged migration, snapshot recovery and OEM restore. Recognize the sealed v1.6.2 recovery generation.

Known limits: vehicle validation is pending. PF kernel/application checks require the vehicle AP and /dev/pf; the VM tests use explicit network/kernel stand-ins and do not establish real packet-filter success. BT audio-profile release remains the upstream opt-in, with no new automatic teardown. Wi-Fi-first arbitration, detailed SDK jitter/skip timing, navigation-card default reconciliation and car-GNSS forwarding remain open. The main-screen30 ceiling is deliberate; the current receiver's verified native display contract supports it.
