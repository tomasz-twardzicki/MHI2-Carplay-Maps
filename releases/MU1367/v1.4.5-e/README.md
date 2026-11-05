# MU1367 v1.4.5-e — experimental reroute handling and 25 fps test option

**EXPERIMENTAL — TO BE TESTED.** Based on the stable **v1.4.4** package, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its experimental status.
This package has no vehicle result yet. Use v1.4.4 for a stable installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.4.5-e/CarPlay_Maps_VC_MU1367_791_v1.4.5-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- A reroute shows the factory calculating symbol. Distance, progress bar, road and
  arrival data keep their values instead of restarting.
- With no maneuver yet, the placeholder is the straight direction-to-destination arrow.
- **App-Connect > Virtual Cockpit settings > Map stream** adds an optional
  **25 fps / IDR 5 (test)** choice. 30 fps / IDR 5 stays the default.

The guidance JAR, map core and MU menu change. Audio and the reader match v1.4.4.

An installed v1.4.4 uses the checked removal, full reboot and install sequence, as do
all earlier supported revisions. Preserve all snapshots and follow `START_HERE.md`.
Before rolling back to v1.4.4 or older, select another map stream, because older menus
do not recognize the new choice.

Leave a route on purpose to test a reroute, and compare 30 and 25 fps with the same app
and route. Export diagnostics while the issue is on screen.

Still open from v1.4.4: Apple Maps results vary and Waze has no vehicle result. See the
[v1.4.4 known issues](../v1.4.4/README.md).
