> **Current complete stable release: [v1.6.1](../../releases/MU1367/v1.6.1/START_HERE.md).** This directory retains its exact v1.5.4 base and compatibility migrations; the current stable release builder and recovery flow are in [wireless-native/stable](../wireless-native/stable/README.md).

# MU1367 / 791 integration v1.5.4 — stable

**v1.5.4 is the recommended release** ([release files](../../releases/MU1367/v1.5.4/README.md)).

- **v1.5.4:** the AID follows the OEM navigation's arrival-time setting during CarPlay
  guidance (the unit's clock plus the remaining time), and a Toolbox stream test tries
  any map rate from 20 to 40 fps with a key frame every 5 to 15 frames. Not yet tested in
  a car.
- **v1.5.3** (from v1.5.3-e): a 4.2 s startup animation on the AID before the live CarPlay map
  (MU UI > **Startup animation**: once per boot by default, every connection or off);
  the video bridges run at a higher priority so the map keeps getting CPU while the
  navigation and the reverse camera load the unit.
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
- [Release files](../../releases/MU1367/v1.5.4/README.md) (previous stable: [v1.5.3](../../releases/MU1367/v1.5.3/README.md))
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
