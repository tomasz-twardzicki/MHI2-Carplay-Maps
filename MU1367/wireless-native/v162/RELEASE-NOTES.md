# v1.6.2-e-test1 — wireless test candidate

- Raise the wireless alternate sender and port-9997 input adapter to a priority floor of 14 without lowering existing higher priorities or changing scheduling policy.
- Capture native iAP2 0x5001 metadata and completed artwork into session-bound RAM snapshots. Deliver text, playback state, position and normalized artwork through the MU1367 factory dispatcher and existing AID text/picture paths.
- Confirm pending factory media subscriptions; retain incremental metadata, restore text after stop/resume, and replay state to newly registered HMI listeners.
- Reject incomplete, oversized, malformed or stale media and covers. Bind file transfers to their starting track identity, including reused transfer IDs. Decode images in a supervised child with a five-second timeout and the existing 800 KB input, dimension and memory limits.
- Set the OEM menu icon label to Volkswagen in both the RAM-only receiver configuration and late /info refresh, independently of driver-coding readiness.
- Retain stable v1.6.1 map/guidance/tuning runtime and checked migration from earlier layers. Add an independent 41-target snapshot/recovery generation and media evidence to standard diagnostics.

QNX receiver, factory ARM J9 and host sanitizer tests are recorded in VERIFICATION.json. Vehicle validation and reverse-load timing comparison are pending.
