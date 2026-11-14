# MU1367 / 791 integration v1.5.2 — stable

Stable release, built from v1.5.2-e after vehicle tests with very good results. It
replaces **v1.4.6** as the recommended release.

- **v1.5.2:** 40 fps / IDR 5 is the default map stream (25 and 30 fps stay in the MU UI);
  P4521 is no longer experimental; **Tuning > Saved snapshots** lists the copies kept
  by earlier installations, rollbacks and OEM resets and removes them one at a time or
  all at once.
- **v1.5.2-e:** the map-only view declares v1.2.2's taller safe area (160,20,480,440)
  for a closer, lighter map, and the video bridge allows a 2048-packet backlog (was
  1024) before it resets.
- **v1.5.1-e:** the CarPlay video bridge takes the MOST output back from the factory
  encoder during boot instead of exiting; the Android Auto cluster map no longer
  freezes after a stream hiccup.
- **Android Auto on the AID** (since v1.5.0-e): the Google Maps picture from an Android
  phone and native VW turn arrows with distance, installed by the same install action
  as CarPlay. **Not yet fully tested.**
- **CarPlay** keeps everything of v1.4.6: driving-side U-turn lanes, Apple Maps in any
  phone language and compressed album artwork by default.

Supports **K4525 and P4521 MU1367 + AID 791**, both tested in vehicles.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Reroute capture analysis](evidence/REROUTE-2026-11-05.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.5.2/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance, the map core and the menu in one
verified snapshot transaction and migrates v1.4.5 through the established
reboot boundary. Optional turn-card tuning remains available.

## Thanks and sources

omonob (original CarPlay Maps VC), luka-dev (CarPlay route guidance research),
chrzanowy (Android Auto feeder and route translation), MacsInSpace (the `gal`
cluster-map hook), Mr-MIBonk (M.I.B.), Jille & Olli (MIB2 Toolbox) and
[Karan](https://t.me/karanldn) for road tests and feedback. Links are in
[RELEASE-NOTES.md](RELEASE-NOTES.md#thanks-and-sources); licenses in [NOTICE.md](NOTICE.md).
