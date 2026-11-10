# MU1367 v1.5.1-e — experimental Android Auto on the AID (cluster-map freeze fixed, CarPlay boot drop-out fixed)

**EXPERIMENTAL — TO BE TESTED.** Replaces v1.5.0-e. Based on stable **v1.4.6**, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its experimental status.
Use v1.4.6 for a stable CarPlay installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.1-e/CarPlay_Maps_VC_MU1367_791_v1.5.1-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **Android Auto in the same installation** as every CarPlay feature of v1.4.6: the Google
  Maps picture from an Android phone (cable) on the AID and native VW turn arrows with
  distance and the countdown bar.
- **New in v1.5.1-e: the Android Auto map no longer freezes after a stream hiccup.** In the
  first car test guidance worked but the cluster map froze until a reconnect.
- **New in this rebuild: the CarPlay map no longer drops out about 18 s after every boot.**
  The factory video encoder briefly takes the MOST video output while the unit boots; the
  bridge now takes it back (up to 3 times in the first 3 minutes) instead of exiting into a
  4 s restart. The bridge is built from this repository's source; the upstream one is kept
  in the snapshot.
- **Diagnostics export** now includes the Android Auto feeder, bridge and session files.
- **Android Auto cluster map: off / on** in the same menu switch only the Android Auto map.

Updating from v1.5.0-e, from the first v1.5.1-e package (published earlier on 2026-11-10)
or from older releases goes through the checked two-stage update: install → full reboot →
install again. Stage 1 also removes the old Android Auto layer; all snapshots are kept.

Android Auto limits: the picture starts about 5 s after connecting; a dark start needs a
reconnect; no arrow for the first route step; remaining distance, arrival time, lanes and
road name are not sent to the VW cluster; 30 fps. Use a short, good USB data cable.

Builds on [chrzanowy/mhi2-aid-carplay](https://github.com/chrzanowy/mhi2-aid-carplay) and
MacsInSpace's [mib-cluster-map](https://github.com/MacsInSpace/mib-cluster-map) hook.
