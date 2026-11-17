# MU1367 v1.5.4 — stable: arrival time on the AID, stream test

**Stable release** for **K4525 / P4521 MU1367 + AID 791**. Replaces v1.5.3 as the
recommended release.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.4/CarPlay_Maps_VC_MU1367_791_v1.5.4.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **Arrival time on the AID.** With the OEM navigation setup set to show the **arrival
  time**, CarPlay guidance now shows the arrival time on the AID: the unit's own clock plus
  the remaining time from the phone, in the unit's time zone and 12/24 h format. With
  **time to destination** nothing changes. Until the unit's clock is valid after a start,
  the remaining time is shown.
- **Stream test** (Toolbox > CarPlay diagnostics): try any map rate from 20 to 40 fps and a
  key frame every 5 to 15 frames. The test values override the MU UI stream choice until
  **Stream test: off** and apply on the next phone connection. The default stays
  40 fps / IDR 5.
- **Everything of v1.5.3:** the startup animation on the AID, the higher video-bridge
  priority, the steadier CarPlay map, P4521 support and the saved-snapshot tuning entries.
  The MU menus, audio and reader are the v1.5.3 ones, byte for byte; the video bridges and
  the Android Auto feeder are the v1.5.3 sources rebuilt with a newer compiler.
- **Android Auto on the AID** (Google Maps picture and native VW arrows from an Android
  phone) is included but **not yet fully tested**.

The two new features are verified off the unit (host, the factory Java VM and the firmware
shell in the QNX emulator, full install and migration tests) but **not yet tested in a
car**. Updating from v1.5.3 or any earlier supported version uses the checked two-stage
update: install → full reboot → install again. MU UI settings are kept. The final message
is `MU1367_RELEASE_1_5_4_INSTALLED_FULL_REBOOT_REQUIRED`.

## Thanks and sources

[omonob](https://github.com/omonob) (original [CarPlay Maps VC](https://github.com/omonob/MHI2-Carplay-Maps)),
[luka-dev](https://github.com/luka-dev) (CarPlay route guidance research),
[chrzanowy](https://github.com/chrzanowy) (Android Auto feeder and route translation),
[MacsInSpace](https://github.com/MacsInSpace) (the `gal` cluster-map hook),
[Mr-MIBonk](https://github.com/Mr-MIBonk) (M.I.B.),
Jille & Olli ([MIB2 Toolbox](https://github.com/jilleb/mib2-toolbox)) and
[Karan](https://t.me/karanldn) for valuable road tests and feedback. Details in the
[release notes](RELEASE-NOTES.md#thanks-and-sources).
