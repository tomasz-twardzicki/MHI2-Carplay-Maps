# v1.6.4-e-test1: install and test GPS

This is an experimental MU1367 package for exact supported K4525/P4521 firmware. GPS forwarding and the GPS diagnostics probe start off. The existing wired path is unchanged.

1. Extract the complete ZIP to the SD root and use the included GEM release installer. Use the included complete package when migrating from v1.5.3, v1.5.4, stable v1.6.1 or recognized earlier wireless test packages. If it restores a previous layer or installs the base, perform the requested full MU reboot and run the installer again until the release reports installed. Keep the SD and recovery snapshots.
2. With GPS off, check wireless and wired maps on MU/AID, guidance, media, reverse return and reconnects. Keep the same wireless tuning for comparison (40/8/150 is the default alternate stream setting; native main-screen demand stays 30).
3. In GEM → CarPlay Maps VC → Wireless, select **Vehicle location feed (experimental): on (reboot)**. Optionally enable **GPS diagnostics probe: on**. Perform a full MU reboot, obtain a vehicle GNSS fix, then connect/reconnect wireless CarPlay without USB.
4. Export the normal base diagnostics while wireless is active. The separate wireless collector also includes GPS evidence. Exports contain bounded current NMEA/location observations; pairing stores remain excluded.
5. Inspect `wireless/state/wcp-location-source.status` for live callbacks and advancing GGA/RMC sequences. Inspect `wcp-location-latest.bin` for the 320-byte original-sentence snapshot and `wcp-rg-location.status` for source match, advertised capability, phone request and native submissions. `sent` counts calls to the native sender, not phone acknowledgements. `cpmap-gps-probe.txt` contains optional OEM position/clock observations, not generated GPS input.
6. Check loss of fix and stale input: valid forwarding must stop even if the publisher heartbeat advances. Check Wi-Fi off/reconnect, BT off with healthy Wi-Fi, source/session replacement and wired takeover. No previous-session fix should be replayed. Compare positioning behavior and accuracy with GPS off.
7. To disable, choose **Vehicle location feed (experimental): off (reboot)** and perform a full MU reboot. The probe has separate on/off/status actions and responds within a second. Disabling GPS does not change the wired OEM location path.

A fresh valid NMEA fix is required at identification. A late first fix or replacement producer needs a reconnect. Zero NMEA callbacks during wireless means the passive source may need a read-only OEM service subscription; it does not establish which GPS source the iPhone uses.

The source has a once-per-boot attempt guard. If DIO restarts after an experimental attempt, its next launch uses the normal preload chain for the remainder of that boot. Export `cpmap-gps-dio-attempt.state` with source/receiver state; a full MU reboot permits another attempt.

For rollback, use this package's **remove wireless layer** action, reboot, and follow its previous-layer instructions. For full removal, use this package's **complete OEM restore** action and follow every reboot/run-again prompt. The recovery directory and GPS preferences are archived during OEM restore. Older toolboxes do not know this new layer, so retain this SD package for recovery. Do not manually copy component binaries or delete snapshots.

These bench-tested paths still require vehicle acceptance. They cannot establish phone sensor fusion or prove receipt of location messages without the live test.
