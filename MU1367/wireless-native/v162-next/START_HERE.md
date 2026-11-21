# v1.6.3-e-test2 vehicle test

For MU1367 K4525/P4521 and AID 791. Copy the entire ZIP contents to the SD root, retaining Toolbox and Custom. Refresh Toolbox menus/scripts from this SD before opening GEM. Disconnect phones and fully reboot before installation.

In GEM, run **CarPlay Maps → Install**. Follow every full-reboot instruction and repeat Install until v1.6.3-e-test2 reports installed. From v1.6.1 or v1.6.2, the first stage restores the saved wireless layer, followed by installation after reboot. v1.5.3/v1.5.4 can require further checked migration stages. Keep all recovery folders.

Pair normally through Bluetooth; the wireless handshake joins Wi-Fi. Retain the same 40 fps / IDR8 / 150 ms settings for comparisons.

1. Export standard diagnostics after a cold wireless connection, then again after disconnect/reconnect. Timing magic and sequence should advance, the accepted session should match, and an IDR receipt should appear. Confirm smooth AID motion and zooms. Main-screen demand remains its native 30 fps; the 40 fps option applies to AID.
2. Play and skip tracks in several apps; confirm title/artist/album, playback state and the correct cover on AID and MU. WCPMEDIA2 reports queued and delivered counters separately. Pause/resume, stop and seek, then check that an old cover never appears for a newer track.
3. Select reverse repeatedly with music playing. Compare audio stutter, AID gaps and main-screen return. If CarPlay was visible before reverse, it should return after the popup closes. If the OEM screen was active, it should remain active. Explicitly leave CarPlay during a borrow and confirm it does not reopen automatically.
4. Confirm RHD/LHD and Volkswagen icon label after cold boot and reconnect. Connect by cable and verify maps, guidance, media text and artwork still work.
5. Export **standard diagnostics** while any fault is present. This includes wireless state, rotated receiver logs, minute summaries, media metadata and the completed cover snapshot. Review identifying data before sharing.

**Recovery:** use this candidate SD's Remove wireless or Recovery, then fully reboot. Removal restores the saved base, including its audio and wireless service JAR preimages. To return to stable v1.6.1, run the stable installer after removal and reboot. **Restore OEM** uses the checked staged restore; repeat it after each requested reboot. Older SD scripts do not recognize this future recovery generation.

BT profile release remains opt-in and unchanged in this candidate. Wi-Fi-first connection arbitration, live SDK jitter counters, track-skip latency and car-GNSS forwarding remain open; see RELEASE-NOTES.md. No radio, MFi, MOST or physical audio success is inferred from the bench tests.
