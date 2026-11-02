# MU1367 / 791 integration v1.4.3

The maintained MU1367 package combines CarPlay maps, native arrows/progress,
ETA/current road and lane guidance, audio metadata/artwork, MU display settings
and reconnect recovery. The retained v1.4.2 fix makes the lane decoder emit the factory VW
left/right U-turn bytes (114/146), incorporating [PR #8](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/pull/8). Defaults are map only and **30 fps / IDR5**. Optional
turn-card tuning adds both the runtime support and its MU UI controls.

- [Install, update from existing test builds, and rollback](INSTALL.md)
- [Known issues and planned navigation improvements](KNOWN-ISSUES.md)
- [Independent OEM reset and no-SD recovery](RECOVERY.md)
- [Source layout, builds and verification](DEVELOPMENT.md)
- [Download v1.4.3](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.3)

K4525 or **P4521 MU1367 + AID 791**. P4521 installation remains **experimental**;
the prior P4521 experimental build has been confirmed working in a vehicle.
This combined v1.4.3 package adds the full current feature set. Mini Pico can override the MU's map-only URL
and still display a card. Normal safe-area alignment is restored. Unused-lane
blank slots are expected OEM rendering. Apple Maps/Waze remain planned work.

U-turn encoding and factory serialization are verified against MU1367. Vehicle
rendering was reported on MU1161 + AID 791; MU1367 U-turn acceptance remains
pending. The patch covers −180…−170° and 170…179°; +180° selects left for
right-hand traffic. ±169° retains its previous sector encoding.
