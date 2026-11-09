# MU1367 / 791 integration v1.4.6-e — experimental

This release builds on the stable **v1.4.5**. It is **experimental, to be tested**.

- **U-turn lanes in left-hand traffic** (UK and similar) now show the right U-turn
  arrow. Right-hand traffic is unchanged.
- **Apple Maps with any phone language:** a phone that alternates between two names
  for the app (for example "Apple Maps" and "Mapy Apple") no longer loses the stored
  maneuvers, so arrows and lanes update from the first turn.
- **Map stream:** 25 fps / IDR 5 is the new default. The choices are 20, 25, 27, 30
  and 40 fps, all with IDR 5; the IDR 20 choices are removed.
- **Optional compressed album artwork** under **Tuning**, off by default.

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. Map-only defaults, audio and reader runtime are unchanged from
v1.4.5.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Reroute capture analysis](evidence/REROUTE-2026-11-05.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.4.6-e/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance, the map core and the menu in one
verified snapshot transaction and migrates v1.4.5 through the established
reboot boundary. Optional turn-card tuning remains available.
