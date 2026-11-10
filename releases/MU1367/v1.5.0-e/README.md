# MU1367 v1.5.0-e — experimental Android Auto on the AID

**Replaced by [v1.5.1-e](../v1.5.1-e/README.md)**, which fixes the Android Auto cluster map freezing; this release is no longer offered for download.

**EXPERIMENTAL — TO BE TESTED.** Based on stable **v1.4.6**, for **K4525 / P4521 MU1367 +
AID 791**. P4521 installation retains its experimental status. This package has **no
vehicle result yet**. Use v1.4.6 for a stable CarPlay installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.0-e/CarPlay_Maps_VC_MU1367_791_v1.5.0-e.zip) · [Install/update/rollback](START_HERE.md) ·
[Release notes](RELEASE-NOTES.md) · [Reader recovery](READER-RECOVERY.md) ·
[Known issues](KNOWN-ISSUES.md) · [Checksums](SHA256SUMS.txt) ·
[Verification](VERIFICATION.json).

- **Android Auto in the same installation.** The usual **Install / update CarPlay
  integration (reboot)** entry installs Android Auto together with every CarPlay
  feature of v1.4.6: the Google Maps picture from an Android phone (cable) on the
  AID, and native VW turn arrows with distance and the countdown bar.
- **Android Auto cluster map: off / on** in the same menu switch only the Android Auto
  hook. The MU menu's cluster map switch applies to Android Auto as well.
- **CarPlay is unchanged.** Only the guidance JAR changes; map core, menu, audio,
  compressed artwork, reader and driver match v1.4.6.
- **Removal:** **Recovery > Remove latest update only** removes Android Auto first and
  restores the factory Android Auto receiver from its verified snapshot. The menu's
  **RESTORE OEM** removes Android Auto first as well.

Android Auto limits: the picture starts about 5 s after connecting; a dark start needs a
reconnect; no arrow for the first route step; remaining distance, arrival time, lanes
and road name are not sent to the VW cluster; Android Auto runs at 30 fps whatever the
MU frame-rate setting.

An installed v1.4.6 (and every earlier supported revision) uses the checked removal,
full reboot and install sequence.

Android Auto builds on [chrzanowy/mhi2-aid-carplay](https://github.com/chrzanowy/mhi2-aid-carplay)
and MacsInSpace's [mib-cluster-map](https://github.com/MacsInSpace/mib-cluster-map) hook.
