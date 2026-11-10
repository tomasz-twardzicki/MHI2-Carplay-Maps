# MU1367 / 791 integration v1.4.6 — stable

Stable release of the v1.4.6-e build, with two new defaults.

- **U-turn lanes in left-hand traffic** (UK and similar) show the right U-turn arrow.
  Right-hand traffic is unchanged.
- **Apple Maps with any phone language:** a phone that alternates between two names
  for the app (for example "Apple Maps" and "Mapy Apple") no longer loses the stored
  maneuvers, so arrows and lanes update from the first turn.
- **Map stream:** **27 fps / IDR 5 is the default**. The choices are 20, 25, 27, 30 and
  40 fps, all with IDR 5. A saved choice is kept.
- **Compressed album artwork is installed by default** (lossless; **Tuning** switches it
  off and on).

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. Guidance, audio and reader runtime are byte-identical to v1.4.6-e;
only the map core and MU menu change, for the new stream default.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Reroute capture analysis](evidence/REROUTE-2026-11-05.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.4.6/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance, the map core and the menu in one
verified snapshot transaction and migrates v1.4.5 through the established
reboot boundary. Optional turn-card tuning remains available.
