# v1.6.3-e-test3 changes

- Add a hash-pinned BT-only module extending the exact wireless add-on's private guard probes. A fresh advancing accepted receiver/session lease preserves AirPlay on bootstrap BT/iAP2 loss, pauses RC reconnect attempts and guards redundant session-start probes. Stale/inactive ownership, receiver receipt loss, wireless disable and wired takeover release the guard. The OEM Bluetooth binary and vendor library files remain unchanged.
- Verify both add-on/guard hashes before wrapper activation. Missing or changed inputs fall back to OEM BT. No boot crash latch, user reconnect preference or profile-release flag is fabricated. BT audio-profile release stays opt-in.
- Export timestamped BT owner status and bounded lifecycle history, including preservation/pause counters.
- Add bounded artwork exception/gate history, error phase/class/message/sequence and per-track source/identity diagnostics. Inactive wireless with no USB source no longer opens wired PPS metadata. Collector includes both trace histories. This does not repair missing phone metadata/transfers or guarantee artwork on every track.
- Retain test2's timing/IDR reconnect, reverse return, audio-output floor, PF readiness, RHD/label and wired behavior. Add a separate recovery generation recognizing test2 and v162.

Experimental: actual radio/control timeout, in-flight connection races, calls and multi-phone behavior require vehicle validation. The BT guard's QNX fixture executes native decision paths with hardware boundaries stubbed; it does not emulate a Bluetooth controller or AirPlay peer. Wi-Fi link counters and SDK jitter/skip tracing remain open.
