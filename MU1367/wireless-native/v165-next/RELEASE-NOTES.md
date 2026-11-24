# v1.6.5-e-test1

Follow-up to the supplied v1.6.4 drives; local experimental candidate, vehicle validation pending.

- Fix BT guard startup attachment for the pinned lazy-binding slots; add a bounded 60-second retry, atomic conflict/race handling, known native overwrite repair and precise stage/slot status. Retain fresh accepted-session gating for BT-loss survival and reconnect/paging/resend suppression.
- Add GEM next/current/off dial-road choices, using the exact active manoeuvre's upcoming-road field on wired and wireless. Protect route/head freshness, index reuse, prefetched heads and the existing UTF-8 limit. Default remains current.
- Retry artwork publication when the picture server changes. Expose stage/handle/server state and bounded metadata/cover-transfer events without weakening track identity checks.
- Add main-display ownership and native launch traces with explicit clock fields for the MU-only startup freeze. No speculative foreground or stream-timing change.
- Expand GPS status to show actual source/fix/UTC health and receiver counters. Capture bounded read-only bootstrap/clock qualifications and claim reasons where the DIO launcher executes.
- Include all new evidence in normal base diagnostics and the separate wireless collector. Preserve complete managed installation, previous-layer/reboot recovery and OEM restore across 45 targets and the new preference metadata.

Vehicle GPS remains unresolved for wireless-only sessions because DIO is absent; HMI position and UTC observations have not established a raw GNSS producer. Forwarding/probe remain off by default. The startup freeze, complete artwork presentation, pre-acceptance Wi-Fi-first/last-phone arbitration, track-skip delay and SDK/radio instrumentation remain open. Retain 40/8/150, native main demand 30 and the established timing, audio, RHD, guidance and reverse-return fixes.

Host and factory-QNX evidence is shipped with the package, including managed restore and interruption checks. The earlier input-preload fixture failure is resolved: sequential ring allocations exhausted the RAM disk; cleaning and syncing between runs makes both released-control and candidate pass. Production input code was not changed for that result. Sealed stable and prior experimental archives remain unchanged. No public release upload is part of this build.
