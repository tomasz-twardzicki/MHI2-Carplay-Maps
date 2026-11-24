# v1.6.2-e-test1 vehicle test

For MU1367 K4525/P4521 and AID 791 only. This is an experimental build; bench verification does not establish in-car timing or rendering results.

Copy the entire SD ZIP contents to the SD root. Keep both Toolbox and Custom. Disconnect phones and fully reboot before starting.

Run **CarPlay Maps → Install** in GEM, then follow each full-reboot instruction. Repeat Install after each reboot until the candidate reports installed. From v1.6.1 this first restores the saved wireless layer, then installs the new generation after reboot. From v1.5.3/v1.5.4 the existing checked base migration remains available; it can require further reboot-and-repeat stages. Do not remove or rename recovery folders.

Pair/connect normally using Bluetooth; the wireless handshake joins Wi-Fi automatically. Reconnect CarPlay to obtain the refreshed `/info` menu label.

Test:

1. With wireless maps active, select reverse several times and compare freezes/frame gaps with v1.6.1. Keep the same FPS, IDR and smoothing settings for this comparison. The input log should show `WCP_PRIORITY` with `after=14` or higher and `error=0`; higher native priorities must remain higher.
2. Confirm **Volkswagen** below the OEM icon and the correct RHD/LHD layout after a cold boot and reconnect.
3. Play several tracks in different music apps. Check title, artist, album and the corresponding image on both AID and MU. Pause/resume, stop/restart and seek. Change tracks quickly and check that a late old image is never shown on the new track.
4. Disconnect/reconnect wireless, then connect by cable. Confirm wired maps, guidance, text and artwork still work, and wireless data does not replace wired media.
5. Export **standard diagnostics** while the symptom is present. The combined export includes wireless scheduling logs, media counters, the current metadata envelope and completed cover snapshot. Session/track metadata and the image are part of this debug capture.

**Recovery and OEM restore:** use this candidate SD's Remove wireless or Recovery first, then fully reboot. Wireless removal restores the saved v1.5.4 base, including its audio JAR, and removes the added decoder. To return to stable v1.6.1, run its complete installer after this removal and reboot. Use this candidate's **Restore OEM**, following reboot-and-repeat instructions, for the full factory restore. Unwind this candidate before using older SD restore scripts, which cannot recognize a future recovery generation.

Please retain before/after diagnostics for the reverse-load comparison. This build has not yet demonstrated that priority 14 eliminates the 821 ms freeze in the vehicle.
