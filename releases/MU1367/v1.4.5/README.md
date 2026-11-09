# MU1367 / 791 v1.4.5 — stable

Stable release of the **v1.4.5-e** build, for **K4525 / P4521 MU1367 + AID 791**.
P4521 installation retains its experimental status.

[Release and ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.5) ·
[Install/update/recovery](../v1.4.5-e/START_HERE.md) ·
[Release notes](../v1.4.5-e/RELEASE-NOTES.md) ·
[Reader recovery](../v1.4.5-e/READER-RECOVERY.md) ·
[Known issues](../v1.4.5-e/KNOWN-ISSUES.md) · [SHA-256](SHA256SUMS.txt) ·
[Verification](../v1.4.5-e/VERIFICATION.json).

The ZIP is **byte-identical** to v1.4.5-e
(`80e38ec252a8bf84af628e450af80e6a992319315aa8e4be4c66837fb61f4826`); it was not
rebuilt, so its menu banner, documents and completion message still read
"v1.4.5-e" / "experimental". Those labels refer to this same package.

## What changed since v1.4.4

- **Reroutes:** the factory calculating symbol shows instead of guidance dropping, and
  the distance, progress bar, road name and arrival data keep their values until the
  phone reports a real distance again.
- **Placeholder arrow:** with an active route and no maneuver yet, the cluster shows
  the straight direction-to-destination arrow.
- **25 fps / IDR 5 (test)** map stream choice. 30 fps / IDR 5 stays the default.

## Known issues in this release

- **U-turn lane arrows point left in left-hand traffic** (UK and similar). A lane at
  exactly 180° is always drawn as a left U-turn; the main arrow is correct. Fixed in
  v1.4.6-e.
- **Apple Maps with some phone languages** starts updating arrows and lanes a few
  turns late. The phone alternates between two names for the app (for example "Apple
  Maps" and "Mapy Apple"), and each change clears the stored maneuvers. English
  phones are not affected. Fixed in v1.4.6-e.
- **Zooming with the wheel arrows over a wireless adapter** also opens the factory
  menu on the cluster. Under investigation.
- **Waze has no vehicle result.**

Installation, migration from v1.4.4 / v1.4.4-e and earlier supported revisions,
rollback and the independent OEM reset are unchanged from v1.4.5-e. Before rolling
back to v1.4.4 or older, select another map stream than 25 fps, or use **Reset saved
MU UI settings**. Follow `START_HERE.md` exactly and preserve all snapshots.
