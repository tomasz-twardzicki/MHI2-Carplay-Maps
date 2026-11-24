# v1.6.3-e-test3 vehicle test

MU1367 K4525/P4521 and AID791 only. Copy the complete ZIP to the SD root and refresh Toolbox menus/scripts. Disconnect phones and fully reboot before installation. In GEM run **CarPlay Maps → Install**, follow every full-reboot instruction, then repeat Install until test3 reports installed. From test2 this first restores its saved wireless layer. Keep recovery folders; do not edit receipts or STATE files.

Keep40/8/150. Export standard diagnostics immediately after connection and during any symptom.

1. Cold start: normal Bluetooth-assisted wireless connection should work. Verify maps, guidance, text, RHD and Volkswagen label. BTSESSION1 should become installed=1/live=1; its counter should advance.
2. With CarPlay working over Wi-Fi, turn phone Bluetooth off. Main/AID maps and audio should continue. Diagnostics should show bt_preserved increasing, with no WC bye caused by that BT close. RC should not keep paging absent phones or reopen iAP2 during the accepted session.
3. Turn phone Wi-Fi off. Record how quickly AirPlay ends and BTSESSION1 becomes live=0. This guard never owns AirPlay teardown; it must retain the receiver's native control-close/keepalive handling. Then turn Wi-Fi/BT back on and verify reconnect, timing correlation and IDR8. Repeat in both orders and test another cold boot.
4. Test incoming/outgoing calls, Siri and a second paired phone. BT audio-profile release remains the existing opt-in and is not enabled by this candidate. The new guard creates no release or reconnect-preference flags.
5. Play/skip tracks and check covers. Inspect cpmap-artwork.status plus the current/prior artwork trace in standard diagnostics: phase, actual exception class/message, error sequence, keep/source-live and generation/UID/cover readiness. Missing-current-cover and stale-image rejection are distinct from decoder errors; artwork completeness still needs diagnosis.
6. Verify reverse return, audio and wired maps/guidance/media. With wired takeover the BT-session guard should stop claiming wireless ownership. Export after cold connection, BT-off, Wi-Fi-off and reconnect so the transition is captured.

**Recovery/OEM restore:** use this test3 SD's Remove wireless or Recovery, then fully reboot. It restores the saved base and removes the added guard/decoder. To install stable1.6.1, unwind test3 first and reboot. For complete OEM restore use this SD's Restore OEM and repeat after each requested reboot. Older SD restore scripts do not know this recovery generation.

Physical BT/Wi-Fi loss behavior, native AirPlay timeout duration, calls and multi-phone operation remain car checks. Bench tests stub hardware boundaries explicitly. Wi-Fi link counters and detailed SDK jitter/track-skip timing remain future work.
