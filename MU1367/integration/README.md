# MU1367 / 791 integration v1.5.0-e — experimental

This release builds on stable **v1.4.6**. It is **experimental, to be tested**.

- **Android Auto on the AID:** the Google Maps picture from an Android phone and
  native VW turn arrows with distance, installed by the same install action as
  CarPlay. Two new menu entries switch the Android Auto cluster map off and on.
- **CarPlay** is as in v1.4.6: driving-side U-turn lanes, Apple Maps in any phone
  language, 27 fps / IDR 5 default and compressed album artwork by default.

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. Only the guidance JAR changes in the CarPlay runtime.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Reroute capture analysis](evidence/REROUTE-2026-11-05.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.5.0-e/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance, the map core and the menu in one
verified snapshot transaction and migrates v1.4.5 through the established
reboot boundary. Optional turn-card tuning remains available.
