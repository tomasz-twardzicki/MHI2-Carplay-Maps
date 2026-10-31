# MU1367 / 791 integration v1.4.1

The maintained MU1367 package combines CarPlay maps, native arrows/progress,
ETA/current road and lane guidance, audio metadata/artwork, MU display settings
and reconnect recovery. Defaults are map only and **30 fps / IDR5**. Optional
turn-card tuning adds both the runtime support and its MU UI controls.

- [Install, update from existing test builds, and rollback](INSTALL.md)
- [Known issues and planned navigation improvements](KNOWN-ISSUES.md)
- [Independent OEM reset and no-SD recovery](RECOVERY.md)
- [Source layout, builds and verification](DEVELOPMENT.md)
- [Download v1.4.1](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.1)

Exact K4525 MU1367 + AID 791 only. Mini Pico can override the MU's map-only URL
and still display a card. Normal safe-area alignment is restored. Unused-lane
blank slots are expected OEM rendering. Apple Maps/Waze remain planned work.
