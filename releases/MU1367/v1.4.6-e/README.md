# MU1367 v1.4.6-e — experimental U-turn lanes, Apple Maps languages and 25 fps default

**EXPERIMENTAL — TO BE TESTED.** Based on the stable **v1.4.5** package, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its experimental status.
This package has no vehicle result yet. Use v1.4.5 for a stable installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.4.6-e/CarPlay_Maps_VC_MU1367_791_v1.4.6-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **U-turn lanes in left-hand traffic** (UK and similar) show the right U-turn arrow.
  Right-hand traffic is unchanged.
- **Apple Maps with any phone language:** alternating app names ("Apple Maps" /
  "Mapy Apple") no longer clear the stored maneuvers, so arrows and lanes update from
  the first turn.
- **Map stream:** 25 fps / IDR 5 is the default; the choices are 20, 25, 27, 30 and
  40 fps, all with IDR 5.
- **Optional compressed album artwork** under **Tuning**, off by default.

The guidance JAR, map core and MU menu change. Audio and the reader match v1.4.5.

An installed v1.4.5 uses the checked removal, full reboot and install sequence, as do
all earlier supported revisions. Remove the v1.4.5 artwork refresh test first if it is
installed. Before rolling back, select 30 or 40 fps / IDR 5, because older menus do not
recognize 20 or 27 fps.

Still open: wheel-arrow zoom over a wireless adapter also opens the factory cluster
menu, and Waze has no vehicle result.
