# MU1367 / 791 integration v1.4.5-e — experimental

This release builds on the stable **v1.4.4**. It is **experimental, to be tested**.

- A reroute shows the factory calculating symbol, and the distance, progress bar,
  road and arrival data keep their values instead of restarting.
- With no maneuver yet, the placeholder is the straight direction-to-destination
  arrow.
- **App-Connect > Virtual Cockpit settings > Map stream** adds an optional
  **25 fps / IDR 5 (test)** choice. 30 fps / IDR 5 stays the default.

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. The U-turn lane fix, map-only defaults, **30 fps / IDR5**,
audio and reader runtime are unchanged from v1.4.4.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Reroute capture analysis](evidence/REROUTE-2026-11-05.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.4.5-e/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance, the map core and the menu in one
verified snapshot transaction and migrates v1.4.4 through the established
reboot boundary. Optional turn-card tuning remains available.
