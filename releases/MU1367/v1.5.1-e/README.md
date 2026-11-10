# MU1367 v1.5.1-e — experimental Android Auto on the AID (cluster-map freeze fixed)

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
- **Diagnostics export** now includes the Android Auto feeder, bridge and session files.
- **Android Auto cluster map: off / on** in the same menu switch only the Android Auto map.

Updating from v1.5.0-e replaces only the Android Auto files (no extra reboot stage). An
installed pre-release test build goes through the checked removal → full reboot → install.

Android Auto limits: the picture starts about 5 s after connecting; a dark start needs a
reconnect; no arrow for the first route step; remaining distance, arrival time, lanes and
road name are not sent to the VW cluster; 30 fps. Use a short, good USB data cable.

Builds on [chrzanowy/mhi2-aid-carplay](https://github.com/chrzanowy/mhi2-aid-carplay) and
MacsInSpace's [mib-cluster-map](https://github.com/MacsInSpace/mib-cluster-map) hook.
